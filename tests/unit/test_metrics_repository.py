import pytest
from datetime import datetime, timezone
from uuid import uuid4
from src.flight_controll.models.metrics import RunMetrics
from src.flight_controll.event.metrics_repository import MetricsRepository

class FakeCollection:
    def __init__(self):
        self.inserted = []
    def insert_one(self, doc):
        self.inserted.append(doc)
        return {'inserted_id': doc.get('uuid')}

def test_insert_metrics_inserts_document():
    fake_coll = FakeCollection()
    repo = MetricsRepository(fake_coll)
    metrics = RunMetrics(
        uuid=str(uuid4()),
        start_time=datetime(2026, 3, 7, 12, 0, tzinfo=timezone.utc),
        stop_time=datetime(2026, 3, 7, 12, 1, tzinfo=timezone.utc),
        success=True,
        new_count=2,
        updated_count=1,
        removed_count=0,
        error=None,
    )
    result = repo.insert_metrics(metrics)
    assert len(fake_coll.inserted) == 1
    doc = fake_coll.inserted[0]
    assert doc['uuid'] == metrics.uuid
    assert doc['start_time'] == metrics.start_time
    assert doc['stop_time'] == metrics.stop_time
    assert doc['success'] is True
    assert doc['new_count'] == 2
    assert doc['updated_count'] == 1
    assert doc['removed_count'] == 0
    assert doc['error'] is None
    assert result['inserted_id'] == metrics.uuid
