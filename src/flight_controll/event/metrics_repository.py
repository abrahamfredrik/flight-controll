from __future__ import annotations
from typing import Any, Dict
from ..models.metrics import RunMetrics

class MetricsRepository:
    """Repository for persisting run metrics to MongoDB."""
    def __init__(self, collection: object):
        self.collection = collection

    def insert_metrics(self, metrics: RunMetrics) -> Any:
        """Insert a RunMetrics object as a document in the metrics collection.

        Args:
            metrics: RunMetrics dataclass instance.
        Returns:
            The result of the insert operation (e.g., InsertOneResult).
        """
        doc: Dict[str, Any] = {
            "uuid": metrics.uuid,
            "start_time": metrics.start_time,
            "stop_time": metrics.stop_time,
            "success": metrics.success,
            "new_count": metrics.new_count,
            "updated_count": metrics.updated_count,
            "removed_count": metrics.removed_count,
            "error": metrics.error,
        }
        return self.collection.insert_one(doc)
