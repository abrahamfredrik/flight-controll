import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta, timezone

from app.event import event_service as es_module
from app.event.event_service import EventService


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


@patch.object(es_module, 'MongoClient')
def test_store_events_inserts_only_new(mock_mongo_client):
    config = DummyConfig()

    mock_collection = MagicMock()
    # find_one returns None for new event
    mock_collection.find_one.return_value = None

    # Build a fake mongo client that returns a db containing our collection
    mock_db = {config.MONGO_COLLECTION: mock_collection}
    mock_client = MagicMock()
    mock_client.__getitem__.return_value = mock_db
    mock_mongo_client.return_value = mock_client

    es = EventService(config=config, email_sender_cls=MagicMock, fetcher_cls=MagicMock)

    events = [
        {"uid": "uid-1", "summary": "S", "dtstart": "s", "dtend": "e"}
    ]

    res = es.store_events(events)

    assert res == events
    mock_collection.find_one.assert_called_once_with({"uid": "uid-1"})
    mock_collection.insert_one.assert_called_once()


@patch.object(es_module, 'MongoClient')
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
        {"uid": "new", "summary": "new", "dtstart": "s2", "dtend": "e2"}
    ]

    out = es.filter_new_events(events)
    assert len(out) == 1
    assert out[0]["uid"] == "new"


@patch.object(es_module, 'MongoClient')
def test_fetch_events_filters_privileged_location(mock_mongo_client):
    config = DummyConfig()

    mock_client = MagicMock()
    mock_client.__getitem__.return_value = {config.MONGO_COLLECTION: MagicMock()}
    mock_mongo_client.return_value = mock_client

    # Patch the fetcher class to return some sample events
    fake_events = [
        {"uid": "1", "summary": "A", "dtstart": datetime(2025,1,1), "dtend": datetime(2025,1,1), "location": "Privat"},
        {"uid": "2", "summary": "B", "dtstart": datetime(2025,1,2), "dtend": datetime(2025,1,2), "location": "Public"}
    ]

    class FakeFetcher:
        def __init__(self, url):
            pass

        def fetch_events(self):
            return fake_events

    es = EventService(config=config, email_sender_cls=MagicMock, fetcher_cls=FakeFetcher)

    out = es.fetch_events()
    # event with location 'Privat' (case-insensitive) should be filtered out
    assert len(out) == 1
    assert out[0]["uid"] == "2"


@patch.object(es_module, 'MongoClient')
def test_send_events_email_uses_sender(mock_mongo_client):
    config = DummyConfig()
    mock_client = MagicMock()
    mock_client.__getitem__.return_value = {config.MONGO_COLLECTION: MagicMock()}
    mock_mongo_client.return_value = mock_client

    fake_sender_cls = MagicMock()
    fake_sender_instance = MagicMock()
    fake_sender_cls.return_value = fake_sender_instance

    es = EventService(config=config, email_sender_cls=fake_sender_cls, fetcher_cls=MagicMock)

    events = [
        {"uid": "1", "summary": "S1", "dtstart": "ds", "dtend": "de", "description": "d", "location": "l"}
    ]

    es.send_events_email(events)

    fake_sender_cls.assert_called_once_with(config.SMTP_SERVER, config.SMTP_PORT, config.SMTP_USERNAME, config.SMTP_PASSWORD)
    fake_sender_instance.send_email.assert_called_once()


@patch.object(es_module, 'MongoClient')
def test_detect_and_remove_deleted_events(mock_mongo_client):
    config = DummyConfig()

    mock_collection = MagicMock()

    # existing uids in DB: 'keep' and 'removed'
    # ensure removed event has a future start time so it is eligible for removal
    stored_doc_removed = {"uid": "removed", "summary": "Removed", "start_time": "2099-01-01T10:00:00", "end_time": "2099-01-01T11:00:00"}

    def find_side(query=None, projection=None):
        # first call: find({}, {"uid":1}) -> return both uids
        if query == {} and projection == {"uid": 1}:
            return [{"uid": "keep"}, {"uid": "removed"}]
        # second call: find({"uid": {"$in": removed_uids}}) -> return stored doc(s)
        if isinstance(query, dict) and "uid" in query and "$in" in query["uid"]:
            return [stored_doc_removed]
        return []

    mock_collection.find.side_effect = lambda *args, **kwargs: find_side(*args, **kwargs)
    mock_collection.delete_many = MagicMock()

    mock_db = {config.MONGO_COLLECTION: mock_collection}
    mock_client = MagicMock()
    mock_client.__getitem__.return_value = mock_db
    mock_mongo_client.return_value = mock_client

    # Fake fetcher returns only 'keep' event (so 'removed' is missing)
    class FakeFetcher:
        def __init__(self, url):
            pass

        def fetch_events(self):
            return [{"uid": "keep", "summary": "Keep", "dtstart": "s1", "dtend": "e1"}]

    fake_sender_cls = MagicMock()
    fake_sender_instance = MagicMock()
    fake_sender_cls.return_value = fake_sender_instance

    es = EventService(config=config, email_sender_cls=fake_sender_cls, fetcher_cls=FakeFetcher)

    out = es.fetch_persist_and_send_events()

    # no new events in this scenario
    assert out == []

    # verify delete was called for the removed uid
    mock_collection.delete_many.assert_called_once_with({"uid": {"$in": ["removed"]}})

    # verify removal email was sent
    fake_sender_instance.send_email.assert_called_once()


@patch.object(es_module, 'MongoClient')
def test_past_removed_event_is_ignored(mock_mongo_client):
    """If a stored event is removed but its start time is in the past, it should not be deleted or emailed about."""
    config = DummyConfig()

    mock_collection = MagicMock()

    # stored event has a past start time
    stored_doc_removed = {"uid": "removed", "summary": "Removed", "start_time": "2000-01-01T10:00:00", "end_time": "2000-01-01T11:00:00"}

    def find_side(query=None, projection=None):
        if query == {} and projection == {"uid": 1}:
            return [{"uid": "keep"}, {"uid": "removed"}]
        if isinstance(query, dict) and "uid" in query and "$in" in query["uid"]:
            # return stored doc when asked about removed_uids
            return [stored_doc_removed]
        return []

    mock_collection.find.side_effect = lambda *args, **kwargs: find_side(*args, **kwargs)
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

    es = EventService(config=config, email_sender_cls=fake_sender_cls, fetcher_cls=FakeFetcher)

    out = es.fetch_persist_and_send_events()

    # no new events
    assert out == []

    # verify delete_many was NOT called because stored event is in the past
    mock_collection.delete_many.assert_not_called()

    # verify no email was sent about removals
    fake_sender_instance.send_email.assert_not_called()


@patch.object(es_module, 'MongoClient')
def test_recent_removed_event_is_removed(mock_mongo_client):
    """A stored event that started within the last 10 hours should be removed and emailed about."""
    config = DummyConfig()

    mock_collection = MagicMock()

    # stored event started 5 hours ago (within the 10h window)
    recent_start = (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat()
    stored_doc_removed = {"uid": "recent", "summary": "RecentRemoved", "start_time": recent_start, "end_time": "2099-01-01T11:00:00"}

    def find_side(query=None, projection=None):
        if query == {} and projection == {"uid": 1}:
            return [{"uid": "keep"}, {"uid": "recent"}]
        if isinstance(query, dict) and "uid" in query and "$in" in query["uid"]:
            return [stored_doc_removed]
        return []

    mock_collection.find.side_effect = lambda *args, **kwargs: find_side(*args, **kwargs)
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

    es = EventService(config=config, email_sender_cls=fake_sender_cls, fetcher_cls=FakeFetcher)

    out = es.fetch_persist_and_send_events()

    # no new events
    assert out == []

    # verify delete_many was called because stored event started within 10h
    mock_collection.delete_many.assert_called_once()

    # verify email was sent about removal
    fake_sender_instance.send_email.assert_called()
