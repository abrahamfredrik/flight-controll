import pytest

from app.event.event_service import EventService


class FakeCollection:
    def __init__(self):
        self.docs = []

    def find_one(self, query):
        for d in self.docs:
            if d.get("uid") == query.get("uid"):
                return d
        return None

    def insert_one(self, doc):
        # mimic pymongo InsertOneResult by returning a simple dict
        self.docs.append(doc.copy())

    def find(self, query, projection=None):
        uids = query.get("uid", {}).get("$in", [])
        return [{"uid": d["uid"]} for d in self.docs if d["uid"] in uids]


class FakeFetcher:
    def __init__(self, url):
        self.url = url

    def fetch_events(self):
        return [
            {
                "uid": "uid-123",
                "summary": "Test Event",
                "dtstart": "2026-01-26T10:00:00",
                "dtend": "2026-01-26T11:00:00",
                "description": "Desc",
                "location": "Location A",
            }
        ]


class MultiEventFetcher(FakeFetcher):
    def fetch_events(self):
        return [
            {
                "uid": "uid-1",
                "summary": "Event One",
                "dtstart": "2026-01-26T08:00:00",
                "dtend": "2026-01-26T09:00:00",
                "description": "First",
                "location": "Location X",
            },
            {
                "uid": "uid-2",
                "summary": "Event Two",
                "dtstart": "2026-01-26T09:00:00",
                "dtend": "2026-01-26T10:00:00",
                "description": "Second",
                "location": "Location Y",
            },
            {
                "uid": "uid-3",
                "summary": "Event Three",
                "dtstart": "2026-01-26T11:00:00",
                "dtend": "2026-01-26T12:00:00",
                "description": "Third",
                "location": "Location Z",
            },
        ]


class FakeEmailSender:
    sent = []

    def __init__(self, smtp_server, smtp_port, username, password):
        pass

    def send_email(self, recipient, subject, body):
        self.sent.append({"recipient": recipient, "subject": subject, "body": body})


def test_scheduler_flow_sends_email_for_new_event(app):
    """Integration-style test: run the scheduler flow (via EventService) end-to-end.

    It uses lightweight fakes for the fetcher, mail sender and the events collection
    so the test does not require network or a real MongoDB instance.
    """

    # create EventService instance without calling its real __init__ (avoid real MongoClient)
    es = object.__new__(EventService)
    es.logger = None
    es.config = app.app_config
    # provide WEB_CAL_URL expected by EventService.fetch_events
    es.config.WEB_CAL_URL = "http://test.local/calendar.ics"
    es.email_sender_cls = FakeEmailSender
    es.fetcher_cls = FakeFetcher
    es.events_collection = FakeCollection()

    # Ensure no previous sent emails
    FakeEmailSender.sent.clear()

    events = es.fetch_persist_and_send_events()

    assert len(events) == 1
    # event should have been persisted to our fake collection
    assert len(es.events_collection.docs) == 1
    # email should have been sent
    assert FakeEmailSender.sent, "expected an email to be sent"
    sent = FakeEmailSender.sent[0]
    assert sent["recipient"] == app.app_config.RECIPIENT_EMAIL
    assert "Test Event" in sent["body"]


def test_scheduler_no_email_for_existing_event(app):
    """If the event already exists in the DB, no email is sent."""

    es = object.__new__(EventService)
    es.logger = None
    es.config = app.app_config
    # provide WEB_CAL_URL expected by EventService.fetch_events
    es.config.WEB_CAL_URL = "http://test.local/calendar.ics"
    es.email_sender_cls = FakeEmailSender
    es.fetcher_cls = FakeFetcher

    # prepare fake collection with existing event
    fc = FakeCollection()
    fc.insert_one({
        "uid": "uid-123",
        "summary": "Test Event",
        "start_time": "2026-01-26T10:00:00",
        "end_time": "2026-01-26T11:00:00",
        "description": "Desc",
        "location": "Location A",
    })
    es.events_collection = fc

    FakeEmailSender.sent.clear()

    events = es.fetch_persist_and_send_events()

    # no new events should be returned or stored
    assert len(events) == 0
    assert len(es.events_collection.docs) == 1
    # and no email should be sent
    assert not FakeEmailSender.sent


def test_scheduler_multiple_events_single_email(app):
    """When multiple new events are found, only a single email is sent containing all events."""

    es = object.__new__(EventService)
    es.logger = None
    es.config = app.app_config
    es.config.WEB_CAL_URL = "http://test.local/calendar.ics"
    es.email_sender_cls = FakeEmailSender
    # use fetcher that returns several events
    es.fetcher_cls = MultiEventFetcher

    es.events_collection = FakeCollection()

    FakeEmailSender.sent.clear()

    events = es.fetch_persist_and_send_events()

    # all events should be returned and stored
    assert len(events) == 3
    assert len(es.events_collection.docs) == 3

    # only one email should have been sent
    assert len(FakeEmailSender.sent) == 1
    sent = FakeEmailSender.sent[0]
    assert sent["recipient"] == app.app_config.RECIPIENT_EMAIL
    # ensure body contains every event summary
    assert "Event One" in sent["body"]
    assert "Event Two" in sent["body"]
    assert "Event Three" in sent["body"]
