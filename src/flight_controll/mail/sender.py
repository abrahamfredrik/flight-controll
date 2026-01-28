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

    def send_email(self, recipient: str, subject: str, body: str) -> None:
        msg = MIMEMultipart()
        msg['From'] = self.username
        msg['To'] = recipient
        msg['Subject'] = subject

        msg.attach(MIMEText(body, 'plain'))

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
            print(f"Email sent to {recipient}")
        except Exception:
            import sys
            e = sys.exc_info()[1]
            logger.exception("Failed to send email to %s", recipient)
            # keep previous behaviour of printing the error for backwards compatibility
            try:
                print(f"Failed to send email: {e}")
            except Exception:
                pass
