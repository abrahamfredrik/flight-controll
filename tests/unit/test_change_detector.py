import pytest
from unittest.mock import MagicMock
from datetime import datetime, timedelta, timezone

from flight_controll.event.change_detector import (
    normalize_dtstamp,
    event_changed,
    detect_and_apply_updates,
    fetch_removed_events,
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


def test_detect_and_apply_updates_updates_changed_event_and_returns_payload():
    repo = MagicMock()
    stored_doc = {
        "uid": "u1",
        "summary": "Event",
        "start_time": "2099-01-01T10:00:00",
        "end_time": "2099-01-01T11:00:00",
        "description": "Old desc",
        "location": "Room A",
    }
    repo.find_docs_by_uids.return_value = [stored_doc]
    repo.update_one = MagicMock()

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

    results = detect_and_apply_updates(events, {"u1"}, repo)

    assert len(results) == 1
    assert repo.update_one.called
    assert results[0]["uid"] == "u1"
    assert results[0]["old_description"] == "Old desc"
    assert results[0]["new_description"] == "New desc"


def test_detect_and_apply_updates_skips_dtstamp_only_description_change():
    repo = MagicMock()
    stored_doc = {
        "uid": "u2",
        "summary": "Event",
        "start_time": "2099-01-01T10:00:00",
        "end_time": "2099-01-01T11:00:00",
        "description": "Same description",
        "location": "Room A",
    }
    repo.find_docs_by_uids.return_value = [stored_doc]
    repo.update_one = MagicMock()

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

    results = detect_and_apply_updates(events, {"u2"}, repo)

    assert results == []
    repo.update_one.assert_not_called()


def test_fetch_removed_events_deletes_future_documents_and_returns_them():
    repo = MagicMock()
    future_start = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    stored_docs = [
        {
            "uid": "r1",
            "summary": "Removed",
            "start_time": future_start,
            "end_time": "2099-01-01T11:00:00",
        }
    ]
    repo.find_docs_by_uids.return_value = stored_docs
    repo.delete_by_uids = MagicMock()

    results = fetch_removed_events({"r1"}, set(), repo)

    assert results == stored_docs
    repo.delete_by_uids.assert_called_once_with(["r1"])


def test_fetch_removed_events_ignores_past_documents():
    repo = MagicMock()
    past_start = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    stored_docs = [
        {
            "uid": "r2",
            "summary": "Removed",
            "start_time": past_start,
            "end_time": "2099-01-01T11:00:00",
        }
    ]
    repo.find_docs_by_uids.return_value = stored_docs
    repo.delete_by_uids = MagicMock()

    results = fetch_removed_events({"r2"}, set(), repo)

    assert results == []
    repo.delete_by_uids.assert_not_called()
