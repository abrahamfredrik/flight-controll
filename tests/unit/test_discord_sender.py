import os
from types import SimpleNamespace

import pytest


def test_no_webhook_config_logs_and_skips(caplog):
    # Ensure environment has no webhook configured
    os.environ.pop("DISCORD_WEBHOOK_URL", None)
    from flight_controll.mail.discord_sender import DiscordWebhookSender

    sender = DiscordWebhookSender()
    with caplog.at_level("ERROR"):
        sender.send_email("recipient", "subj", "body")
    assert "Discord webhook URL not configured" in caplog.text


def test_successful_post(monkeypatch):
    os.environ["DISCORD_WEBHOOK_URL"] = "https://discord.test/webhook"
    posts = []

    def fake_post(url, json, timeout):
        posts.append((url, json, timeout))
        # emulate Discord returning 204 for success
        r = SimpleNamespace()
        r.status_code = 204
        r.text = ""
        return r

    monkeypatch.setattr("flight_controll.mail.discord_sender.requests.post", fake_post)
    from flight_controll.mail.discord_sender import DiscordWebhookSender

    sender = DiscordWebhookSender(timeout=5, max_retries=1)
    sender.send_email("recipient", "Subj", "Plain body")

    assert len(posts) == 1
    url, payload, timeout = posts[0]
    assert url == os.environ["DISCORD_WEBHOOK_URL"]
    assert "Subj" in payload["content"]
    assert "Plain body" in payload["content"]
    assert timeout == 5
