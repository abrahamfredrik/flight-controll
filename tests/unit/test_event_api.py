import pytest
from unittest.mock import MagicMock

from flight_controll import create_app


class ConfigWithoutMongo:
    SCHEDULER_ENABLED = False


def make_service_mock(return_events=None):
    inst = MagicMock()
    if return_events is None:
        return_events = []
    inst.fetch_events.return_value = return_events
    inst.filter_new_events.return_value = return_events
    inst.store_events.return_value = return_events
    inst.fetch_persist_and_send_events.return_value = return_events
    return inst


def test_service_factory_is_registered_without_mongo_config():
    app = create_app(config_object=ConfigWithoutMongo, enable_scheduler=False)
    make_service = app.extensions["make_event_service"]

    with pytest.raises(RuntimeError, match="Mongo is not configured"):
        make_service()

    collection = MagicMock()
    app.extensions["events_collection"] = collection
    service = make_service()

    assert service.repository.collection is collection


def test_fetch_endpoint_returns_filtered_events(client):
    data = [{"uid": "1", "summary": "S", "dtstart": "d", "dtend": "e"}]
    service = make_service_mock(return_events=data)
    client.application.extensions["make_event_service"] = MagicMock(return_value=service)

    resp = client.post("/events/fetch")
    assert resp.status_code == 200
    assert resp.get_json() == data


def test_fetch_persist_endpoint_stores_events(client):
    data = [{"uid": "1", "summary": "S"}]
    inst = make_service_mock(return_events=data)
    client.application.extensions["make_event_service"] = MagicMock(return_value=inst)

    resp = client.post("/events/fetch-persist")
    assert resp.status_code == 200
    assert resp.get_json() == data
    inst.store_events.assert_called_once()


def test_trigger_check_calls_fetch_persist_and_send(client):
    data = [{"uid": "1", "summary": "S"}]
    inst = make_service_mock(return_events=data)
    client.application.extensions["make_event_service"] = MagicMock(return_value=inst)

    resp = client.post("/events/trigger-check")
    assert resp.status_code == 200
    assert resp.get_json() == data
    inst.fetch_persist_and_send_events.assert_called_once()
