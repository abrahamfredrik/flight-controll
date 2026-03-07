import logging
import re
from typing import List, Dict, Any, Optional, Set
from datetime import datetime
import time
from . import repository, notifier, utils

from pymongo import MongoClient
from ..webcal.fetcher import WebcalFetcher
from ..mail.sender import MailService
from ..config import Config

EXCLUDED_LOCATIONS = ["privat"]


class EventService:
    """Service responsible for fetching events, persisting new ones and sending email.

    Improvements:
    - Accept optional `mongo_client` or `events_collection` to allow dependency injection
      for testing and to avoid creating real network clients at import-time.
    - Keep backwards compatibility when mongo_client/events_collection are not provided.
    """

    def __init__(
        self,
        config: Config,
        email_sender_cls=MailService,
        fetcher_cls=WebcalFetcher,
        mongo_client: Optional[MongoClient] = None,
        events_collection: Optional[object] = None,
        repo: Optional[repository.EventRepository] = None,
    ):
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.email_sender_cls = email_sender_cls
        self.fetcher_cls = fetcher_cls
        # Repository injection: accept an EventRepository instance directly
        if repo is not None:
            self.repository = repo
            # expose underlying collection for backward compatibility
            self.events_collection = getattr(self.repository, "collection", None)
            self.mongo_client = getattr(self.repository, "collection", None)
            self.db = None
            return

        # allow tests to inject a fake collection directly; wrap it in repository
        if events_collection is not None:
            self.events_collection = events_collection
            self.mongo_client = mongo_client
            self.db = None
            self.repository = repository.EventRepository(self.events_collection)
            return

        # otherwise construct or use provided mongo_client and create repository
        self.mongo_uri = (
            f"mongodb+srv://{self.config.MONGO_USERNAME}:{self.config.MONGO_PASSWORD}@"
            f"{self.config.MONGO_HOST}/{self.config.MONGO_DB}?retryWrites=true&w=majority"
        )
        self.mongo_client = mongo_client or MongoClient(self.mongo_uri)
        self.db = self.mongo_client[self.config.MONGO_DB]
        self.events_collection = self.db[self.config.MONGO_COLLECTION]
        self.repository = repository.EventRepository(self.events_collection)

    def store_events(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Persist new event dicts to the events collection.

        Args:
            events: list of event dictionaries as returned by the fetcher.

        Returns:
            The same list of events that were passed in.
        """
        # persist via repository
        self.repository.insert_events(events)
        return events

    def _ensure_repository(self) -> None:
        """Ensure `self.repository` is available, creating it from
        `self.events_collection` when necessary (supports tests that set
        `events_collection` on instances created via `object.__new__`).
        """
        if not hasattr(self, "repository") or self.repository is None:
            if hasattr(self, "events_collection") and self.events_collection is not None:
                self.repository = repository.EventRepository(self.events_collection)
            else:
                raise RuntimeError("No repository or events_collection available on EventService")

    def fetch_events(self) -> List[Dict[str, Any]]:
        """Fetch events from the external calendar provider and filter them.

        Returns:
            A list of event dictionaries. Events from excluded locations are
            filtered out.
        """
        fetcher: WebcalFetcher = self.fetcher_cls(self.config.WEB_CAL_URL)
        events = fetcher.fetch_events()
        excluded_lower = [loc.lower() for loc in EXCLUDED_LOCATIONS]
        filtered_events = [
            event
            for event in events
            if not (
                event.get("location")
                and event["location"].strip().lower() in excluded_lower
            )
        ]
        return filtered_events

    def send_events_email(self, events: List[Dict[str, Any]]) -> None:
        """Send one plain-text email describing the provided events.

        Args:
            events: list of event dicts to include in the email. If empty,
                the function is a no-op.
        """
        if not events:
            return
        email_sender = self.email_sender_cls(
            self.config.SMTP_SERVER,
            self.config.SMTP_PORT,
            self.config.SMTP_USERNAME,
            self.config.SMTP_PASSWORD,
        )
        subject = f"New Events: {len(events)} found"
        body = "Event Details:\n\n"
        for event in events:
            body += (
                f"Summary: {event['summary']}\n"
                f"Start Time: {event['dtstart']}\n"
                f"End Time: {event['dtend']}\n"
                f"Description: {event.get('description', 'N/A')}\n"
                f"Location: {event.get('location', 'N/A')}\n"
                "--------------------------\n"
            )
        email_sender.send_email(self.config.RECIPIENT_EMAIL, subject, body)

    def send_summary_email(
        self,
        added_events: List[Dict[str, Any]],
        removed_events: List[Dict[str, Any]],
        updated_events: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Send a single summary email covering added, removed and updated events.

        Delegates to the `notifier` module which builds the HTML/plain bodies.
        """
        notifier.send_summary(
            self.email_sender_cls,
            self.config,
            added_events or [],
            removed_events or [],
            updated_events or [],
        )

    def filter_new_events(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        uids = [event["uid"] for event in events]
        existing_uids_cursor = self.repository.collection.find({"uid": {"$in": uids}}, {"uid": 1})
        existing_uids = {doc["uid"] for doc in existing_uids_cursor}
        return [event for event in events if event["uid"] not in existing_uids]

    def _existing_matching_uids(self, fetched_uids: Set[str]) -> Set[str]:
        return self.repository.existing_matching_uids(fetched_uids)

    def _parse_dt(self, v: Any) -> Optional[datetime]:
        return utils.parse_dt(v)

    def _event_changed(
        self,
        old_start: Optional[datetime],
        old_end: Optional[datetime],
        new_start: Optional[datetime],
        new_end: Optional[datetime],
        old_desc: Optional[str],
        new_desc: Optional[str],
        old_loc: Optional[str],
        new_loc: Optional[str],
    ) -> bool:
        """Return True if start, end, description, or location differ (None-safe)."""
        if (old_start is None) != (new_start is None):
            return True
        if (
            old_start is not None
            and new_start is not None
            and old_start != new_start
        ):
            return True
        if (old_end is None) != (new_end is None):
            return True
        if old_end is not None and new_end is not None and old_end != new_end:
            return True
        if self.normalize_dtstamp(old_desc) != self.normalize_dtstamp(new_desc):
            return True
        if (old_loc or "") != (new_loc or ""):
            return True
        return False

    def _detect_and_apply_updates(
        self, events: List[Dict[str, Any]], existing_matching: Set[str]
    ) -> List[Dict[str, Any]]:
        """Detect events whose start/end changed compared to stored docs.

        Apply the updates to the DB and return a list of update records with
        old and new values for inclusion in the summary email.
        """
        if not existing_matching:
            return []

        # retrieve stored documents for matching uids
        stored_cursor = self.repository.find_docs_by_uids(list(existing_matching))
        # Fake collections in tests may only expose full docs via .docs
        if (
            stored_cursor
            and all(
                "start_time" not in d and "end_time" not in d and "summary" not in d
                for d in stored_cursor
            )
            and hasattr(self.events_collection, "docs")
        ):
            stored_cursor = list(getattr(self.events_collection, "docs", []))

        stored_by_uid = {doc["uid"]: doc for doc in stored_cursor}

        updates: List[Dict[str, Any]] = []
        for ev in events:
            uid = ev.get("uid")
            if uid not in stored_by_uid:
                continue
            stored = stored_by_uid[uid]

            old_start = utils.parse_dt(
                stored.get("start_time") or stored.get("dtstart")
            )
            old_end = utils.parse_dt(stored.get("end_time") or stored.get("dtend"))
            new_start = utils.parse_dt(ev.get("dtstart") or ev.get("start_time"))
            new_end = utils.parse_dt(ev.get("dtend") or ev.get("end_time"))
            old_desc = stored.get("description")
            new_desc = ev.get("description")
            old_loc = stored.get("location")
            new_loc = ev.get("location")

            if not self._event_changed(
                old_start, old_end, new_start, new_end,
                old_desc, new_desc, old_loc, new_loc,
            ):
                continue

            # prepare update payload (store as ISO strings if present)
            set_payload: Dict[str, Any] = {}
            if new_start is not None:
                set_payload["start_time"] = new_start.isoformat()
            if new_end is not None:
                set_payload["end_time"] = new_end.isoformat()
            for k in ("summary", "description", "location"):
                if k in ev:
                    set_payload[k] = ev[k]

            if set_payload:
                self.repository.update_one(uid, set_payload)

            updates.append(
                {
                    "uid": uid,
                    "summary": ev.get("summary", stored.get("summary")),
                    "old_description": old_desc,
                    "new_description": new_desc,
                    "old_location": old_loc,
                    "new_location": new_loc,
                    "old_start": (
                        old_start.isoformat() if old_start is not None else None
                    ),
                    "old_end": old_end.isoformat() if old_end is not None else None,
                    "new_start": (
                        new_start.isoformat() if new_start is not None else None
                    ),
                    "new_end": new_end.isoformat() if new_end is not None else None,
                }
            )

        return updates

    def _existing_all_uids(self) -> Set[str]:
        """Return all uids currently stored in the collection.

        This prefers a normal `find({}, {"uid":1})` but falls back to a
        `docs` attribute (used by the lightweight FakeCollection in tests).
        """
        return self.repository.existing_all_uids()

    def _fetch_and_remove_events(
        self, existing_all: Set[str], fetched_uids: Set[str]
    ) -> List[Dict[str, Any]]:
        """Return list of removed event documents (and delete them from DB).

        `removed_uids` are those present in DB but not in the fetched set.
        The stored documents are returned so they can be included in the
        summary email.
        """
        removed_uids = list(existing_all - fetched_uids)
        removed_events: List[Dict[str, Any]] = []
        if not removed_uids:
            return removed_events

        # Retrieve stored docs for the removed uids
        stored = self.repository.find_docs_by_uids(removed_uids)

        # Only consider events whose start time is within the allowed window.
        future_docs = []
        for doc in stored:
            st = utils.parse_dt(doc.get("start_time") or doc.get("dtstart"))
            if st is not None and utils.is_within_removal_window(st):
                future_docs.append(doc)

        # delete only the future events from DB and return them for email
        if future_docs:
            future_uids = [d["uid"] for d in future_docs]
            self.repository.delete_by_uids(future_uids)

        return future_docs

    def fetch_persist_and_send_events(self) -> List[Dict[str, Any]]:
        # ensure repository is available for instances created without __init__
        try:
            self._ensure_repository()
        except Exception:
            # if repository cannot be ensured, allow original behavior to raise later
            pass

        start_ts = time.monotonic()
        if self.logger:
            self.logger.info("fetch_persist_and_send_events.start", extra={"action": "fetch_start"})

        # fetch remote events
        events = self.fetch_events()
        fetched_count = len(events)
        fetched_uids = {event["uid"] for event in events}
        if self.logger:
            self.logger.info("fetch_persist_and_send_events.fetched", extra={"fetched_count": fetched_count})

        # Which fetched uids already exist in DB?
        existing_matching = self._existing_matching_uids(fetched_uids)

        # New events are those fetched but not present in DB
        new_events = [event for event in events if event["uid"] not in existing_matching]
        new_count = len(new_events)

        # Determine all uids present in DB (used to compute removals)
        existing_all = self._existing_all_uids()

        # If the $in matching returned nothing but DB clearly contains some fetched uids,
        # use that information to recompute matching/new sets (guard for fakes)
        if not existing_matching and (fetched_uids & existing_all):
            existing_matching = fetched_uids & existing_all
            new_events = [event for event in events if event["uid"] not in existing_matching]
            new_count = len(new_events)

        # Detect and apply updates for events that still exist but changed
        updated_events = self._detect_and_apply_updates(events, existing_matching)
        updated_count = len(updated_events)

        # Find and remove events that existed previously but are no longer fetched
        removed_events = self._fetch_and_remove_events(existing_all, fetched_uids)
        removed_count = len(removed_events)

        # persist new events and send a single summary email for added/removed/updated
        if new_events:
            self.store_events(new_events)

        # send summary
        try:
            self.send_summary_email(new_events, removed_events, updated_events)
            email_status = "sent"
        except Exception as e:
            if self.logger:
                self.logger.exception("Failed to send summary email: %s", e)
            email_status = "failed"

        duration = time.monotonic() - start_ts
        # Structured summary log of the run
        if self.logger:
            self.logger.info(
                "fetch_persist_and_send_events.complete",
                extra={
                    "duration_seconds": duration,
                    "fetched_count": fetched_count,
                    "new_count": new_count,
                    "updated_count": updated_count,
                    "removed_count": removed_count,
                    "email_status": email_status,
                },
            )

        # Return list of processed new events for backward compatibility
        return new_events
    
    def normalize_dtstamp(self, text: Optional[str]) -> str:
        if text is None:
            return ""
        # Remove the entire DTSTAMP line (including trailing spaces/newline)
        newText = re.sub(r"DTSTAMP:[^\n]*\n?", "", text)
        # Optional: also normalize whitespace
        return newText.strip()
