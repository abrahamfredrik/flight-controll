import requests
import re
from datetime import datetime

class WebcalFetcher:
    def __init__(self, webcal_url: str):
        self.webcal_url = webcal_url

    def fetch_events(self):
        # Fetch the webcal (iCal) data
        response = requests.get(self.webcal_url)
        response.raise_for_status()
        ical_data = response.text

        # Split into VEVENT blocks
        events = []
        vevents = re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", ical_data, re.DOTALL)
        for vevent in vevents:
            event = {}
            # Extract fields using regex
            uid = re.search(r"UID:(.+)", vevent)
            dtstart = re.search(r"DTSTART(?:;TZID=[^:]+)?:([0-9T]+)", vevent)
            dtend = re.search(r"DTEND(?:;TZID=[^:]+)?:([0-9T]+)", vevent)
            summary = re.search(r"SUMMARY:(.+)", vevent)
            location = re.search(r"LOCATION:(.+)", vevent)
            description = re.search(r"DESCRIPTION:(.+)", vevent, re.DOTALL)

            event["uid"] = uid.group(1).strip() if uid else None
            event["dtstart"] = dtstart.group(1).strip() if dtstart else None
            event["dtend"] = dtend.group(1).strip() if dtend else None
            event["summary"] = summary.group(1).strip() if summary else None
            event["location"] = location.group(1).strip() if location else None
            event["description"] = description.group(1).strip().replace("\\n", "\n") if description else None

            # Optionally, parse dates to datetime objects
            if event["dtstart"]:
                try:
                    event["dtstart"] = datetime.strptime(event["dtstart"], "%Y%m%dT%H%M%S")
                except ValueError:
                    try:
                        event["dtstart"] = datetime.strptime(event["dtstart"], "%Y%m%dT%H%M")
                    except ValueError:
                        event["dtstart"] = event["dtstart"]
            if event["dtend"]:
                try:
                    event["dtend"] = datetime.strptime(event["dtend"], "%Y%m%dT%H%M%S")
                except ValueError:
                    try:
                        event["dtend"] = datetime.strptime(event["dtend"], "%Y%m%dT%H%M")
                    except ValueError:
                        event["dtend"] = event["dtend"]

            if event["uid"]:
                events.append(event)
        return events