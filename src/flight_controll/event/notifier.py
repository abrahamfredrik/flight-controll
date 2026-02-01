from typing import List, Dict, Any


def send_summary(
    email_sender_cls,
    config,
    added: List[Dict[str, Any]],
    removed: List[Dict[str, Any]],
    updated: List[Dict[str, Any]],
):
    """Send one summary email for added, removed, and updated events. Builds the sender from config internally."""
    if not added and not removed and not updated:
        return

    email_sender = email_sender_cls(
        config.SMTP_SERVER, config.SMTP_PORT, config.SMTP_USERNAME, config.SMTP_PASSWORD
    )
    subject = f"Events update: {len(added)} added, {len(removed)} removed, {len(updated)} updated"
    body = "Events Update:\n\n"

    if added:
        body += "Added Events:\n\n"
        for event in added:
            body += (
                f"Summary: {event.get('summary', 'N/A')}\n"
                f"Start Time: {event.get('dtstart', event.get('start_time', 'N/A'))}\n"
                f"End Time: {event.get('dtend', event.get('end_time', 'N/A'))}\n"
                f"Description: {event.get('description', 'N/A')}\n"
                f"Location: {event.get('location', 'N/A')}\n"
                "--------------------------\n"
            )

    if removed:
        body += "Removed Events:\n\n"
        for event in removed:
            body += (
                f"Summary: {event.get('summary', 'N/A')}\n"
                f"Start Time: {event.get('start_time', 'N/A')}\n"
                f"End Time: {event.get('end_time', 'N/A')}\n"
                f"Description: {event.get('description', 'N/A')}\n"
                f"Location: {event.get('location', 'N/A')}\n"
                "--------------------------\n"
            )

    if updated:
        body += "Updated Events:\n\n"
        for u in updated:
            body += (
                f"Summary: {u.get('summary', 'N/A')}\n"
                f"Old Start: {u.get('old_start', 'N/A')}\n"
                f"Old End: {u.get('old_end', 'N/A')}\n"
                f"Old Description: {u.get('old_description', u.get('description', 'N/A'))}\n"
                f"Old Location: {u.get('old_location', u.get('location', 'N/A'))}\n"
                f"New Start: {u.get('new_start', 'N/A')}\n"
                f"New End: {u.get('new_end', 'N/A')}\n"
                f"New Description: {u.get('new_description', u.get('description', 'N/A'))}\n"
                f"New Location: {u.get('new_location', u.get('location', 'N/A'))}\n"
                "--------------------------\n"
            )

    email_sender.send_email(config.RECIPIENT_EMAIL, subject, body)
