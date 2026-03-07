import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
from src.flight_controll.scheduler import scheduler as sched_module
from src.flight_controll.models.metrics import RunMetrics

def test_scheduler_persists_metrics(monkeypatch):
    app = MagicMock()
    app.app_config.WEBCAL_SCHEDULER_DELAY_MINUTES = 1
    fake_metrics_collection = MagicMock()
    app.extensions = {
        "make_event_service": lambda **kwargs: MagicMock(fetch_persist_and_send_events=lambda: []),
        "metrics_collection": fake_metrics_collection,
    }
    # Patch APScheduler to not actually start
    monkeypatch.setattr(sched_module.scheduler, "init_app", lambda app: None)
    monkeypatch.setattr(sched_module.scheduler, "start", lambda: None)
    # Patch uuid4 to return a fixed value
    monkeypatch.setattr("uuid.uuid4", lambda: "test-uuid")
    # (No need to patch datetime for this test)
    # Call init_scheduler, which will register the job and expose the function
    sched_module.init_scheduler(app)
    # Call the scheduled job function directly
    job_func = app.extensions["_webcal_check_func"]
    job_func()
    # Check that metrics were inserted
    assert fake_metrics_collection.insert_one.called
    inserted_doc = fake_metrics_collection.insert_one.call_args[0][0]
    assert inserted_doc["uuid"] == "test-uuid"
    assert inserted_doc["success"] is True
    assert inserted_doc["new_count"] == 0
    assert inserted_doc["updated_count"] == 0
    assert inserted_doc["removed_count"] == 0
