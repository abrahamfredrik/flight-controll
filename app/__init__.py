from flask import Flask

from .config import Config
from app.rest import register_blueprints
from app.scheduler.scheduler import init_scheduler

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.app_config = Config()
    register_blueprints(app)
    if app.app_config.SCHEDULER_ENABLED:
        init_scheduler(app)

    return app