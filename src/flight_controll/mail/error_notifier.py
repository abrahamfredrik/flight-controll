from __future__ import annotations

import os
from typing import Optional

from .discord_sender import DiscordWebhookSender


def notify_discord_error(
    error: object, config: Optional[object] = None
) -> None:
    """Send an application error description to the configured Discord webhook.

    Args:
        error: Exception or error description to report.
        config: Optional application configuration used for webhook and secrets.
    """
    description = str(error).strip() if error is not None else ""
    if not description:
        description = "An error occurred."

    webhook_url = getattr(config, "DISCORD_WEBHOOK_URL", None)
    secrets = [os.environ.get("DISCORD_WEBHOOK_URL", ""), webhook_url or ""]
    for name in ("MONGO_PASSWORD", "SMTP_PASSWORD"):
        secrets.append(getattr(config, name, None) or os.environ.get(name, ""))
    for secret in secrets:
        if secret:
            description = description.replace(secret, "[REDACTED]")

    sender = DiscordWebhookSender(webhook_url=webhook_url)
    sender.send_email("", "Application error", description)