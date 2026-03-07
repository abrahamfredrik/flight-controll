from flask_apscheduler import APScheduler
from ..event.event_service import EventService
from ..webcal.fetcher import WebcalFetcher
from ..mail.sender import MailService
import logging

logger = logging.getLogger(__name__)

scheduler = APScheduler()


def init_scheduler(app):
    app.config["SCHEDULER_API_ENABLED"] = True

    def webcal_check():
        logger.info("Running scheduled task: webcal_check", extra={"task": "webcal_check", "phase": "start"})
        # Prefer an injected factory when available so scheduler does not
        # construct service instances or clients directly.
        make_event_service = None
        try:
            make_event_service = app.extensions.get("make_event_service")
        except Exception:
            make_event_service = None

        if make_event_service:
            event_service = make_event_service(cfg=app.app_config)
        else:
            # fallback: construct EventService directly
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
        from ..event.metrics_repository import MetricsRepository
        from ..models.metrics import RunMetrics
        import uuid as uuidlib
        from datetime import datetime, timezone

        metrics_collection = app.extensions.get("metrics_collection")
        metrics_repo = MetricsRepository(metrics_collection) if metrics_collection is not None else None

        run_uuid = str(uuidlib.uuid4())
        start_time = datetime.now(timezone.utc)
        success = False
        new_count = updated_count = removed_count = 0
        error_msg = None
        try:
            events = event_service.fetch_persist_and_send_events()
            # For metrics: fetch_persist_and_send_events returns new events; updated/removed counts are in logs only, so not directly available
            new_count = len(events)
            # Optionally, could expose updated/removed counts from service if needed
            success = True
            logger.info(
                "webcal_check.completed",
                extra={"task": "webcal_check", "new_events": new_count, "phase": "complete"},
            )
        except Exception as exc:
            error_msg = str(exc)
            logger.exception("Error during scheduled task webcal_check:")
        stop_time = datetime.now(timezone.utc)
        # Store metrics
        if metrics_repo:
            metrics = RunMetrics(
                uuid=run_uuid,
                start_time=start_time,
                stop_time=stop_time,
                success=success,
                new_count=new_count,
                updated_count=updated_count,
                removed_count=removed_count,
                error=error_msg,
            )
            try:
                metrics_repo.insert_metrics(metrics)
            except Exception:
                logger.exception("Failed to persist run metrics")

    scheduler.task(
        "interval",
        id="webcal-check",
        minutes=app.app_config.WEBCAL_SCHEDULER_DELAY_MINUTES,
    )(webcal_check)
    # Expose for testing
    app.extensions["_webcal_check_func"] = webcal_check
    scheduler.init_app(app)
    scheduler.start()
