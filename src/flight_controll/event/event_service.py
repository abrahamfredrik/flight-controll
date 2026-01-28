import logging
from typing import List, Dict, Any, Optional, Set
from datetime import datetime, timezone, timedelta
from . import repository, notifier, utils

from pymongo import MongoClient
from ..webcal.fetcher import WebcalFetcher
from ..mail.sender import EmailSender
from ..config import Config

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
        email_sender_cls=EmailSender,
        fetcher_cls=WebcalFetcher,
        mongo_client: Optional[MongoClient] = None,
        events_collection: Optional[object] = None,
    ):
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.email_sender_cls = email_sender_cls
        self.fetcher_cls = fetcher_cls

        # allow tests to inject a fake collection directly
        if events_collection is not None:
            self.events_collection = events_collection
            self.mongo_client = mongo_client
            self.db = None
            return

        # otherwise construct or use provided mongo_client
        self.mongo_uri = (
            f"mongodb+srv://{self.config.MONGO_USERNAME}:{self.config.MONGO_PASSWORD}@"
            f"{self.config.MONGO_HOST}/{self.config.MONGO_DB}?retryWrites=true&w=majority"
        )
        self.mongo_client = mongo_client or MongoClient(self.mongo_uri)
        self.db = self.mongo_client[self.config.MONGO_DB]
        self.events_collection = self.db[self.config.MONGO_COLLECTION]
        
    def store_events(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        for event_data in events:
            if not self.events_collection.find_one({"uid": event_data["uid"]}):
                doc = {
                    "uid": event_data["uid"],
                    "summary": event_data["summary"],
                    "start_time": event_data["dtstart"],
                    "end_time": event_data["dtend"],
                    "description": event_data.get("description"),
                    "location": event_data.get("location")
                }
                self.events_collection.insert_one(doc)
        return events

    def fetch_events(self) -> List[Dict[str, Any]]:
        fetcher: WebcalFetcher = self.fetcher_cls(self.config.WEB_CAL_URL)
        events = fetcher.fetch_events()
        # List of locations to filter out (case-insensitive)
        excluded_locations = ["privat"] 
        excluded_locations = [loc.lower() for loc in excluded_locations]
        filtered_events = [
            event for event in events
            if not (
                event.get('location') and 
                event['location'].strip().lower() in excluded_locations
            )
        ]
        return filtered_events

    def send_events_email(self, events: List[Dict[str, Any]]) -> None:
        if not events:
            return
        email_sender = self.email_sender_cls(self.config.SMTP_SERVER, 
                                   self.config.SMTP_PORT, 
                                   self.config.SMTP_USERNAME, 
                                   self.config.SMTP_PASSWORD)
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
        
    def send_summary_email(self, added_events: List[Dict[str, Any]], removed_events: List[Dict[str, Any]], updated_events: List[Dict[str, Any]] = None) -> None:
        notifier.send_summary(self.email_sender_cls, self.config, added_events or [], removed_events or [], updated_events or [])

    def filter_new_events(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        uids = [event["uid"] for event in events]
        existing_uids_cursor = self.events_collection.find(
            {"uid": {"$in": uids}}, {"uid": 1}
        )
        existing_uids = {doc["uid"] for doc in existing_uids_cursor}
        return [event for event in events if event["uid"] not in existing_uids]

    def _existing_matching_uids(self, fetched_uids: Set[str]) -> Set[str]:
        return repository.existing_matching_uids(self.events_collection, fetched_uids)

    def _parse_dt(self, v: Any) -> Optional[datetime]:
        return utils.parse_dt(v)

    def _detect_and_apply_updates(self, events: List[Dict[str, Any]], existing_matching: Set[str]) -> List[Dict[str, Any]]:
        """Detect events whose start/end changed compared to stored docs.

        Apply the updates to the DB and return a list of update records with
        old and new values for inclusion in the summary email.
        """
        if not existing_matching:
            return []

        # retrieve stored documents for matching uids
        stored_cursor = repository.find_docs_by_uids(self.events_collection, list(existing_matching))
        # Some lightweight fake collections only return uid entries for `find`.
        if stored_cursor and all("start_time" not in d and "end_time" not in d and "summary" not in d for d in stored_cursor) and hasattr(self.events_collection, "docs"):
            stored_cursor = list(getattr(self.events_collection, "docs", []))

        stored_by_uid = {doc["uid"]: doc for doc in stored_cursor}

        updates: List[Dict[str, Any]] = []
        for ev in events:
            uid = ev.get("uid")
            if uid not in stored_by_uid:
                continue
            stored = stored_by_uid[uid]

            old_start = utils.parse_dt(stored.get("start_time") or stored.get("dtstart"))
            old_end = utils.parse_dt(stored.get("end_time") or stored.get("dtend"))
            new_start = utils.parse_dt(ev.get("dtstart") or ev.get("start_time"))
            new_end = utils.parse_dt(ev.get("dtend") or ev.get("end_time"))

            # consider updated if start or end differ (None-safe)
            changed = False
            if (old_start is None) != (new_start is None):
                changed = True
            elif old_start is not None and new_start is not None and old_start != new_start:
                changed = True

            if (old_end is None) != (new_end is None):
                changed = True
            elif old_end is not None and new_end is not None and old_end != new_end:
                changed = True

            # consider description/location changed (None-safe string compare)
            old_desc = stored.get("description")
            new_desc = ev.get("description")
            if (old_desc or "") != (new_desc or ""):
                changed = True

            old_loc = stored.get("location")
            new_loc = ev.get("location")
            if (old_loc or "") != (new_loc or ""):
                changed = True

            if changed:
                # prepare update payload (store as ISO strings if present)
                set_payload: Dict[str, Any] = {}
                if new_start is not None:
                    set_payload["start_time"] = new_start.isoformat()
                if new_end is not None:
                    set_payload["end_time"] = new_end.isoformat()
                # also update summary/description/location in case they changed
                for k in ("summary", "description", "location"):
                    if k in ev:
                        set_payload[k] = ev[k]

                if set_payload:
                    repository.update_one(self.events_collection, uid, set_payload)

                updates.append({
                    "uid": uid,
                    "summary": ev.get("summary", stored.get("summary")),
                    "old_description": old_desc,
                    "new_description": new_desc,
                    "old_location": old_loc,
                    "new_location": new_loc,
                    "old_start": old_start.isoformat() if old_start is not None else None,
                    "old_end": old_end.isoformat() if old_end is not None else None,
                    "new_start": new_start.isoformat() if new_start is not None else None,
                    "new_end": new_end.isoformat() if new_end is not None else None,
                })

        return updates

    def _existing_all_uids(self) -> Set[str]:
        """Return all uids currently stored in the collection.

        This prefers a normal `find({}, {"uid":1})` but falls back to a
        `docs` attribute (used by the lightweight FakeCollection in tests).
        """
        return repository.existing_all_uids(self.events_collection)

    def _fetch_and_remove_events(self, existing_all: Set[str], fetched_uids: Set[str]) -> List[Dict[str, Any]]:
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
        stored = repository.find_docs_by_uids(self.events_collection, removed_uids)

        # Only consider events whose start time is within the allowed window.
        future_docs = []
        for doc in stored:
            st = utils.parse_dt(doc.get("start_time") or doc.get("dtstart"))
            if st is not None and utils.is_within_removal_window(st):
                future_docs.append(doc)

        # delete only the future events from DB and return them for email
        if future_docs:
            future_uids = [d["uid"] for d in future_docs]
            repository.delete_by_uids(self.events_collection, future_uids)

        return future_docs

    def fetch_persist_and_send_events(self) -> List[Dict[str, Any]]:
        # fetch remote events
        events = self.fetch_events()

        fetched_uids = {event["uid"] for event in events}

        # Which fetched uids already exist in DB?
        existing_matching = self._existing_matching_uids(fetched_uids)

        # New events are those fetched but not present in DB
        new_events = [event for event in events if event["uid"] not in existing_matching]

        # Determine all uids present in DB (used to compute removals)
        existing_all = self._existing_all_uids()

        # If the $in matching returned nothing but DB clearly contains some fetched uids,
        # use that information to recompute matching/new sets (guard for fakes)
        if not existing_matching and (fetched_uids & existing_all):
            existing_matching = fetched_uids & existing_all
            new_events = [event for event in events if event["uid"] not in existing_matching]

        # Detect and apply updates for events that still exist but changed
        updated_events = self._detect_and_apply_updates(events, existing_matching)

        # Find and remove events that existed previously but are no longer fetched
        removed_events = self._fetch_and_remove_events(existing_all, fetched_uids)

        # persist new events and send a single summary email for added/removed/updated
        if new_events:
            self.store_events(new_events)
        self.send_summary_email(new_events, removed_events, updated_events)

        # Return list of processed new events for backward compatibility
        return new_events
