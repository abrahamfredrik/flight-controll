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
