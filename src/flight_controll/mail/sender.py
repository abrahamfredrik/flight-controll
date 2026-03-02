import logging
import smtplib
from typing import Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)


class EmailSender:
    """Sends email via SMTP. Accepts an optional `smtp_class` parameter for easier
    testing/mock injection (defaults to `smtplib.SMTP`). Uses logging instead of
    printing to stdout.
    """

    def __init__(
        self,
        smtp_server: str,
        smtp_port: int,
        username: str,
        password: str,
        smtp_class: Optional[type] = None,
    ):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        # do not bind to smtplib.SMTP at construction time so tests that patch
        # `flight_controll.mail.sender.smtplib.SMTP` before calling `send_email` continue to work
        self.smtp_class = smtp_class

    def send_email(
        self,
        recipient: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
    ) -> None:
        msg = MIMEMultipart()
        msg["From"] = self.username
        msg["To"] = recipient
        msg["Subject"] = subject

        if html_body is None:
            msg.attach(MIMEText(body, "plain"))
        else:
            alternative = MIMEMultipart("alternative")
            alternative.attach(MIMEText(body, "plain"))
            alternative.attach(MIMEText(html_body, "html"))
            msg.attach(alternative)

        try:
            smtp_cls = self.smtp_class or smtplib.SMTP
            with smtp_cls(self.smtp_server, self.smtp_port) as server:
                # only call starttls/login if provided by the smtp client
                if hasattr(server, "starttls"):
                    server.starttls()
                if hasattr(server, "login"):
                    server.login(self.username, self.password)
                server.send_message(msg)
            logger.info("Email sent to %s", recipient)
        except Exception as e:
            logger.exception("Failed to send email to %s: %s", recipient, e)


class MailService:
    """Higher-level mail service that wraps `EmailSender` with retries and timeout.

    Maintains the same constructor signature as `EmailSender` for backward
    compatibility so it can be passed as `email_sender_cls` to services and
    blueprints. It attempts a small number of retries and logs failures.
    """

    def __init__(
        self,
        smtp_server: str,
        smtp_port: int,
        username: str,
        password: str,
        smtp_class: Optional[type] = None,
        timeout: int = 10,
        max_retries: int = 3,
    ):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.smtp_class = smtp_class
        self.timeout = timeout
        self.max_retries = max_retries
        self.logger = logging.getLogger(__name__)

    def send_email(
        self,
        recipient: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
    ) -> None:
        """Send an email with retry/backoff. Raises nothing; exceptions are logged.

        Args:
            recipient: recipient email address
            subject: email subject
            body: plain-text body
            html_body: optional HTML body
        """
        attempt = 0
        last_exc = None
        while attempt < self.max_retries:
            try:
                smtp_cls = self.smtp_class or smtplib.SMTP
                # pass timeout to SMTP constructor where supported
                with smtp_cls(self.smtp_server, self.smtp_port, self.timeout) as server:
                    if hasattr(server, "starttls"):
                        server.starttls()
                    if hasattr(server, "login"):
                        server.login(self.username, self.password)
                    msg = MIMEMultipart()
                    msg["From"] = self.username
                    msg["To"] = recipient
                    msg["Subject"] = subject
                    if html_body is None:
                        msg.attach(MIMEText(body, "plain"))
                    else:
                        alternative = MIMEMultipart("alternative")
                        alternative.attach(MIMEText(body, "plain"))
                        alternative.attach(MIMEText(html_body, "html"))
                        msg.attach(alternative)
                    server.send_message(msg)
                self.logger.info("Email sent to %s", recipient)
                return
            except Exception as e:
                last_exc = e
                self.logger.exception(
                    "Attempt %d: Failed to send email to %s: %s", attempt + 1, recipient, e
                )
                attempt += 1
        # all attempts failed
        self.logger.error("All %d attempts failed to send email to %s: %s", self.max_retries, recipient, last_exc)
