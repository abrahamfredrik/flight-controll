"""HTTP client for remote iCalendar (webcal) feeds."""

from typing import Any, Dict, List

import requests
from .parser import parse_ical_events


class WebcalFetcher:
    """Fetch a remote iCalendar (.ics) feed and parse its events.

    Args:
        webcal_url: the HTTP(S) URL of the calendar feed.
    """

    def __init__(self, webcal_url: str):
        self.webcal_url = webcal_url

    def fetch_events(self) -> List[Dict[str, Any]]:
        """Return a list of event dicts parsed from the remote feed.

        The parser is permissive and returns string values when date parsing
        fails. No timezone conversion is performed by this implementation.
        """
        response = requests.get(self.webcal_url)
        response.raise_for_status()
        return parse_ical_events(response.text)
