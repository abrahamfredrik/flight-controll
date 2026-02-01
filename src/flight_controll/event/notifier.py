import html as html_module
from typing import List, Dict, Any


def _escape(s: Any) -> str:
    """Escape for HTML; None and non-strings become empty string."""
    if s is None:
        return ""
    return html_module.escape(str(s))


def _format_updated_field(u: Dict[str, Any], old_key: str, new_key: str) -> tuple:
    """Return (old_display, new_display) with <strong> when values differ."""
    old_val = u.get(old_key) or ""
    new_val = u.get(new_key) or ""
    old_str = str(old_val) if old_val else "N/A"
    new_str = str(new_val) if new_val else "N/A"
    changed = old_val != new_val
    if changed:
        return (
            f"<strong>{_escape(old_str)}</strong>",
            f"<strong>{_escape(new_str)}</strong>",
        )
    return (_escape(old_str), _escape(new_str))


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
    body_html_parts = ["<html><body><pre style='font-family: sans-serif;'>Events Update:\n\n"]

    if added:
        body += "Added Events:\n\n"
        body_html_parts.append("Added Events:\n\n")
        for event in added:
            s = event.get("summary", "N/A")
            st = event.get("dtstart", event.get("start_time", "N/A"))
            e = event.get("dtend", event.get("end_time", "N/A"))
            d = event.get("description", "N/A")
            loc = event.get("location", "N/A")
            body += (
                f"Summary: {s}\n"
                f"Start Time: {st}\n"
                f"End Time: {e}\n"
                f"Description: {d}\n"
                f"Location: {loc}\n"
                "--------------------------\n"
            )
            body_html_parts.append(
                f"Summary: {_escape(s)}\n"
                f"Start Time: {_escape(st)}\n"
                f"End Time: {_escape(e)}\n"
                f"Description: {_escape(d)}\n"
                f"Location: {_escape(loc)}\n"
                "--------------------------\n"
            )

    if removed:
        body += "Removed Events:\n\n"
        body_html_parts.append("Removed Events:\n\n")
        for event in removed:
            s = event.get("summary", "N/A")
            st = event.get("start_time", "N/A")
            e = event.get("end_time", "N/A")
            d = event.get("description", "N/A")
            loc = event.get("location", "N/A")
            body += (
                f"Summary: {s}\n"
                f"Start Time: {st}\n"
                f"End Time: {e}\n"
                f"Description: {d}\n"
                f"Location: {loc}\n"
                "--------------------------\n"
            )
            body_html_parts.append(
                f"Summary: {_escape(s)}\n"
                f"Start Time: {_escape(st)}\n"
                f"End Time: {_escape(e)}\n"
                f"Description: {_escape(d)}\n"
                f"Location: {_escape(loc)}\n"
                "--------------------------\n"
            )

    if updated:
        body += "Updated Events:\n\n"
        body_html_parts.append("Updated Events:\n\n")
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
            old_start_d, new_start_d = _format_updated_field(u, "old_start", "new_start")
            old_end_d, new_end_d = _format_updated_field(u, "old_end", "new_end")
            old_desc_d, new_desc_d = _format_updated_field(
                u, "old_description", "new_description"
            )
            old_loc_d, new_loc_d = _format_updated_field(
                u, "old_location", "new_location"
            )
            summary_esc = _escape(u.get("summary", "N/A"))
            body_html_parts.append(
                f"Summary: {summary_esc}\n"
                f"Old Start: {old_start_d}\n"
                f"Old End: {old_end_d}\n"
                f"Old Description: {old_desc_d}\n"
                f"Old Location: {old_loc_d}\n"
                f"New Start: {new_start_d}\n"
                f"New End: {new_end_d}\n"
                f"New Description: {new_desc_d}\n"
                f"New Location: {new_loc_d}\n"
                "--------------------------\n"
            )

    body_html_parts.append("</pre></body></html>")
    body_html = "".join(body_html_parts)

    email_sender.send_email(
        config.RECIPIENT_EMAIL, subject, body, html_body=body_html
    )
