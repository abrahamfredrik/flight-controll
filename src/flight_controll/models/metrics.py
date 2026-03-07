from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass(frozen=True)
class RunMetrics:
    """Represents metrics for a scheduler run, to be persisted in MongoDB.

    Attributes:
        uuid: Unique identifier for this metrics record.
        start_time: UTC datetime when the run started.
        stop_time: UTC datetime when the run ended.
        success: True if the run completed without error, else False.
        new_count: Number of new entities detected.
        updated_count: Number of updated entities detected.
        removed_count: Number of removed entities detected.
        error: Optional error message if the run failed.
    """
    uuid: str
    start_time: datetime
    stop_time: datetime
    success: bool
    new_count: int
    updated_count: int
    removed_count: int
    error: Optional[str] = None
