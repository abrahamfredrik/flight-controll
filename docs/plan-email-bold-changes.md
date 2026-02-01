# Plan: Mark changed fields in summary emails (bold)

## Goal

When the summary email lists **Updated Events**, any field where the old value differs from the new value should be visually emphasized (e.g. **bold**) for both the old and new value, so readers can quickly see what changed.

## Current behaviour

- **Where emails are built**: [src/flight_controll/event/notifier.py](src/flight_controll/event/notifier.py) builds a single plain-text `body` and calls `email_sender.send_email(recipient, subject, body)`.
- **Sender**: [src/flight_controll/mail/sender.py](src/flight_controll/mail/sender.py) sends one MIME part: `MIMEText(body, "plain")`.
- **Updated section**: For each updated event, the notifier outputs lines like `Old Start: ...`, `New Start: ...`, `Old Description: ...`, etc. There is no indication of which of these actually changed.

Plain text cannot represent bold, so we need an HTML part for the summary email when we want to emphasize changed fields.

---

## 1. Support optional HTML body in EmailSender

**File**: [src/flight_controll/mail/sender.py](src/flight_controll/mail/sender.py)

- Change signature to: `send_email(self, recipient: str, subject: str, body: str, html_body: Optional[str] = None)`.
- If `html_body` is `None`: keep current behaviour (attach a single `MIMEText(body, "plain")` to the existing `MIMEMultipart()`).
- If `html_body` is provided:
  - Create an inner `MIMEMultipart("alternative")`.
  - Attach `MIMEText(body, "plain")` first, then `MIMEText(html_body, "html")`.
  - Attach this alternative container to the root message (so clients that support HTML show the HTML part; others show plain).
- No change to other callers: `event_service.send_events_email` continues to call `send_email(recipient, subject, body)` without `html_body`.

**Reference**: RFC 2046 / common practice — attach plain first, then HTML, inside a multipart/alternative.

---

## 2. Build HTML summary in notifier and mark changed fields

**File**: [src/flight_controll/event/notifier.py](src/flight_controll/event/notifier.py)

- Keep building the existing plain `body` unchanged (used as fallback and for the first part of the alternative).
- Build a second string `body_html` with the same structure but using HTML:
  - Use a simple HTML skeleton (e.g. `<html><body><pre>...</pre></body></html>` or `<p>`/`<br>`) so the layout is readable.
  - **Escape all user-supplied content** (summary, description, location, date strings) before inserting into HTML to avoid broken layout or XSS — use `html.escape(s)` (or a small helper that handles `None`).
- **Updated Events section only**: For each update record `u`, for each field pair (old_start vs new_start, old_end vs new_end, old_description vs new_description, old_location vs new_location):
  - Normalize for comparison (e.g. treat `None` and `""` as equal).
  - If old and new differ, wrap **both** the old value and the new value in `<strong>...</strong>` in the HTML body (so both are bold). If they are equal, output them without bold.
- Call `email_sender.send_email(config.RECIPIENT_EMAIL, subject, body, html_body=body_html)`.

**Field pairs** (keys in the update dict from [event_service.py](src/flight_controll/event/event_service.py)):

- Start: `old_start`, `new_start`
- End: `old_end`, `new_end`
- Description: `old_description`, `new_description`
- Location: `old_location`, `new_location`

**Comparison**: Treat missing key or `None` as empty string for comparison so "N/A" vs empty are consistent. Use something like `(u.get('old_start') or '') != (u.get('new_start') or '')` (and same for description/location; dates are already strings from the service).

---

## 3. Tests

- **Mail sender** ([tests/unit/test_mail_sender.py](tests/unit/test_mail_sender.py)): Add a test that when `send_email(..., html_body=some_html)` is called, the message has two parts in an alternative multipart (plain and HTML). No change to existing tests that call `send_email` with two or three args.
- **Notifier** ([tests/unit/test_notifier.py](tests/unit/test_notifier.py)): The fake sender currently records `send_email(recipient, subject, body)`. Update the fake to accept and store an optional `html_body` (e.g. keyword-only). Add a test that when `updated` contains one event where e.g. `old_start != new_start`, the generated `html_body` contains `<strong>` around the old and new start values (and optionally that unchanged fields are not wrapped in `<strong>`).

---

## 4. Implementation order

| Step | Task |
|------|------|
| 1 | EmailSender: add `html_body` parameter and multipart/alternative when present |
| 2 | Notifier: add HTML escape helper; build `body_html` with same sections as plain |
| 3 | Notifier: in Updated section, compare old/new per field and wrap differing values in `<strong>` |
| 4 | Notifier: call `send_email(..., html_body=body_html)` |
| 5 | Tests: mail sender test for HTML part; notifier test for bold in updated section |

---

## 5. Out of scope

- **send_events_email** (the “New Events: N found” email in event_service): remains plain only; no bold logic needed.
- Rich formatting (colour, underline) beyond bold: not in this plan; can be added later using the same HTML body.
- Attachments: no change to attachment handling.
