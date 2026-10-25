from flask_apscheduler import APScheduler
import logging

logger = logging.getLogger(__name__)

scheduler = APScheduler()


def init_scheduler(app):
    app.config["SCHEDULER_API_ENABLED"] = True

    def webcal_check():
        logger.info("Running scheduled task: webcal_check", extra={"task": "webcal_check", "phase": "start"})
        try:
            event_service = app.extensions["make_event_service"](cfg=app.app_config)
            events = event_service.fetch_persist_and_send_events()
            new_count = len(events)
            logger.info(
                "webcal_check.completed",
                extra={"task": "webcal_check", "new_events": new_count, "phase": "complete"},
            )
        except Exception:
            logger.exception("Error during scheduled task webcal_check:")

    scheduler.task(
        "interval",
        id="webcal-check",
        minutes=app.app_config.WEBCAL_SCHEDULER_DELAY_MINUTES,
    )(webcal_check)
    # Expose for testing
    app.extensions["_webcal_check_func"] = webcal_check
    scheduler.init_app(app)
    scheduler.start()
