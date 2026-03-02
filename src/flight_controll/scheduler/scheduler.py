from flask_apscheduler import APScheduler
from ..event.event_service import EventService
from ..webcal.fetcher import WebcalFetcher
from ..mail.sender import MailService
import logging

logger = logging.getLogger(__name__)

scheduler = APScheduler()


def init_scheduler(app):
    app.config["SCHEDULER_API_ENABLED"] = True

    @scheduler.task(
        "interval",
        id="webcal-check",
        minutes=app.app_config.WEBCAL_SCHEDULER_DELAY_MINUTES,
    )
    def webcal_check():
        logger.info("Running scheduled task: webcal_check", extra={"task": "webcal_check", "phase": "start"})
        # Prefer an injected collection when available to avoid creating new
        # network clients during scheduled runs (enables easier testing and
        # deterministic behaviour).
        events_collection = None
        try:
            events_collection = app.extensions.get("events_collection")
        except Exception:
            events_collection = None

        event_service = EventService(
            config=app.app_config,
            fetcher_cls=WebcalFetcher,
            email_sender_cls=MailService,
            events_collection=events_collection,
        )
        try:
            events = event_service.fetch_persist_and_send_events()
            logger.info(
                "webcal_check.completed",
                extra={"task": "webcal_check", "new_events": len(events), "phase": "complete"},
            )
        except Exception:
            logger.exception("Error during scheduled task webcal_check:")

    scheduler.init_app(app)
    scheduler.start()
