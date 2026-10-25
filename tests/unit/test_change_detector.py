import pytest
from datetime import datetime, timedelta, timezone

from flight_controll.event.change_detector import (
    normalize_dtstamp,
    event_changed,
    detect_updates,
    detect_removed_events,
)


def test_normalize_dtstamp_removes_dtstamp_lines():
    assert normalize_dtstamp("Some text") == "Some text"
    assert normalize_dtstamp("DTSTAMP:20250101T120000Z\n") == ""
    assert normalize_dtstamp("Prefix\nDTSTAMP:20250101T120000Z\nSuffix") == "Prefix\nSuffix"
    assert normalize_dtstamp("Line1\nDTSTAMP:20250101T120000Z\nLine2") == "Line1\nLine2"
    assert normalize_dtstamp("") == ""
    assert normalize_dtstamp(None) == ""


def test_event_changed_detects_real_change_and_ignores_dtstamp_only():
    old_start = datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc)
    new_start = datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc)

    assert not event_changed(
        old_start,
        old_start,
        new_start,
        new_start,
        "Same description",
        "Same description\nDTSTAMP:20250101T120000Z",
        "Room A",
        "Room A",
    )

    assert event_changed(
        old_start,
        old_start,
        new_start,
        new_start,
        "Old description",
        "New description",
        "Room A",
        "Room A",
    )

    assert event_changed(
        old_start,
        old_start,
        datetime(2025, 1, 1, 11, 0, tzinfo=timezone.utc),
        new_start,
        "Same",
        "Same",
        "Room A",
        "Room A",
    )


def test_detect_updates_returns_persistence_and_notification_data():
    stored_doc = {
        "uid": "u1",
        "summary": "Event",
        "start_time": "2099-01-01T10:00:00",
        "end_time": "2099-01-01T11:00:00",
        "description": "Old desc",
        "location": "Room A",
    }
    events = [
        {
            "uid": "u1",
            "summary": "Event",
            "dtstart": "2099-01-01T10:00:00",
            "dtend": "2099-01-01T11:00:00",
            "description": "New desc",
            "location": "Room A",
        }
    ]

    results = detect_updates(events, [stored_doc])

    assert len(results) == 1
    assert results[0].uid == "u1"
    assert results[0].set_payload["description"] == "New desc"
    assert results[0].notification["old_description"] == "Old desc"
    assert results[0].notification["new_description"] == "New desc"


def test_detect_updates_skips_dtstamp_only_description_change():
    stored_doc = {
        "uid": "u2",
        "summary": "Event",
        "start_time": "2099-01-01T10:00:00",
        "end_time": "2099-01-01T11:00:00",
        "description": "Same description",
        "location": "Room A",
    }
    events = [
        {
            "uid": "u2",
            "summary": "Event",
            "dtstart": "2099-01-01T10:00:00",
            "dtend": "2099-01-01T11:00:00",
            "description": "Same description\nDTSTAMP:20250101T120000Z",
            "location": "Room A",
        }
    ]

    results = detect_updates(events, [stored_doc])

    assert results == []


def test_detect_removed_events_selects_future_documents():
    future_start = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    stored_docs = [
        {
            "uid": "r1",
            "summary": "Removed",
            "start_time": future_start,
            "end_time": "2099-01-01T11:00:00",
        }
    ]
    results = detect_removed_events({"r1"}, set(), stored_docs)

    assert results == stored_docs


def test_detect_removed_events_ignores_past_documents():
    past_start = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    stored_docs = [
        {
            "uid": "r2",
            "summary": "Removed",
            "start_time": past_start,
            "end_time": "2099-01-01T11:00:00",
        }
    ]
    results = detect_removed_events({"r2"}, set(), stored_docs)

    assert results == []
