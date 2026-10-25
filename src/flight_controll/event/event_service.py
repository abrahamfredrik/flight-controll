import logging
from typing import List, Dict, Any, Optional, Set
from datetime import datetime
import time
from . import repository, notifier, utils
from .change_detector import detect_removed_events, detect_updates, normalize_dtstamp

from ..webcal.fetcher import WebcalFetcher
from ..mail.sender import EmailSenderFactory, MailService
from ..config import Config

EXCLUDED_LOCATIONS = ["privat"]


class EventService:
    """Service responsible for fetching events, persisting new ones and sending email.

        Persistence and external adapters are injected by the application factory.
    """

    def __init__(
        self,
        config: Config,
        repo: repository.EventRepository,
        email_sender_cls: EmailSenderFactory = MailService,
        fetcher_cls=WebcalFetcher,
    ):
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.email_sender_cls = email_sender_cls
        self.fetcher_cls = fetcher_cls
        self.repository = repo

    def store_events(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Persist new event dicts to the events collection.

        Args:
            events: list of event dictionaries as returned by the fetcher.

        Returns:
            The same list of events that were passed in.
        """
        # persist via repository
        self.repository.insert_events(events)
        return events

    def fetch_events(self) -> List[Dict[str, Any]]:
        """Fetch events from the external calendar provider and filter them.

        Returns:
            A list of event dictionaries. Events from excluded locations are
            filtered out.
        """
        fetcher: WebcalFetcher = self.fetcher_cls(self.config.WEB_CAL_URL)
        events = fetcher.fetch_events()
        excluded_lower = [loc.lower() for loc in EXCLUDED_LOCATIONS]
        filtered_events = [
            event
            for event in events
            if not (
                event.get("location")
                and event["location"].strip().lower() in excluded_lower
            )
        ]
        return filtered_events

    def send_events_email(self, events: List[Dict[str, Any]]) -> None:
        """Send one plain-text email describing the provided events.

        Args:
            events: list of event dicts to include in the email. If empty,
                the function is a no-op.
        """
        if not events:
            return
        email_sender = self.email_sender_cls(
            self.config.SMTP_SERVER,
            self.config.SMTP_PORT,
            self.config.SMTP_USERNAME,
            self.config.SMTP_PASSWORD,
        )
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

    def send_summary_email(
        self,
        added_events: List[Dict[str, Any]],
        removed_events: List[Dict[str, Any]],
        updated_events: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Render and send a single summary email for the event changes.

        Message formatting is delegated to `notifier`; the configured mail
        transport is responsible only for delivery.
        """
        message = notifier.render_summary(
            added_events or [],
            removed_events or [],
            updated_events or [],
        )
        if message is None:
            return

        email_sender = self.email_sender_cls(
            self.config.SMTP_SERVER,
            self.config.SMTP_PORT,
            self.config.SMTP_USERNAME,
            self.config.SMTP_PASSWORD,
        )
        email_sender.send_email(
            self.config.RECIPIENT_EMAIL,
            message.subject,
            message.body,
            html_body=message.html_body,
        )

    def filter_new_events(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        uids = [event["uid"] for event in events]
        existing_uids_cursor = self.repository.collection.find({"uid": {"$in": uids}}, {"uid": 1})
        existing_uids = {doc["uid"] for doc in existing_uids_cursor}
        return [event for event in events if event["uid"] not in existing_uids]

    def _existing_matching_uids(self, fetched_uids: Set[str]) -> Set[str]:
        return self.repository.existing_matching_uids(fetched_uids)

    def _parse_dt(self, v: Any) -> Optional[datetime]:
        return utils.parse_dt(v)

    def normalize_dtstamp(self, text: Optional[str]) -> str:
        return normalize_dtstamp(text)

    def fetch_persist_and_send_events(self) -> List[Dict[str, Any]]:
        start_ts = time.monotonic()
        if self.logger:
            self.logger.info("fetch_persist_and_send_events.start", extra={"action": "fetch_start"})

        # fetch remote events
        events = self.fetch_events()
        fetched_count = len(events)
        fetched_uids = {event["uid"] for event in events}
        if self.logger:
            self.logger.info("fetch_persist_and_send_events.fetched", extra={"fetched_count": fetched_count})

        # Which fetched uids already exist in DB?
        existing_matching = self._existing_matching_uids(fetched_uids)

        # New events are those fetched but not present in DB
        new_events = [event for event in events if event["uid"] not in existing_matching]
        new_count = len(new_events)

        # Determine all uids present in DB (used to compute removals)
        existing_all = self.repository.existing_all_uids()

        # If the $in matching returned nothing but DB clearly contains some fetched uids,
        # use that information to recompute matching/new sets (guard for fakes)
        if not existing_matching and (fetched_uids & existing_all):
            existing_matching = fetched_uids & existing_all
            new_events = [event for event in events if event["uid"] not in existing_matching]
            new_count = len(new_events)

        # Compare matching events, then persist the detected changes.
        stored_matching = self.repository.find_docs_by_uids(list(existing_matching))
        detected_updates = detect_updates(events, stored_matching)
        for update in detected_updates:
            self.repository.update_one(update.uid, update.set_payload)
        updated_events = [update.notification for update in detected_updates]
        updated_count = len(updated_events)

        # Select eligible removals, then remove them from persistence.
        removed_uids = existing_all - fetched_uids
        stored_removed = self.repository.find_docs_by_uids(list(removed_uids))
        removed_events = detect_removed_events(existing_all, fetched_uids, stored_removed)
        if removed_events:
            self.repository.delete_by_uids([event["uid"] for event in removed_events])
        removed_count = len(removed_events)

        # persist new events and send a single summary email for added/removed/updated
        if new_events:
            self.store_events(new_events)

        # send summary
        try:
            self.send_summary_email(new_events, removed_events, updated_events)
            email_status = "sent"
        except Exception as e:
            if self.logger:
                self.logger.exception("Failed to send summary email: %s", e)
            email_status = "failed"

        duration = time.monotonic() - start_ts
        # Structured summary log of the run
        if self.logger:
            self.logger.info(
                "fetch_persist_and_send_events.complete",
                extra={
                    "duration_seconds": duration,
                    "fetched_count": fetched_count,
                    "new_count": new_count,
                    "updated_count": updated_count,
                    "removed_count": removed_count,
                    "email_status": email_status,
                },
            )

        # Return list of processed new events for backward compatibility
        return new_events
