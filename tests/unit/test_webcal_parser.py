from datetime import datetime

from flight_controll.webcal.parser import parse_ical_events


def test_parse_ical_events_extracts_fields_and_unescapes_newlines():
    ical_data = """BEGIN:VCALENDAR
BEGIN:VEVENT
UID:event-1@example.com
DTSTART:20251022T100000
DTEND:20251022T110000
SUMMARY:Test Event
LOCATION:Test Location
DESCRIPTION:First line\\nSecond line
END:VEVENT
END:VCALENDAR
"""

    events = parse_ical_events(ical_data)

    assert len(events) == 1
    assert events[0] == {
        "uid": "event-1@example.com",
        "dtstart": datetime(2025, 10, 22, 10, 0),
        "dtend": datetime(2025, 10, 22, 11, 0),
        "summary": "Test Event",
        "location": "Test Location",
        "description": "First line\nSecond line",
    }


def test_parse_ical_events_skips_events_without_uid():
    events = parse_ical_events(
        """BEGIN:VEVENT
DTSTART:20251022T100000
SUMMARY:Missing UID
END:VEVENT"""
    )

    assert events == []


def test_parse_ical_events_returns_none_for_unrecognized_date_format():
    events = parse_ical_events(
        """BEGIN:VEVENT
UID:event-1
DTSTART:invalid-date
DTEND:invalid-date
END:VEVENT"""
    )

    assert events[0]["dtstart"] is None
    assert events[0]["dtend"] is None


def test_parse_ical_events_preserves_unparseable_numeric_date():
    events = parse_ical_events(
        """BEGIN:VEVENT
UID:event-1
DTSTART:20251340T250000
END:VEVENT"""
    )

    assert events[0]["dtstart"] == "20251340T250000"


def test_parse_ical_events_accepts_tzid_and_seconds():
    events = parse_ical_events(
        """BEGIN:VEVENT
UID:event-1
DTSTART;TZID=Europe/Berlin:20260126T101530
DTEND;TZID=Europe/Berlin:20260126T111530
END:VEVENT"""
    )

    assert events[0]["dtstart"] == datetime(2026, 1, 26, 10, 15, 30)
    assert events[0]["dtend"] == datetime(2026, 1, 26, 11, 15, 30)