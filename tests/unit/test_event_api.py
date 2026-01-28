import json
from unittest.mock import MagicMock, patch


def make_service_mock(return_events=None):
    inst = MagicMock()
    if return_events is None:
        return_events = []
    inst.fetch_events.return_value = return_events
    inst.filter_new_events.return_value = return_events
    inst.store_events.return_value = return_events
    inst.fetch_persist_and_send_events.return_value = return_events
    return inst


@patch('flight_controll.rest.event_api.EventService')
def test_fetch_endpoint_returns_filtered_events(mock_event_service, client):
    data = [{"uid": "1", "summary": "S", "dtstart": "d", "dtend": "e"}]
    mock_event_service.return_value = make_service_mock(return_events=data)

    resp = client.post('/fetch')
    assert resp.status_code == 200
    assert resp.get_json() == data


@patch('flight_controll.rest.event_api.EventService')
def test_fetch_persist_endpoint_stores_events(mock_event_service, client):
    data = [{"uid": "1", "summary": "S"}]
    inst = make_service_mock(return_events=data)
    mock_event_service.return_value = inst

    resp = client.post('/fetch-persist')
    assert resp.status_code == 200
    assert resp.get_json() == data
    inst.store_events.assert_called_once()


@patch('flight_controll.rest.event_api.EventService')
def test_trigger_check_calls_fetch_persist_and_send(mock_event_service, client):
    data = [{"uid": "1", "summary": "S"}]
    inst = make_service_mock(return_events=data)
    mock_event_service.return_value = inst

    resp = client.post('/trigger-check')
    assert resp.status_code == 200
    assert resp.get_json() == data
    inst.fetch_persist_and_send_events.assert_called_once()
