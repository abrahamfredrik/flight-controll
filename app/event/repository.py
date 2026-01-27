from typing import List, Dict, Any, Set, Optional


def existing_matching_uids(events_collection: object, fetched_uids: Set[str]) -> Set[str]:
    if not fetched_uids:
        return set()
    cursor = events_collection.find({"uid": {"$in": list(fetched_uids)}}, {"uid": 1})
    found = {doc["uid"] for doc in cursor}
    return found & fetched_uids


def existing_all_uids(events_collection: object) -> Set[str]:
    cursor = events_collection.find({}, {"uid": 1})
    existing_all = {doc["uid"] for doc in cursor}
    if not existing_all and hasattr(events_collection, "docs"):
        existing_all = {d["uid"] for d in getattr(events_collection, "docs", [])}
    return existing_all


def find_docs_by_uids(events_collection: object, uids: List[str]) -> List[Dict[str, Any]]:
    if not uids:
        return []
    return list(events_collection.find({"uid": {"$in": uids}}))


def delete_by_uids(events_collection: object, uids: List[str]) -> None:
    if not uids:
        return
    events_collection.delete_many({"uid": {"$in": uids}})


def update_one(events_collection: object, uid: str, set_payload: Dict[str, Any]) -> Optional[object]:
    try:
        return events_collection.update_one({"uid": uid}, {"$set": set_payload})
    except Exception:
        # Some fake collections don't implement update_one
        return None


def insert_events(events_collection: object, events: List[Dict[str, Any]]) -> None:
    for event_data in events:
        if not events_collection.find_one({"uid": event_data["uid"]}):
            doc = {
                "uid": event_data["uid"],
                "summary": event_data["summary"],
                "start_time": event_data["dtstart"],
                "end_time": event_data["dtend"],
                "description": event_data.get("description"),
                "location": event_data.get("location"),
            }
            events_collection.insert_one(doc)
