import html as html_module
from typing import Any, Dict, List, Tuple


_SECTION_SEPARATOR = "--------------------------\n"


def _escape(value: Any) -> str:
    """Escape a value for HTML and normalize None to an empty string."""
    if value is None:
        return ""
    return html_module.escape(str(value))


def _format_event_value(event: Dict[str, Any], primary: str, fallback: str = None) -> str:
    value = event.get(primary)
    if value is None and fallback is not None:
        value = event.get(fallback)
    return str(value) if value is not None else "N/A"


def _render_plain_line(label: str, value: Any) -> str:
    return f"{label}: {value}\n"


def _render_html_line(label: str, value: Any) -> str:
    return f"{label}: {_escape(value)}\n"


def _render_raw_html_line(label: str, value: Any) -> str:
    return f"{label}: {value}\n"


def _render_event_block(event: Dict[str, Any], field_map: List[Tuple[str, str, str]]) -> Tuple[str, str]:
    """Render a single event block for plain text and HTML."""
    plain_lines: List[str] = []
    html_lines: List[str] = []
    for label, primary_key, fallback_key in field_map:
        value = _format_event_value(event, primary_key, fallback_key)
        plain_lines.append(_render_plain_line(label, value))
        html_lines.append(_render_html_line(label, value))
    plain_lines.append(_SECTION_SEPARATOR)
    html_lines.append(_SECTION_SEPARATOR)
    return "".join(plain_lines), "".join(html_lines)


def _render_updated_field(
    updated: Dict[str, Any], label: str, old_key: str, new_key: str, fallback_key: str = None
) -> Tuple[str, str, str, str]:
    """Render an updated field pair with optional <strong> wrapping in HTML."""
    old_value = _format_event_value(updated, old_key, fallback_key)
    new_value = _format_event_value(updated, new_key, fallback_key)
    changed = old_value != new_value
    old_html_value = f"<strong>{_escape(old_value)}</strong>" if changed else _escape(old_value)
    new_html_value = f"<strong>{_escape(new_value)}</strong>" if changed else _escape(new_value)
    return (
        _render_plain_line(f"Old {label}", old_value),
        _render_plain_line(f"New {label}", new_value),
        _render_raw_html_line(f"Old {label}", old_html_value),
        _render_raw_html_line(f"New {label}", new_html_value),
    )


def _render_updated_event(updated: Dict[str, Any]) -> Tuple[str, str]:
    plain_lines: List[str] = []
    html_lines: List[str] = []
    summary = _format_event_value(updated, "summary")
    plain_lines.append(_render_plain_line("Summary", summary))
    html_lines.append(_render_html_line("Summary", summary))

    old_start_plain, new_start_plain, old_start_html, new_start_html = _render_updated_field(
        updated, "Start", "old_start", "new_start"
    )
    old_end_plain, new_end_plain, old_end_html, new_end_html = _render_updated_field(
        updated, "End", "old_end", "new_end"
    )
    old_desc_plain, new_desc_plain, old_desc_html, new_desc_html = _render_updated_field(
        updated, "Description", "old_description", "new_description", "description"
    )
    old_loc_plain, new_loc_plain, old_loc_html, new_loc_html = _render_updated_field(
        updated, "Location", "old_location", "new_location", "location"
    )

    plain_lines.extend([
        old_start_plain,
        old_end_plain,
        old_desc_plain,
        old_loc_plain,
        new_start_plain,
        new_end_plain,
        new_desc_plain,
        new_loc_plain,
    ])
    html_lines.extend([
        old_start_html,
        old_end_html,
        old_desc_html,
        old_loc_html,
        new_start_html,
        new_end_html,
        new_desc_html,
        new_loc_html,
    ])

    plain_lines.append(_SECTION_SEPARATOR)
    html_lines.append(_SECTION_SEPARATOR)
    return "".join(plain_lines), "".join(html_lines)


def send_summary(
    email_sender_cls,
    config,
    added: List[Dict[str, Any]],
    removed: List[Dict[str, Any]],
    updated: List[Dict[str, Any]],
):
    """Send one summary email for added, removed, and updated events."""
    if not added and not removed and not updated:
        return

    email_sender = email_sender_cls(
        config.SMTP_SERVER, config.SMTP_PORT, config.SMTP_USERNAME, config.SMTP_PASSWORD
    )
    subject = f"Events update: {len(added)} added, {len(removed)} removed, {len(updated)} updated"
    body = ["Events Update:\n\n"]
    body_html = ["<html><body><pre style='font-family: sans-serif;'>Events Update:\n\n"]

    added_fields = [
        ("Summary", "summary", None),
        ("Start Time", "dtstart", "start_time"),
        ("End Time", "dtend", "end_time"),
        ("Description", "description", None),
        ("Location", "location", None),
    ]
    removed_fields = [
        ("Summary", "summary", None),
        ("Start Time", "start_time", None),
        ("End Time", "end_time", None),
        ("Description", "description", None),
        ("Location", "location", None),
    ]

    if added:
        body.append("Added Events:\n\n")
        body_html.append("Added Events:\n\n")
        for event in added:
            text_block, html_block = _render_event_block(event, added_fields)
            body.append(text_block)
            body_html.append(html_block)

    if removed:
        body.append("Removed Events:\n\n")
        body_html.append("Removed Events:\n\n")
        for event in removed:
            text_block, html_block = _render_event_block(event, removed_fields)
            body.append(text_block)
            body_html.append(html_block)

    if updated:
        body.append("Updated Events:\n\n")
        body_html.append("Updated Events:\n\n")
        for event in updated:
            text_block, html_block = _render_updated_event(event)
            body.append(text_block)
            body_html.append(html_block)

    body_html.append("</pre></body></html>")
    email_sender.send_email(
        config.RECIPIENT_EMAIL, subject, "".join(body), html_body="".join(body_html)
    )
