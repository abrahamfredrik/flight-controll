from datetime import datetime, timezone, timedelta
from typing import Optional, Any


def parse_dt(v: Any) -> Optional[datetime]:
    if v is None:
        return None
    if isinstance(v, datetime):
        dt = v
    elif isinstance(v, str):
        try:
            dt = datetime.fromisoformat(v)
        except Exception:
            return None
    else:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def removal_threshold_hours() -> int:
    # Keep hardcoded threshold here; make configurable later if desired
    return 10


def threshold_datetime() -> datetime:
    return datetime.now(timezone.utc) - timedelta(hours=removal_threshold_hours())


def is_within_removal_window(dt: datetime) -> bool:
    """Return True if dt is after (now - window_hours)."""
    if dt is None:
        return False
    return dt > threshold_datetime()
