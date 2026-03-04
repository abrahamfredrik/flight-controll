from flask import Blueprint, current_app, jsonify
from ..event.event_service import EventService


def create_event_api_blueprint() -> Blueprint:
    event_api = Blueprint("event_api", __name__)

    def get_event_service() -> EventService:
        # Prefer factory from app.extensions to ensure consistent wiring.
        make_event_service = None
        try:
            make_event_service = current_app.extensions.get("make_event_service")
        except Exception:
            make_event_service = None

        if make_event_service:
            return make_event_service(cfg=current_app.app_config)

        config = current_app.app_config
        # fallback: prefer app-provided events collection when present
        events_collection = None
        try:
            events_collection = current_app.extensions.get("events_collection")
        except Exception:
            events_collection = None
        return EventService(config=config, events_collection=events_collection)

    @event_api.route("/trigger-check", methods=["POST"])
    def trigger_check() -> tuple:
        event_service = get_event_service()
        events = event_service.fetch_persist_and_send_events()
        return jsonify(events), 200

    @event_api.route("/fetch-persist", methods=["POST"])
    def fetch_persist() -> tuple:
        event_service = get_event_service()
        events = event_service.fetch_events()
        events = event_service.filter_new_events(events)
        event_service.store_events(events)
        return jsonify(events), 200

    @event_api.route("/fetch", methods=["POST"])
    def fetch() -> tuple:
        event_service = get_event_service()
        events = event_service.fetch_events()
        events = event_service.filter_new_events(events)
        return jsonify(events), 200

    return event_api
