import logging
from typing import List, Dict, Any, Optional

from pymongo import MongoClient
from app.webcal.fetcher import WebcalFetcher
from app.mail.sender import EmailSender
from app.config import Config

class EventService:
    """Service responsible for fetching events, persisting new ones and sending email.

    Improvements:
    - Accept optional `mongo_client` or `events_collection` to allow dependency injection
      for testing and to avoid creating real network clients at import-time.
    - Keep backwards compatibility when mongo_client/events_collection are not provided.
    """

    def __init__(
        self,
        config: Config,
        email_sender_cls=EmailSender,
        fetcher_cls=WebcalFetcher,
        mongo_client: Optional[MongoClient] = None,
        events_collection: Optional[object] = None,
    ):
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.email_sender_cls = email_sender_cls
        self.fetcher_cls = fetcher_cls

        # allow tests to inject a fake collection directly
        if events_collection is not None:
            self.events_collection = events_collection
            self.mongo_client = mongo_client
            self.db = None
            return

        # otherwise construct or use provided mongo_client
        self.mongo_uri = (
            f"mongodb+srv://{self.config.MONGO_USERNAME}:{self.config.MONGO_PASSWORD}@"
            f"{self.config.MONGO_HOST}/{self.config.MONGO_DB}?retryWrites=true&w=majority"
        )
        self.mongo_client = mongo_client or MongoClient(self.mongo_uri)
        self.db = self.mongo_client[self.config.MONGO_DB]
        self.events_collection = self.db[self.config.MONGO_COLLECTION]
        
    def store_events(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        for event_data in events:
            if not self.events_collection.find_one({"uid": event_data["uid"]}):
                doc = {
                    "uid": event_data["uid"],
                    "summary": event_data["summary"],
                    "start_time": event_data["dtstart"],
                    "end_time": event_data["dtend"],
                    "description": event_data.get("description"),
                    "location": event_data.get("location")
                }
                self.events_collection.insert_one(doc)
        return events

    def fetch_events(self) -> List[Dict[str, Any]]:
        fetcher: WebcalFetcher = self.fetcher_cls(self.config.WEB_CAL_URL)
        events = fetcher.fetch_events()
        # List of locations to filter out (case-insensitive)
        excluded_locations = ["privat"] 
        excluded_locations = [loc.lower() for loc in excluded_locations]
        filtered_events = [
            event for event in events
            if not (
                event.get('location') and 
                event['location'].strip().lower() in excluded_locations
            )
        ]
        return filtered_events

    def send_events_email(self, events: List[Dict[str, Any]]) -> None:
        if not events:
            return
        email_sender = self.email_sender_cls(self.config.SMTP_SERVER, 
                                   self.config.SMTP_PORT, 
                                   self.config.SMTP_USERNAME, 
                                   self.config.SMTP_PASSWORD)
        subject = f"New Events: {len(events)} found"
        body = "Event Details:\n\n"
        for event in events:
            body += (
                f"Summary: {event['summary']}\n"
                f"Start Time: {event['dtstart']}\n"
                f"End Time: {event['dtend']}\n"
                f"Description: {event.get('description', 'N/A')}\n"
                f"Location: {event.get('location', 'N/A')}\n"
                "--------------------------\n"
            )
        email_sender.send_email(self.config.RECIPIENT_EMAIL, subject, body)

    def filter_new_events(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        uids = [event["uid"] for event in events]
        existing_uids_cursor = self.events_collection.find(
            {"uid": {"$in": uids}}, {"uid": 1}
        )
        existing_uids = {doc["uid"] for doc in existing_uids_cursor}
        return [event for event in events if event["uid"] not in existing_uids]

    def fetch_persist_and_send_events(self) -> List[Dict[str, Any]]:
        events = self.fetch_events()
        events = self.filter_new_events(events)
        self.store_events(events)
        self.send_events_email(events)
        return events
