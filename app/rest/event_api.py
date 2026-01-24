from flask import Blueprint, current_app, jsonify
from app.event.event_service import EventService

def create_event_api_blueprint() -> Blueprint:
    event_api = Blueprint("event_api", __name__)

    def get_event_service() -> EventService:
        config = current_app.app_config
        return EventService(config=config)

    @event_api.route('/trigger-check', methods=['POST'])
    def trigger_check() -> tuple:
        event_service = get_event_service()
        events = event_service.fetch_persist_and_send_events()
        return jsonify(events), 200

    @event_api.route('/fetch-persist', methods=['POST'])
    def fetch_persist() -> tuple:
        event_service = get_event_service()
        events = event_service.fetch_events()
        events = event_service.filter_new_events(events)
        event_service.store_events(events)
        return jsonify(events), 200

    @event_api.route('/fetch', methods=['POST'])
    def fetch() -> tuple:
        event_service = get_event_service()
        events = event_service.fetch_events()
        events = event_service.filter_new_events(events)
        return jsonify(events), 200

    return event_api
