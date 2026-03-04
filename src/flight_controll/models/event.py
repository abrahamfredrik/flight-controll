from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class Event:
    """Domain model for a calendar event.

    This is a lightweight dataclass used for internal typing and conversion.
    Public APIs in the project still accept and return dicts for compatibility
    with existing tests and lightweight fake collections.
    """

    uid: str
    summary: Optional[str] = None
    dtstart: Optional[str] = None
    dtend: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "uid": self.uid,
            "summary": self.summary,
            "dtstart": self.dtstart,
            "dtend": self.dtend,
            "description": self.description,
            "location": self.location,
        }
