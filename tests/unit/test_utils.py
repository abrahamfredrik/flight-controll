from datetime import datetime, timedelta, timezone

from flight_controll.event import utils


def test_parse_dt_with_iso_string():
    s = "2099-01-01T10:00:00"
    dt = utils.parse_dt(s)
    assert dt is not None
    assert dt.tzinfo is not None
    assert dt.isoformat().startswith(s)


def test_parse_dt_with_datetime_obj():
    now = datetime.now(timezone.utc)
    dt = utils.parse_dt(now)
    assert dt == now


def test_is_within_removal_window(monkeypatch):
    # control the threshold to a fixed point
    fixed = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(utils, "threshold_datetime", lambda: fixed)

    # dt after threshold -> True
    dt_after = fixed + timedelta(hours=1)
    assert utils.is_within_removal_window(dt_after)

    # dt before threshold -> False
    dt_before = fixed - timedelta(hours=11)
    assert not utils.is_within_removal_window(dt_before)
