from unittest.mock import MagicMock, patch

import pytest

from flight_controll.webcal.fetcher import WebcalFetcher


@patch("flight_controll.webcal.fetcher.parse_ical_events")
@patch("flight_controll.webcal.fetcher.requests.get")
def test_fetch_events_delegates_response_text_to_parser(mock_get, mock_parser):
    response = MagicMock()
    response.text = "calendar body"
    mock_get.return_value = response
    parsed_events = [{"uid": "event-1"}]
    mock_parser.return_value = parsed_events
    fetcher = WebcalFetcher("https://example.com/calendar.ics")

    events = fetcher.fetch_events()

    assert events == parsed_events
    mock_get.assert_called_once_with("https://example.com/calendar.ics")
    response.raise_for_status.assert_called_once_with()
    mock_parser.assert_called_once_with("calendar body")


@patch("flight_controll.webcal.fetcher.requests.get")
def test_fetch_events_raises_for_bad_http(mock_get):
    response = MagicMock()
    response.raise_for_status.side_effect = Exception("404 Not Found")
    mock_get.return_value = response
    fetcher = WebcalFetcher("https://example.com/calendar.ics")

    with pytest.raises(Exception, match="404 Not Found"):
        fetcher.fetch_events()
