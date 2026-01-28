from flask_apscheduler import APScheduler
from ..event.event_service import EventService
from ..webcal.fetcher import WebcalFetcher
from ..mail.sender import EmailSender
from ..config import Config
import logging

logger = logging.getLogger(__name__)

scheduler = APScheduler()

def init_scheduler(app):
    app.config['SCHEDULER_API_ENABLED'] = True
    
    @scheduler.task('interval', id='webcal-check', minutes=app.app_config.WEBCAL_SCHEDULER_DELAY_MINUTES)
    def webcal_check():
        logger.info("Running scheduled task: webcal_check")
        
        event_service = EventService(
        config=app.app_config,
        fetcher_cls=WebcalFetcher,
        email_sender_cls=EmailSender
    )
        try:
            events = event_service.fetch_persist_and_send_events()
            logger.info(f"webcal_check completed. {len(events)} new event(s) processed.")
        except Exception as e:
            logger.exception("Error during scheduled task webcal_check:")
    
    scheduler.init_app(app)
    scheduler.start()
