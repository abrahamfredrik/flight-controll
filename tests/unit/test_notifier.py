from flight_controll.event import notifier


def test_render_summary_returns_none_for_no_changes():
    assert notifier.render_summary([], [], []) is None


def test_render_summary_includes_all_sections():
    added = [{"uid": "a1", "summary": "A", "dtstart": "s", "dtend": "e"}]
    removed = [{"uid": "r1", "summary": "R", "start_time": "s2", "end_time": "e2"}]
    updated = [
        {
            "uid": "u1",
            "summary": "U",
            "old_start": "o",
            "old_end": "oe",
            "new_start": "n",
            "new_end": "ne",
        }
    ]

    message = notifier.render_summary(added, removed, updated)

    assert message is not None
    assert message.subject == "Events update: 1 added, 1 removed, 1 updated"
    assert "Added Events" in message.body
    assert "Removed Events" in message.body
    assert "Updated Events" in message.body
    assert "Updated Events" in message.html_body


def test_render_summary_bolds_changed_fields():
    """When an updated event has old_start != new_start, HTML body wraps both in <strong>."""
    added = []
    removed = []
    # old_start != new_start -> both should be bold; old_end == new_end -> not bold
    updated = [
        {
            "uid": "u1",
            "summary": "Meeting",
            "old_start": "2025-01-01T10:00",
            "new_start": "2025-01-01T11:00",
            "old_end": "2025-01-01T11:00",
            "new_end": "2025-01-01T11:00",
            "old_description": "Same",
            "new_description": "Same",
            "old_location": "Room A",
            "new_location": "Room B",
        }
    ]

    message = notifier.render_summary(added, removed, updated)
    assert message is not None
    html = message.html_body
    # Changed fields: start (old != new), location (old != new) -> bold
    assert "<strong>2025-01-01T10:00</strong>" in html
    assert "<strong>2025-01-01T11:00</strong>" in html
    assert "<strong>Room A</strong>" in html
    assert "<strong>Room B</strong>" in html
    # Unchanged description "Same" should not be wrapped in strong
    assert "Old Description: Same\n" in html
    assert "New Description: Same\n" in html
