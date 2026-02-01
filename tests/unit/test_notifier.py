from unittest.mock import MagicMock

from flight_controll.event import notifier


class DummyConfig:
    SMTP_SERVER = "smtp.example.com"
    SMTP_PORT = 25
    SMTP_USERNAME = "u"
    SMTP_PASSWORD = "p"
    RECIPIENT_EMAIL = "r@example.com"


def test_send_summary_no_changes():
    fake_sender = MagicMock()
    notifier.send_summary(fake_sender, DummyConfig, [], [], [])
    # nothing should be sent
    fake_sender.assert_not_called()


def test_send_summary_with_all_sections():
    fake_sender = MagicMock()
    added = [{"uid": "a1", "summary": "A", "dtstart": "s", "dtend": "e"}]
    removed = [{"uid": "r1", "summary": "R", "start_time": "s2", "end_time": "e2"}]
    updated = [
        {
            "uid": "u1",
            "summary": "U",
            "old_start": "o",
            "old_end": "oe",
            "new_start": "n",
            "new_end": "ne",
        }
    ]

    notifier.send_summary(fake_sender, DummyConfig, added, removed, updated)

    fake_sender.assert_called_once()
    # args: (recipient, subject, body) when send_email is called on the instance
    # but send_summary constructs an EmailSender instance and then calls send_email,
    # our fake_sender receives that instance and should have send_email called.
    # We instead verify by wrapping fake_sender as a class that returns instance with send_email.


def test_send_summary_integration_style():
    sent = []

    class FakeSenderCls:
        def __init__(self, server, port, user, pw):
            pass

        def send_email(self, recipient, subject, body, html_body=None):
            sent.append({
                "recipient": recipient,
                "subject": subject,
                "body": body,
                "html_body": html_body,
            })

    added = [{"uid": "a1", "summary": "A", "dtstart": "s", "dtend": "e"}]
    removed = [{"uid": "r1", "summary": "R", "start_time": "s2", "end_time": "e2"}]
    updated = [
        {
            "uid": "u1",
            "summary": "U",
            "old_start": "o",
            "old_end": "oe",
            "new_start": "n",
            "new_end": "ne",
        }
    ]

    notifier.send_summary(FakeSenderCls, DummyConfig, added, removed, updated)

    assert len(sent) == 1
    assert sent[0]["html_body"] is not None
    assert "Updated Events" in sent[0]["html_body"]


def test_send_summary_updated_section_bolds_changed_fields():
    """When an updated event has old_start != new_start, HTML body wraps both in <strong>."""
    sent = []

    class FakeSenderCls:
        def __init__(self, server, port, user, pw):
            pass

        def send_email(self, recipient, subject, body, html_body=None):
            sent.append({"body": body, "html_body": html_body})

    added = []
    removed = []
    # old_start != new_start -> both should be bold; old_end == new_end -> not bold
    updated = [
        {
            "uid": "u1",
            "summary": "Meeting",
            "old_start": "2025-01-01T10:00",
            "new_start": "2025-01-01T11:00",
            "old_end": "2025-01-01T11:00",
            "new_end": "2025-01-01T11:00",
            "old_description": "Same",
            "new_description": "Same",
            "old_location": "Room A",
            "new_location": "Room B",
        }
    ]

    notifier.send_summary(FakeSenderCls, DummyConfig, added, removed, updated)

    assert len(sent) == 1
    html = sent[0]["html_body"]
    # Changed fields: start (old != new), location (old != new) -> bold
    assert "<strong>2025-01-01T10:00</strong>" in html
    assert "<strong>2025-01-01T11:00</strong>" in html
    assert "<strong>Room A</strong>" in html
    assert "<strong>Room B</strong>" in html
    # Unchanged description "Same" should not be wrapped in strong
    assert "Old Description: Same\n" in html
    assert "New Description: Same\n" in html
