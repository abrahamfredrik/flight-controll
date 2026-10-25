"""Pure parsing helpers for iCalendar feeds."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Union


def _parse_datetime(value: Optional[str]) -> Optional[Union[datetime, str]]:
    if value is None:
        return None
    for date_format in ("%Y%m%dT%H%M%S", "%Y%m%dT%H%M"):
        try:
            return datetime.strptime(value, date_format)
        except ValueError:
            continue
    return value


def parse_ical_events(ical_data: str) -> List[Dict[str, Any]]:
    """Extract supported VEVENT fields from iCalendar text.

    Events without a UID are ignored. Unrecognized date values are preserved
    as strings when they match the supported date-field pattern.
    """
    events: List[Dict[str, Any]] = []
    vevents = re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", ical_data, re.DOTALL)

    for vevent in vevents:
        uid = re.search(r"UID:(.+)", vevent)
        dtstart = re.search(r"DTSTART(?:;TZID=[^:]+)?:([0-9T]+)", vevent)
        dtend = re.search(r"DTEND(?:;TZID=[^:]+)?:([0-9T]+)", vevent)
        summary = re.search(r"SUMMARY:(.+)", vevent)
        location = re.search(r"LOCATION:(.+)", vevent)
        description = re.search(r"DESCRIPTION:(.+)", vevent, re.DOTALL)

        event = {
            "uid": uid.group(1).strip() if uid else None,
            "dtstart": _parse_datetime(dtstart.group(1).strip()) if dtstart else None,
            "dtend": _parse_datetime(dtend.group(1).strip()) if dtend else None,
            "summary": summary.group(1).strip() if summary else None,
            "location": location.group(1).strip() if location else None,
            "description": (
                description.group(1).strip().replace("\\n", "\n")
                if description
                else None
            ),
        }
        if event["uid"]:
            events.append(event)

    return events
