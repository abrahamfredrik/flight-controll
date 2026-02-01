import pytest
from unittest.mock import patch, MagicMock
from flight_controll.mail.sender import EmailSender


@pytest.fixture
def email_sender():
    return EmailSender(
        smtp_server="smtp.example.com",
        smtp_port=587,
        username="user@example.com",
        password="securepassword",
    )


@patch("flight_controll.mail.sender.smtplib.SMTP")
def test_send_email_success(mock_smtp, email_sender):
    mock_server = MagicMock()
    mock_smtp.return_value.__enter__.return_value = mock_server

    email_sender.send_email("recipient@example.com", "Test Subject", "Test Body")

    mock_smtp.assert_called_once_with("smtp.example.com", 587)
    mock_server.starttls.assert_called_once()
    mock_server.login.assert_called_once_with("user@example.com", "securepassword")
    mock_server.send_message.assert_called_once()
    # You can further check the message contents if needed


@patch("flight_controll.mail.sender.smtplib.SMTP")
def test_send_email_with_html_body(mock_smtp, email_sender):
    """When html_body is provided, the message has multipart/alternative with plain and HTML parts."""
    mock_server = MagicMock()
    mock_smtp.return_value.__enter__.return_value = mock_server

    email_sender.send_email(
        "recipient@example.com",
        "Test Subject",
        "Plain body",
        html_body="<html><body><p>HTML body</p></body></html>",
    )

    mock_smtp.assert_called_once()
    mock_server.send_message.assert_called_once()
    msg = mock_server.send_message.call_args[0][0]
    # Message has multipart/alternative: plain first, then HTML
    plain_parts = [p for p in msg.walk() if p.get_content_type() == "text/plain"]
    html_parts = [p for p in msg.walk() if p.get_content_type() == "text/html"]
    assert len(plain_parts) == 1
    assert len(html_parts) == 1
    assert plain_parts[0].get_payload() == "Plain body"
    assert "<p>HTML body</p>" in html_parts[0].get_payload()


@patch("flight_controll.mail.sender.smtplib.SMTP")
def test_send_email_failure(mock_smtp, email_sender, caplog):
    mock_smtp.side_effect = Exception("SMTP connection failed")

    email_sender.send_email("recipient@example.com", "Test Subject", "Test Body")

    assert "Failed to send email" in caplog.text
    assert "SMTP connection failed" in caplog.text
