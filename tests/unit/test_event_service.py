import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta, timezone

from flight_controll.event import event_service as es_module
from flight_controll.event.event_service import EventService


class DummyConfig:
    MONGO_USERNAME = "user"
    MONGO_PASSWORD = "pass"
    MONGO_HOST = "host"
    MONGO_DB = "db"
    MONGO_COLLECTION = "col"
    WEB_CAL_URL = "https://example.com/calendar.ics"
    SMTP_SERVER = "smtp.example.com"
    SMTP_PORT = 587
    SMTP_USERNAME = "u"
    SMTP_PASSWORD = "p"
    RECIPIENT_EMAIL = "r@example.com"


@patch.object(es_module, "MongoClient")
@pytest.mark.parametrize(
    "text, expected",
    [
        ("Some text", "Some text"),
        ("DTSTAMP:20250101T120000Z\n", ""),
        ("Prefix\nDTSTAMP:20250101T120000Z\nSuffix", "Prefix\nSuffix"),
        ("Line1\nDTSTAMP:20250101T120000Z\nLine2", "Line1\nLine2"),
        ("", ""),
        ("   ", ""),
        (None, ""),
    ],
)
def test_normalize_dtstamp(mock_mongo_client, text, expected):
    """Unit tests for normalizeDtstamp: no DTSTAMP, DTSTAMP lines removed, empty, None."""
    config = DummyConfig()
    es = EventService(
        config=config,
        email_sender_cls=MagicMock,
        fetcher_cls=MagicMock,
        events_collection=MagicMock(),
    )
    assert es.normalizeDtstamp(text) == expected


@patch.object(es_module, "MongoClient")
def test_store_events_inserts_only_new(
    mock_mongo_client, fake_collection, fake_sender_cls
):
    config = DummyConfig()

    # Build a fake mongo client that returns a db containing our fixture collection
    mock_db = {config.MONGO_COLLECTION: fake_collection}
    mock_client = MagicMock()
    mock_client.__getitem__.return_value = mock_db
    mock_mongo_client.return_value = mock_client

    es = EventService(
        config=config, email_sender_cls=fake_sender_cls[0], fetcher_cls=MagicMock
    )

    events = [{"uid": "uid-1", "summary": "S", "dtstart": "s", "dtend": "e"}]

    res = es.store_events(events)

    assert res == events
    fake_collection.find_one.assert_called_once_with({"uid": "uid-1"})
    fake_collection.insert_one.assert_called_once()


@patch.object(es_module, "MongoClient")
def test_filter_new_events_filters_existing(mock_mongo_client):
    config = DummyConfig()
    mock_collection = MagicMock()
    # Simulate existing uid in DB
    mock_collection.find.return_value = [{"uid": "existing"}]

    mock_db = {config.MONGO_COLLECTION: mock_collection}
    mock_client = MagicMock()
    mock_client.__getitem__.return_value = mock_db
    mock_mongo_client.return_value = mock_client

    es = EventService(config=config, email_sender_cls=MagicMock, fetcher_cls=MagicMock)

    events = [
        {"uid": "existing", "summary": "old", "dtstart": "s", "dtend": "e"},
        {"uid": "new", "summary": "new", "dtstart": "s2", "dtend": "e2"},
    ]

    out = es.filter_new_events(events)
    assert len(out) == 1
    assert out[0]["uid"] == "new"


@patch.object(es_module, "MongoClient")
def test_fetch_events_filters_privileged_location(mock_mongo_client):
    config = DummyConfig()

    mock_client = MagicMock()
    mock_client.__getitem__.return_value = {config.MONGO_COLLECTION: MagicMock()}
    mock_mongo_client.return_value = mock_client

    # Patch the fetcher class to return some sample events
    fake_events = [
        {
            "uid": "1",
            "summary": "A",
            "dtstart": datetime(2025, 1, 1),
            "dtend": datetime(2025, 1, 1),
            "location": "Privat",
        },
        {
            "uid": "2",
            "summary": "B",
            "dtstart": datetime(2025, 1, 2),
            "dtend": datetime(2025, 1, 2),
            "location": "Public",
        },
    ]

    class FakeFetcher:
        def __init__(self, url):
            pass

        def fetch_events(self):
            return fake_events

    es = EventService(
        config=config, email_sender_cls=MagicMock, fetcher_cls=FakeFetcher
    )

    out = es.fetch_events()
    # event with location 'Privat' (case-insensitive) should be filtered out
    assert len(out) == 1
    assert out[0]["uid"] == "2"


@patch.object(es_module, "MongoClient")
def test_send_events_email_uses_sender(
    mock_mongo_client, fake_collection, fake_sender_cls
):
    config = DummyConfig()
    mock_client = MagicMock()
    mock_client.__getitem__.return_value = {config.MONGO_COLLECTION: fake_collection}
    mock_mongo_client.return_value = mock_client

    es = EventService(
        config=config, email_sender_cls=fake_sender_cls[0], fetcher_cls=MagicMock
    )

    events = [
        {
            "uid": "1",
            "summary": "S1",
            "dtstart": "ds",
            "dtend": "de",
            "description": "d",
            "location": "l",
        }
    ]

    es.send_events_email(events)

    fake_sender_cls[0].assert_called_once_with(
        config.SMTP_SERVER, config.SMTP_PORT, config.SMTP_USERNAME, config.SMTP_PASSWORD
    )
    fake_sender_cls[1].send_email.assert_called_once()


@patch.object(es_module, "MongoClient")
def test_removed_event_behavior(mock_mongo_client, fake_collection, fake_sender_cls):
    """Parametrized test covering future, past and recent (within 10h) removed-event behavior."""
    config = DummyConfig()

    def run_case(start_kind, uid):
        # prepare stored doc depending on case
        if start_kind == "future":
            start_time = "2099-01-01T10:00:00"
        elif start_kind == "past":
            start_time = "2000-01-01T10:00:00"
        else:  # recent
            from datetime import datetime, timedelta, timezone

            start_time = (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat()

        stored_doc = {
            "uid": uid,
            "summary": "Removed",
            "start_time": start_time,
            "end_time": "2099-01-01T11:00:00",
        }

        def find_side(query=None, projection=None):
            if query == {} and projection == {"uid": 1}:
                return [{"uid": "keep"}, {"uid": uid}]
            if isinstance(query, dict) and "uid" in query and "$in" in query["uid"]:
                return [stored_doc]
            return []

        fake_collection.find.side_effect = lambda *args, **kwargs: find_side(
            *args, **kwargs
        )
        fake_collection.delete_many = MagicMock()

        mock_db = {config.MONGO_COLLECTION: fake_collection}
        mock_client = MagicMock()
        mock_client.__getitem__.return_value = mock_db
        mock_mongo_client.return_value = mock_client

        class FakeFetcher:
            def __init__(self, url):
                pass

            def fetch_events(self):
                return [
                    {"uid": "keep", "summary": "Keep", "dtstart": "s1", "dtend": "e1"}
                ]

        es = EventService(
            config=config, email_sender_cls=fake_sender_cls[0], fetcher_cls=FakeFetcher
        )

        out = es.fetch_persist_and_send_events()
        return out

    # future -> removed and emailed
    out = run_case("future", "removed")
    assert out == []
    fake_collection.delete_many.assert_called_once()
    fake_sender_cls[1].send_email.assert_called()

    # past -> not removed, not emailed
    fake_collection.find.side_effect = None
    fake_sender_cls[1].reset_mock()
    fake_collection.delete_many.reset_mock()
    out = run_case("past", "removed")
    assert out == []
    fake_collection.delete_many.assert_not_called()
    fake_sender_cls[1].send_email.assert_not_called()

    # recent (within 10h) -> removed and emailed
    fake_collection.find.side_effect = None
    fake_sender_cls[1].reset_mock()
    fake_collection.delete_many.reset_mock()
    out = run_case("recent", "recent")
    assert out == []
    fake_collection.delete_many.assert_called_once()
    fake_sender_cls[1].send_email.assert_called()


@patch.object(es_module, "MongoClient")
def test_past_removed_event_is_ignored(mock_mongo_client):
    """If a stored event is removed but its start time is in the past, it should not be deleted or emailed about."""
    config = DummyConfig()

    mock_collection = MagicMock()

    # stored event has a past start time
    stored_doc_removed = {
        "uid": "removed",
        "summary": "Removed",
        "start_time": "2000-01-01T10:00:00",
        "end_time": "2000-01-01T11:00:00",
    }

    def find_side(query=None, projection=None):
        if query == {} and projection == {"uid": 1}:
            return [{"uid": "keep"}, {"uid": "removed"}]
        if isinstance(query, dict) and "uid" in query and "$in" in query["uid"]:
            # return stored doc when asked about removed_uids
            return [stored_doc_removed]
        return []

    mock_collection.find.side_effect = lambda *args, **kwargs: find_side(
        *args, **kwargs
    )
    mock_collection.delete_many = MagicMock()

    mock_db = {config.MONGO_COLLECTION: mock_collection}
    mock_client = MagicMock()
    mock_client.__getitem__.return_value = mock_db
    mock_mongo_client.return_value = mock_client

    # Fake fetcher returns only 'keep' event
    class FakeFetcher:
        def __init__(self, url):
            pass

        def fetch_events(self):
            return [{"uid": "keep", "summary": "Keep", "dtstart": "s1", "dtend": "e1"}]

    fake_sender_cls = MagicMock()
    fake_sender_instance = MagicMock()
    fake_sender_cls.return_value = fake_sender_instance

    es = EventService(
        config=config, email_sender_cls=fake_sender_cls, fetcher_cls=FakeFetcher
    )

    out = es.fetch_persist_and_send_events()

    # no new events
    assert out == []

    # verify delete_many was NOT called because stored event is in the past
    mock_collection.delete_many.assert_not_called()

    # verify no email was sent about removals
    fake_sender_instance.send_email.assert_not_called()


@patch.object(es_module, "MongoClient")
def test_recent_removed_event_is_removed(mock_mongo_client):
    """A stored event that started within the last 10 hours should be removed and emailed about."""
    config = DummyConfig()

    mock_collection = MagicMock()

    # stored event started 5 hours ago (within the 10h window)
    recent_start = (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat()
    stored_doc_removed = {
        "uid": "recent",
        "summary": "RecentRemoved",
        "start_time": recent_start,
        "end_time": "2099-01-01T11:00:00",
    }

    def find_side(query=None, projection=None):
        if query == {} and projection == {"uid": 1}:
            return [{"uid": "keep"}, {"uid": "recent"}]
        if isinstance(query, dict) and "uid" in query and "$in" in query["uid"]:
            return [stored_doc_removed]
        return []

    mock_collection.find.side_effect = lambda *args, **kwargs: find_side(
        *args, **kwargs
    )
    mock_collection.delete_many = MagicMock()

    mock_db = {config.MONGO_COLLECTION: mock_collection}
    mock_client = MagicMock()
    mock_client.__getitem__.return_value = mock_db
    mock_mongo_client.return_value = mock_client

    # Fake fetcher returns only 'keep' event
    class FakeFetcher:
        def __init__(self, url):
            pass

        def fetch_events(self):
            return [{"uid": "keep", "summary": "Keep", "dtstart": "s1", "dtend": "e1"}]

    fake_sender_cls = MagicMock()
    fake_sender_instance = MagicMock()
    fake_sender_cls.return_value = fake_sender_instance

    es = EventService(
        config=config, email_sender_cls=fake_sender_cls, fetcher_cls=FakeFetcher
    )

    out = es.fetch_persist_and_send_events()

    # no new events
    assert out == []

    # verify delete_many was called because stored event started within 10h
    mock_collection.delete_many.assert_called_once()

    # verify email was sent about removal
    fake_sender_instance.send_email.assert_called()


@patch.object(es_module, "MongoClient")
@pytest.mark.parametrize(
    "case_name, stored_doc, fetched_event, expected_strings",
    [
        (
            "time_change",
            {
                "uid": "u1",
                "summary": "EventOld",
                "start_time": "2099-01-01T10:00:00",
                "end_time": "2099-01-01T11:00:00",
                "description": "d",
                "location": "L",
            },
            {
                "uid": "u1",
                "summary": "EventOld",
                "dtstart": "2099-01-02T10:00:00",
                "dtend": "2099-01-02T11:00:00",
                "description": "d",
                "location": "L",
            },
            ["Old Start", "New Start"],
        ),
        (
            "description_change",
            {
                "uid": "u2",
                "summary": "Event",
                "start_time": "2099-01-01T10:00:00",
                "end_time": "2099-01-01T11:00:00",
                "description": "old-desc",
                "location": "L",
            },
            {
                "uid": "u2",
                "summary": "Event",
                "dtstart": "2099-01-01T10:00:00",
                "dtend": "2099-01-01T11:00:00",
                "description": "new-desc",
                "location": "L",
            },
            ["Old Description", "New Description"],
        ),
        (
            "location_change",
            {
                "uid": "u3",
                "summary": "Event",
                "start_time": "2099-01-01T10:00:00",
                "end_time": "2099-01-01T11:00:00",
                "description": "d",
                "location": "OldLoc",
            },
            {
                "uid": "u3",
                "summary": "Event",
                "dtstart": "2099-01-01T10:00:00",
                "dtend": "2099-01-01T11:00:00",
                "description": "d",
                "location": "NewLoc",
            },
            ["Old Location", "New Location"],
        ),
        (
            "description_change_with_dtstamp",
            {
                "uid": "u4",
                "summary": "Event",
                "start_time": "2099-01-01T10:00:00",
                "end_time": "2099-01-01T11:00:00",
                "description": "Old text",
                "location": "L",
            },
            {
                "uid": "u4",
                "summary": "Event",
                "dtstart": "2099-01-01T10:00:00",
                "dtend": "2099-01-01T11:00:00",
                "description": "New text\nDTSTAMP:20250101T120000Z",
                "location": "L",
            },
            ["Old Description", "New Description"],
        ),
    ],
)
def test_detect_and_apply_updates_param(
    mock_mongo_client, case_name, stored_doc, fetched_event, expected_strings
):
    """Parametrized test for update detection: time, description, and location changes."""
    config = DummyConfig()

    mock_collection = MagicMock()

    uid = stored_doc["uid"]

    def find_side(query=None, projection=None):
        if isinstance(query, dict) and "uid" in query and "$in" in query["uid"]:
            return [stored_doc]
        if query == {} and projection == {"uid": 1}:
            return [{"uid": uid}]
        return []

    mock_collection.find.side_effect = lambda *args, **kwargs: find_side(
        *args, **kwargs
    )
    mock_collection.update_one = MagicMock()

    mock_db = {config.MONGO_COLLECTION: mock_collection}
    mock_client = MagicMock()
    mock_client.__getitem__.return_value = mock_db
    mock_mongo_client.return_value = mock_client

    class FakeFetcher:
        def __init__(self, url):
            pass

        def fetch_events(self):
            return [fetched_event]

    fake_sender_cls = MagicMock()
    fake_sender_instance = MagicMock()
    fake_sender_cls.return_value = fake_sender_instance

    es = EventService(
        config=config, email_sender_cls=fake_sender_cls, fetcher_cls=FakeFetcher
    )

    out = es.fetch_persist_and_send_events()

    assert out == []
    mock_collection.update_one.assert_called_once()
    fake_sender_instance.send_email.assert_called_once()
    sent = fake_sender_instance.send_email.call_args[0][2]
    assert "Updated Events" in sent
    for s in expected_strings:
        assert s in sent


@patch.object(es_module, "MongoClient")
def test_description_only_dtstamp_difference_not_considered_update(mock_mongo_client):
    """When description differs only by a DTSTAMP line, no update is performed."""
    config = DummyConfig()

    stored_doc = {
        "uid": "u-dtstamp",
        "summary": "Event",
        "start_time": "2099-01-01T10:00:00",
        "end_time": "2099-01-01T11:00:00",
        "description": "Summary of event",
        "location": "L",
    }
    fetched_event = {
        "uid": "u-dtstamp",
        "summary": "Event",
        "dtstart": "2099-01-01T10:00:00",
        "dtend": "2099-01-01T11:00:00",
        "description": "Summary of event\nDTSTAMP:20250101T120000Z",
        "location": "L",
    }

    mock_collection = MagicMock()

    def find_side(query=None, projection=None):
        if isinstance(query, dict) and "uid" in query and "$in" in query["uid"]:
            return [stored_doc]
        if query == {} and projection == {"uid": 1}:
            return [{"uid": "u-dtstamp"}]
        return []

    mock_collection.find.side_effect = lambda *args, **kwargs: find_side(
        *args, **kwargs
    )
    mock_collection.update_one = MagicMock()

    mock_db = {config.MONGO_COLLECTION: mock_collection}
    mock_client = MagicMock()
    mock_client.__getitem__.return_value = mock_db
    mock_mongo_client.return_value = mock_client

    class FakeFetcher:
        def __init__(self, url):
            pass

        def fetch_events(self):
            return [fetched_event]

    fake_sender_cls = MagicMock()
    fake_sender_instance = MagicMock()
    fake_sender_cls.return_value = fake_sender_instance

    es = EventService(
        config=config, email_sender_cls=fake_sender_cls, fetcher_cls=FakeFetcher
    )

    es.fetch_persist_and_send_events()

    mock_collection.update_one.assert_not_called()
