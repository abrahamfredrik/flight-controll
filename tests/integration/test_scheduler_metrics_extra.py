import pytest
from unittest.mock import MagicMock, patch
from src.flight_controll.scheduler import scheduler as sched_module

def test_scheduler_metrics_on_failure(monkeypatch):
    app = MagicMock()
    app.app_config.WEBCAL_SCHEDULER_DELAY_MINUTES = 1
    fake_metrics_collection = MagicMock()
    # Simulate EventService raising an exception
    def failing_fetch():
        raise RuntimeError("Simulated failure")
    app.extensions = {
        "make_event_service": lambda **kwargs: MagicMock(fetch_persist_and_send_events=failing_fetch),
        "metrics_collection": fake_metrics_collection,
    }
    monkeypatch.setattr(sched_module.scheduler, "init_app", lambda app: None)
    monkeypatch.setattr(sched_module.scheduler, "start", lambda: None)
    monkeypatch.setattr("uuid.uuid4", lambda: "fail-uuid")
    sched_module.init_scheduler(app)
    job_func = app.extensions["_webcal_check_func"]
    job_func()
    assert fake_metrics_collection.insert_one.called
    inserted_doc = fake_metrics_collection.insert_one.call_args[0][0]
    assert inserted_doc["uuid"] == "fail-uuid"
    assert inserted_doc["success"] is False
    assert inserted_doc["error"] == "Simulated failure"

def test_scheduler_metrics_counts(monkeypatch):
    app = MagicMock()
    app.app_config.WEBCAL_SCHEDULER_DELAY_MINUTES = 1
    fake_metrics_collection = MagicMock()
    # Simulate EventService returning 3 new events
    app.extensions = {
        "make_event_service": lambda **kwargs: MagicMock(fetch_persist_and_send_events=lambda: [{}, {}, {}]),
        "metrics_collection": fake_metrics_collection,
    }
    monkeypatch.setattr(sched_module.scheduler, "init_app", lambda app: None)
    monkeypatch.setattr(sched_module.scheduler, "start", lambda: None)
    monkeypatch.setattr("uuid.uuid4", lambda: "count-uuid")
    sched_module.init_scheduler(app)
    job_func = app.extensions["_webcal_check_func"]
    job_func()
    assert fake_metrics_collection.insert_one.called
    inserted_doc = fake_metrics_collection.insert_one.call_args[0][0]
    assert inserted_doc["uuid"] == "count-uuid"
    assert inserted_doc["success"] is True
    assert inserted_doc["new_count"] == 3
    assert inserted_doc["updated_count"] == 0
    assert inserted_doc["removed_count"] == 0
