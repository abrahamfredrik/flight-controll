import logging
import os
import time
import re
from typing import Optional
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)


def _strip_html(html: str) -> str:
    # naive HTML tag stripper for simple payloads; keep minimal dependencies
    text = re.sub(r"<[^>]+>", "", html)
    return text


class DiscordWebhookSender:
    """Simple Discord webhook sender that implements the same public
    `send_email(recipient, subject, body, html_body=None)` API used by the
    application so it can be injected without wide refactors.

    The constructor accepts the same positional arguments as `MailService` for
    compatibility with the existing factory/injection pattern, but the actual
    webhook URL is read from the `DISCORD_WEBHOOK_URL` environment variable.
    """

    def __init__(
        self,
        smtp_server: Optional[str] = None,
        smtp_port: Optional[int] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        timeout: int = 10,
        max_retries: int = 3,
    ) -> None:
        # Accept SMTP-ish args for compatibility; webhook comes from env
        self.webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
        self.timeout = timeout
        self.max_retries = max_retries
        self.logger = logging.getLogger(__name__)
        # Basic validation: require https and look like a webhook to avoid leaking secrets
        if self.webhook_url:
            if not self.webhook_url.startswith("https://") or "webhook" not in self.webhook_url:
                self.logger.error("Invalid Discord webhook URL configured; ignoring")
                self.webhook_url = None

    def send_email(self, recipient: str, subject: str, body: str, html_body: Optional[str] = None) -> None:
        """Post a markdown-formatted message to the configured Discord webhook.

        Args mirror existing `send_email` so callers don't need to change.
        """
        if not self.webhook_url:
            self.logger.error("Discord webhook URL not configured; skipping notification")
            return

        # Prefer the HTML body if provided, but strip tags — Discord accepts markdown/html poorly
        content_body = html_body if html_body is not None else body
        if html_body is not None:
            try:
                content_body = _strip_html(html_body)
            except Exception:
                content_body = body

        content = f"**{subject}**\n\n{content_body}"

        payload = {"content": content}

        attempt = 0
        last_exc = None
        while attempt < self.max_retries:
            try:
                resp = requests.post(self.webhook_url, json=payload, timeout=self.timeout)
                if resp.status_code in (200, 204):
                    self.logger.info("Discord webhook posted: %s", _mask_url(self.webhook_url))
                    return
                # handle rate limiting or server errors
                if resp.status_code == 429:
                    # Discord may return a retry-after in seconds (header or JSON). Try both.
                    wait = 1.0
                    try:
                        # Try JSON first (some libraries return ms here)
                        retry_after = resp.json().get("retry_after")
                        if retry_after is not None:
                            raf = float(retry_after)
                            # if value seems like milliseconds, convert to seconds
                            wait = raf / 1000.0 if raf > 10 else raf
                        else:
                            # header is usually seconds
                            hdr = resp.headers.get("Retry-After")
                            if hdr:
                                wait = float(hdr)
                    except Exception:
                        try:
                            hdr = resp.headers.get("Retry-After")
                            if hdr:
                                wait = float(hdr)
                        except Exception:
                            wait = 1.0
                    self.logger.warning("Discord rate limited; sleeping %.2fs", wait)
                    time.sleep(wait)
                else:
                    self.logger.error("Discord webhook returned status %s: %s", resp.status_code, resp.text)
                    # no retry on 4xx other than 429; break
                    if 400 <= resp.status_code < 500:
                        return
            except Exception as e:
                last_exc = e
                self.logger.exception("Attempt %d: Failed to post to Discord webhook", attempt + 1)
                time.sleep(1 + attempt)
            attempt += 1

        self.logger.error("All %d attempts failed to post to Discord webhook: %s", self.max_retries, last_exc)


def _mask_url(url: Optional[str]) -> str:
    """Return a masked representation of a webhook URL suitable for logs.

    Shows host and last 6 chars to avoid leaking the full secret.
    """
    if not url:
        return ""
    try:
        p = urlparse(url)
        tail = url[-6:]
        return f"{p.scheme}://{p.netloc}...{tail}"
    except Exception:
        return f"...{url[-6:]}"
