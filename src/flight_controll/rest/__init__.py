from .event_api import create_event_api_blueprint

def register_blueprints(app):
    app.register_blueprint(create_event_api_blueprint())
