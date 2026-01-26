import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

from app.webcal.fetcher import WebcalFetcher


MOCK_ICAL_DATA = """BEGIN:VCALENDAR
BEGIN:VEVENT
UID:event-1@example.com
DTSTART:20251022T100000
DTEND:20251022T110000
SUMMARY:Test Event 1
LOCATION:Test Location
DESCRIPTION:This is a test event\\nMore details here
END:VEVENT
BEGIN:VEVENT
UID:event-2@example.com
DTSTART:20251023T150000
DTEND:20251023T160000
SUMMARY:Test Event 2
LOCATION:Another Location
DESCRIPTION:Second test event\\nLine two
END:VEVENT
END:VCALENDAR
"""


@patch("app.webcal.fetcher.requests.get")
def test_fetch_events_parses_correctly(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = MOCK_ICAL_DATA
    mock_get.return_value = mock_response

    fetcher = WebcalFetcher("https://example.com/calendar.ics")
    events = fetcher.fetch_events()

    assert len(events) == 2
    assert events[0]["uid"] == "event-1@example.com"
    assert events[0]["summary"] == "Test Event 1"
    assert events[0]["location"] == "Test Location"
    assert events[0]["description"] == "This is a test event\nMore details here"
    assert events[0]["dtstart"] == datetime(2025, 10, 22, 10, 0)
    assert events[0]["dtend"] == datetime(2025, 10, 22, 11, 0)


@patch("app.webcal.fetcher.requests.get")
def test_fetch_events_skips_event_without_uid(mock_get):
    ical_data = """BEGIN:VCALENDAR
BEGIN:VEVENT
DTSTART:20251022T100000
DTEND:20251022T110000
SUMMARY:Missing UID Event
END:VEVENT
END:VCALENDAR"""

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = ical_data
    mock_get.return_value = mock_response

    fetcher = WebcalFetcher("https://example.com/calendar.ics")
    events = fetcher.fetch_events()

    assert len(events) == 0


@patch("app.webcal.fetcher.requests.get")
def test_fetch_events_handles_malformed_dates(mock_get):
    ical_data = """BEGIN:VCALENDAR
BEGIN:VEVENT
UID:event-3@example.com
DTSTART:invalid-date
DTEND:invalid-date
SUMMARY:Malformed Dates
END:VEVENT
END:VCALENDAR"""

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = ical_data
    mock_get.return_value = mock_response

    fetcher = WebcalFetcher("https://example.com/calendar.ics")
    events = fetcher.fetch_events()

    assert len(events) == 1
    assert events[0]["uid"] == "event-3@example.com"
    assert events[0]["dtstart"] == None
    assert events[0]["dtend"] == None


@patch("app.webcal.fetcher.requests.get")
def test_fetch_events_raises_for_bad_http(mock_get):
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = Exception("404 Not Found")
    mock_get.return_value = mock_response

    fetcher = WebcalFetcher("https://example.com/calendar.ics")

    with pytest.raises(Exception, match="404 Not Found"):
        fetcher.fetch_events()


@patch("app.webcal.fetcher.requests.get")
def test_fetch_events_parses_seconds_and_tzid(mock_get):
    ical_data = """BEGIN:VCALENDAR
BEGIN:VEVENT
UID:event-4@example.com
DTSTART;TZID=Europe/Berlin:20260126T101530
DTEND;TZID=Europe/Berlin:20260126T111530
SUMMARY:With Seconds and TZID
LOCATION:Berlin
END:VEVENT
END:VCALENDAR"""

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = ical_data
    mock_get.return_value = mock_response

    fetcher = WebcalFetcher("https://example.com/calendar.ics")
    events = fetcher.fetch_events()

    assert len(events) == 1
    assert events[0]["uid"] == "event-4@example.com"
    # seconds-aware parsing should produce datetime objects
    from datetime import datetime

    assert events[0]["dtstart"] == datetime(2026, 1, 26, 10, 15, 30)
    assert events[0]["dtend"] == datetime(2026, 1, 26, 11, 15, 30)
