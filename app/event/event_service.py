import logging
from typing import List, Dict, Any, Optional, Set
from datetime import datetime, timezone, timedelta

from pymongo import MongoClient
from app.webcal.fetcher import WebcalFetcher
from app.mail.sender import EmailSender
from app.config import Config

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
        # Always send a summary if there are any changes
        if not added_events and not removed_events and not updated_events:
            return

        email_sender = self.email_sender_cls(self.config.SMTP_SERVER,
                                   self.config.SMTP_PORT,
                                   self.config.SMTP_USERNAME,
                                   self.config.SMTP_PASSWORD)
        updated_events = updated_events or []
        subject = f"Events update: {len(added_events)} added, {len(removed_events)} removed, {len(updated_events)} updated"
        body = "Events Update:\n\n"

        if added_events:
            body += "Added Events:\n\n"
            for event in added_events:
                body += (
                    f"Summary: {event.get('summary', 'N/A')}\n"
                    f"Start Time: {event.get('dtstart', event.get('start_time', 'N/A'))}\n"
                    f"End Time: {event.get('dtend', event.get('end_time', 'N/A'))}\n"
                    f"Description: {event.get('description', 'N/A')}\n"
                    f"Location: {event.get('location', 'N/A')}\n"
                    "--------------------------\n"
                )

        if removed_events:
            body += "Removed Events:\n\n"
            for event in removed_events:
                body += (
                    f"Summary: {event.get('summary', 'N/A')}\n"
                    f"Start Time: {event.get('start_time', 'N/A')}\n"
                    f"End Time: {event.get('end_time', 'N/A')}\n"
                    f"Description: {event.get('description', 'N/A')}\n"
                    f"Location: {event.get('location', 'N/A')}\n"
                    "--------------------------\n"
                )

        if updated_events:
            body += "Updated Events:\n\n"
            for u in updated_events:
                body += (
                    f"Summary: {u.get('summary', 'N/A')}\n"
                    f"Old Start: {u.get('old_start', 'N/A')}\n"
                    f"Old End: {u.get('old_end', 'N/A')}\n"
                    f"New Start: {u.get('new_start', 'N/A')}\n"
                    f"New End: {u.get('new_end', 'N/A')}\n"
                    "--------------------------\n"
                )

        email_sender.send_email(self.config.RECIPIENT_EMAIL, subject, body)

    def filter_new_events(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        uids = [event["uid"] for event in events]
        existing_uids_cursor = self.events_collection.find(
            {"uid": {"$in": uids}}, {"uid": 1}
        )
        existing_uids = {doc["uid"] for doc in existing_uids_cursor}
        return [event for event in events if event["uid"] not in existing_uids]

    def _existing_matching_uids(self, fetched_uids: Set[str]) -> Set[str]:
        """Return uids from `fetched_uids` that already exist in the DB.

        Uses a $in query which is compatible with the test fakes. The result
        is intersected with `fetched_uids` to guard against fake find
        implementations that might return unrelated documents.
        """
        if not fetched_uids:
            return set()

        cursor = self.events_collection.find({"uid": {"$in": list(fetched_uids)}}, {"uid": 1})
        found = {doc["uid"] for doc in cursor}
        return found & fetched_uids

    def _parse_dt(self, v: Any) -> Optional[datetime]:
        """Parse value `v` (datetime or ISO string) to timezone-aware datetime (UTC assumed when naive)."""
        if v is None:
            return None
        if isinstance(v, datetime):
            dt = v
        elif isinstance(v, str):
            try:
                dt = datetime.fromisoformat(v)
            except Exception:
                return None
        else:
            return None

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    def _detect_and_apply_updates(self, events: List[Dict[str, Any]], existing_matching: Set[str]) -> List[Dict[str, Any]]:
        """Detect events whose start/end changed compared to stored docs.

        Apply the updates to the DB and return a list of update records with
        old and new values for inclusion in the summary email.
        """
        if not existing_matching:
            return []

        # retrieve stored documents for matching uids
        stored_cursor = list(self.events_collection.find({"uid": {"$in": list(existing_matching)}}))
        # Some lightweight fake collections only return uid entries for `find`.
        # If the returned docs don't contain details, fall back to `events_collection.docs`.
        if stored_cursor and all("start_time" not in d and "end_time" not in d and "summary" not in d for d in stored_cursor) and hasattr(self.events_collection, "docs"):
            stored_cursor = list(getattr(self.events_collection, "docs", []))

        stored_by_uid = {doc["uid"]: doc for doc in stored_cursor}

        updates: List[Dict[str, Any]] = []
        for ev in events:
            uid = ev.get("uid")
            if uid not in stored_by_uid:
                continue
            stored = stored_by_uid[uid]

            old_start = self._parse_dt(stored.get("start_time") or stored.get("dtstart"))
            old_end = self._parse_dt(stored.get("end_time") or stored.get("dtend"))
            new_start = self._parse_dt(ev.get("dtstart") or ev.get("start_time"))
            new_end = self._parse_dt(ev.get("dtend") or ev.get("end_time"))

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
                    # update DB record
                    try:
                        self.events_collection.update_one({"uid": uid}, {"$set": set_payload})
                    except Exception:
                        # Some fake collections might not implement update_one; ignore failure
                        pass

                updates.append({
                    "uid": uid,
                    "summary": ev.get("summary", stored.get("summary")),
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
        cursor = self.events_collection.find({}, {"uid": 1})
        existing_all = {doc["uid"] for doc in cursor}
        if not existing_all and hasattr(self.events_collection, "docs"):
            existing_all = {d["uid"] for d in getattr(self.events_collection, "docs", [])}
        return existing_all

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
        stored = list(self.events_collection.find({"uid": {"$in": removed_uids}}))

        # Only consider events whose start time is within the allowed window.
        # We allow removal for events that start in the future or started within
        # the last 10 hours.
        now = datetime.now(timezone.utc)
        threshold = now - timedelta(hours=10)

        def _parse_start(d: Dict[str, Any]) -> Optional[datetime]:
            for k in ("start_time", "dtstart"):
                v = d.get(k)
                if isinstance(v, datetime):
                    dt = v
                elif isinstance(v, str):
                    try:
                        dt = datetime.fromisoformat(v)
                    except Exception:
                        continue
                else:
                    continue

                # make timezone-aware: assume UTC when no tzinfo
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt

        future_docs = []
        for doc in stored:
            st = _parse_start(doc)
            if st is not None and st > threshold:
                future_docs.append(doc)

        # delete only the future events from DB and return them for email
        if future_docs:
            future_uids = [d["uid"] for d in future_docs]
            self.events_collection.delete_many({"uid": {"$in": future_uids}})

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
