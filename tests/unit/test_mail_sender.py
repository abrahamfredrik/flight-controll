import pytest
from unittest.mock import patch, MagicMock
from app.mail.sender import EmailSender

@pytest.fixture
def email_sender():
    return EmailSender(
        smtp_server="smtp.example.com",
        smtp_port=587,
        username="user@example.com",
        password="securepassword"
    )

@patch("app.mail.sender.smtplib.SMTP")
def test_send_email_success(mock_smtp, email_sender):
    mock_server = MagicMock()
    mock_smtp.return_value.__enter__.return_value = mock_server

    email_sender.send_email("recipient@example.com", "Test Subject", "Test Body")

    mock_smtp.assert_called_once_with("smtp.example.com", 587)
    mock_server.starttls.assert_called_once()
    mock_server.login.assert_called_once_with("user@example.com", "securepassword")
    mock_server.send_message.assert_called_once()
    # You can further check the message contents if needed

@patch("app.mail.sender.smtplib.SMTP")
def test_send_email_failure(mock_smtp, email_sender, capsys):
    mock_smtp.side_effect = Exception("SMTP connection failed")

    email_sender.send_email("recipient@example.com", "Test Subject", "Test Body")

    captured = capsys.readouterr()
    assert "Failed to send email: SMTP connection failed" in captured.out
