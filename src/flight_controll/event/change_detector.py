from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

from . import utils


@dataclass(frozen=True)
class EventUpdate:
    """A detected change, separated into persistence and notification data."""

    uid: str
    set_payload: Dict[str, Any]
    notification: Dict[str, Any]


def normalize_dtstamp(text: Optional[str]) -> str:
    """Normalize an event description by removing DTSTAMP lines."""
    if text is None:
        return ""
    new_text = re.sub(r"DTSTAMP:[^\n]*\n?", "", text)
    return new_text.strip()


def event_changed(
    old_start: Optional[Any],
    old_end: Optional[Any],
    new_start: Optional[Any],
    new_end: Optional[Any],
    old_desc: Optional[str],
    new_desc: Optional[str],
    old_loc: Optional[str],
    new_loc: Optional[str],
) -> bool:
    if (old_start is None) != (new_start is None):
        return True
    if old_start is not None and new_start is not None and old_start != new_start:
        return True
    if (old_end is None) != (new_end is None):
        return True
    if old_end is not None and new_end is not None and old_end != new_end:
        return True
    if normalize_dtstamp(old_desc) != normalize_dtstamp(new_desc):
        return True
    if (old_loc or "") != (new_loc or ""):
        return True
    return False


def detect_updates(
    events: List[Dict[str, Any]], stored_events: List[Dict[str, Any]]
) -> List[EventUpdate]:
    """Compare fetched events with stored events without changing persistence."""
    stored_by_uid = {doc["uid"]: doc for doc in stored_events}
    updates: List[EventUpdate] = []

    for ev in events:
        uid = ev.get("uid")
        if uid not in stored_by_uid:
            continue
        stored = stored_by_uid[uid]

        old_start = utils.parse_dt(stored.get("start_time") or stored.get("dtstart"))
        old_end = utils.parse_dt(stored.get("end_time") or stored.get("dtend"))
        new_start = utils.parse_dt(ev.get("dtstart") or ev.get("start_time"))
        new_end = utils.parse_dt(ev.get("dtend") or ev.get("end_time"))
        old_desc = stored.get("description")
        new_desc = ev.get("description")
        old_loc = stored.get("location")
        new_loc = ev.get("location")

        if not event_changed(
            old_start,
            old_end,
            new_start,
            new_end,
            old_desc,
            new_desc,
            old_loc,
            new_loc,
        ):
            continue

        set_payload: Dict[str, Any] = {}
        if new_start is not None:
            set_payload["start_time"] = new_start.isoformat()
        if new_end is not None:
            set_payload["end_time"] = new_end.isoformat()
        for k in ("summary", "description", "location"):
            if k in ev:
                set_payload[k] = ev[k]

        updates.append(
            EventUpdate(
                uid=uid,
                set_payload=set_payload,
                notification={
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
                },
            )
        )

    return updates


def detect_removed_events(
    existing_all: Set[str],
    fetched_uids: Set[str],
    stored_events: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Select recently relevant removed events without changing persistence."""
    removed_uid_set = existing_all - fetched_uids
    if not removed_uid_set:
        return []

    future_docs: List[Dict[str, Any]] = []
    for doc in stored_events:
        if doc.get("uid") not in removed_uid_set:
            continue
        st = utils.parse_dt(doc.get("start_time") or doc.get("dtstart"))
        if st is not None and utils.is_within_removal_window(st):
            future_docs.append(doc)

    return future_docs
