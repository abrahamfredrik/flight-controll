import logging
from typing import List, Dict, Any, Optional, Set
from datetime import datetime
import time
from . import repository, notifier, utils
from .change_detector import detect_and_apply_updates, fetch_removed_events, normalize_dtstamp

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

    def normalize_dtstamp(self, text: Optional[str]) -> str:
        return normalize_dtstamp(text)

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
        existing_all = self.repository.existing_all_uids()

        # If the $in matching returned nothing but DB clearly contains some fetched uids,
        # use that information to recompute matching/new sets (guard for fakes)
        if not existing_matching and (fetched_uids & existing_all):
            existing_matching = fetched_uids & existing_all
            new_events = [event for event in events if event["uid"] not in existing_matching]
            new_count = len(new_events)

        # Detect and apply updates for events that still exist but changed
        updated_events = detect_and_apply_updates(events, existing_matching, self.repository)
        updated_count = len(updated_events)

        # Find and remove events that existed previously but are no longer fetched
        removed_events = fetch_removed_events(existing_all, fetched_uids, self.repository)
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
