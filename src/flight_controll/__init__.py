from flask import Flask
from typing import Optional

from .config import Config
from .rest import register_blueprints
from .scheduler.scheduler import init_scheduler


def create_app(config_object: Optional[object] = None, enable_scheduler: Optional[bool] = None):
    """Create and configure the Flask application.

    Args:
        config_object: a config object or class to load into `app.config`.
            If omitted, the default `Config` is used. If a class is passed,
            an instance will be created and attached as `app.app_config`.
        enable_scheduler: optional override to enable/disable the scheduler.
            If not provided, the value from `app.app_config.SCHEDULER_ENABLED`
            is used.
    """
    app = Flask(__name__)

    cfg = config_object or Config
    app.config.from_object(cfg)

    # attach a typed config instance for convenience (used elsewhere)
    if isinstance(cfg, type):
        app.app_config = cfg()
    else:
        app.app_config = cfg

    register_blueprints(app)

    # determine whether to run scheduler (explicit override wins)
    if enable_scheduler is None:
        run_scheduler = getattr(app.app_config, "SCHEDULER_ENABLED", False)
    else:
        run_scheduler = bool(enable_scheduler)

    if run_scheduler:
        init_scheduler(app)

    return app
