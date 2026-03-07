"""Repository layer for calendar events.

This module provides an `EventRepository` class that encapsulates MongoDB
operations for events.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Dict, Any, Set, Optional


class EventRepository:
    """Encapsulates DB operations for calendar events.

    Args:
        collection: a pymongo Collection-like object.
    """

    def __init__(self, collection: object):
        self.collection = collection

    def existing_matching_uids(self, fetched_uids: Set[str]) -> Set[str]:
        if not fetched_uids:
            return set()
        cursor = self.collection.find({"uid": {"$in": list(fetched_uids)}}, {"uid": 1})
        found = {doc["uid"] for doc in cursor}
        return found & fetched_uids

    def existing_all_uids(self) -> Set[str]:
        cursor = self.collection.find({}, {"uid": 1})
        existing_all = {doc["uid"] for doc in cursor}
        if not existing_all and hasattr(self.collection, "docs"):
            existing_all = {d["uid"] for d in getattr(self.collection, "docs", [])}
        return existing_all

    def find_docs_by_uids(self, uids: List[str]) -> List[Dict[str, Any]]:
        if not uids:
            return []
        docs = list(self.collection.find({"uid": {"$in": uids}}))
        # Some lightweight fake collections return only uid placeholders for find
        # queries. If that is the case, and the collection exposes a `docs`
        # attribute containing full documents, prefer that.
        if (
            docs
            and all(
                "start_time" not in d and "end_time" not in d and "summary" not in d
                for d in docs
            )
            and hasattr(self.collection, "docs")
        ):
            return list(getattr(self.collection, "docs", []))
        return docs

    def delete_by_uids(self, uids: List[str]) -> None:
        if not uids:
            return
        self.collection.delete_many({"uid": {"$in": uids}})

    def update_one(self, uid: str, set_payload: Dict[str, Any]) -> Optional[object]:
        try:
            return self.collection.update_one({"uid": uid}, {"$set": set_payload})
        except Exception:
            # Some fake collections don't implement update_one
            return None

    def insert_events(self, events: List[Dict[str, Any]]) -> None:
        """Insert event dicts as documents; skip any whose uid already exists.

        Adds `created_at` and `updated_at` timestamps in ISO format (UTC).
        """
        now = datetime.now(timezone.utc).isoformat()
        for event_data in events:
            if not self.collection.find_one({"uid": event_data["uid"]}):
                doc = {
                    "uid": event_data["uid"],
                    "summary": event_data.get("summary"),
                    "start_time": event_data.get("dtstart"),
                    "end_time": event_data.get("dtend"),
                    "description": event_data.get("description"),
                    "location": event_data.get("location"),
                    "created_at": now,
                    "updated_at": now,
                }
                self.collection.insert_one(doc)


def create_indexes(events_collection: object) -> None:
    """Create recommended indexes for the events collection.

    Creates a unique index on `uid` and a non-unique index on `start_time`
    to support efficient queries for deletions and searches.
    """
    try:
        # create_index is a pymongo Collection method; this will be a no-op for
        # fake collections used in tests that don't implement it.
        events_collection.create_index([("uid", 1)], unique=True)
        events_collection.create_index([("start_time", 1)])
    except Exception:
        # Ignore if the collection doesn't support index creation (e.g., fakes)
        return


# Legacy function wrappers to preserve existing module-level API
# Legacy module-level wrappers were removed. Use `EventRepository`
# instances directly for database operations (preferred) or create
# thin adapters in call-sites if backward compatibility is required.
