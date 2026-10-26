# flight-controll

A Flask service that polls a webcal/iCal feed, stores the fetched events, detects additions/removals/updates, and sends a single change summary by email or Discord webhook.

## Features

- Fetches events from a configured iCal/webcal source
- Normalizes and stores event data in MongoDB
- Detects new, removed, and updated events
- Sends one summary notification for the latest change set
- Supports both SMTP email and Discord webhook delivery
- Runs a background scheduler for periodic checks
- Exposes lightweight HTTP endpoints for manual fetch/persist/check flows

## Architecture

The application follows a simple service-oriented layout:

- `src/flight_controll/rest/` — Flask routes
- `src/flight_controll/event/` — fetch, compare, persist, and notification logic
- `src/flight_controll/repository/` — MongoDB interaction via repository classes
- `src/flight_controll/mail/` — email and Discord delivery adapters
- `src/flight_controll/scheduler/` — APScheduler setup
- `src/flight_controll/config.py` — environment-driven configuration

## Local setup

Create and activate a virtual environment, then install the project dependencies:

```bash
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -r requirements-test.txt
```

Set the required environment variables before starting the app. A minimal example looks like this:

```bash
$env:WEB_CAL_URL="https://example.com/calendar.ics"
$env:MONGO_HOST="mongodb+srv://cluster.example.mongodb.net"
$env:MONGO_DB="flight_controll"
$env:MONGO_COLLECTION="events"
$env:SMTP_SERVER="smtp.example.com"
$env:SMTP_PORT="587"
$env:SMTP_USERNAME="user@example.com"
$env:SMTP_PASSWORD="secret"
$env:RECIPIENT_EMAIL="alerts@example.com"
$env:SCHEDULER_ENABLED="true"
$env:WEBCAL_SCHEDULER_DELAY_MINUTES="15"
```

Optional:

```bash
$env:DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
```

If `DISCORD_WEBHOOK_URL` is set, notifications are sent there before falling back to SMTP delivery.

## Running the app

Start the Flask app from the project root:

```bash
python main.py
```

The app listens on `0.0.0.0:3001` by default.

## HTTP API

The app registers a blueprint at `/events` and exposes these endpoints:

- `POST /events/trigger-check` — fetch the remote calendar, compare it with stored events, persist new ones, and send a summary notification
- `POST /events/fetch` — fetch the remote calendar and return only newly discovered events without persisting them
- `POST /events/fetch-persist` — fetch the remote calendar, keep only new events, and store them without sending email

Example:

```bash
curl -X POST http://localhost:3001/events/trigger-check
```

## Scheduler

The scheduler is initialized in the app factory and started when `SCHEDULER_ENABLED` is true.

The scheduled task runs `fetch_persist_and_send_events()` and logs run details including counts and duration. You can disable it locally with:

```bash
$env:SCHEDULER_ENABLED="false"
```

## Docker

Build and run the service with Docker Compose:

```bash
docker-compose build
docker-compose up
```

The Docker image sets `PYTHONPATH=/app/src` so the `src/flight_controll` package is importable inside the container.

## Testing

Run the unit and integration tests with:

```bash
pytest -q
```

The project includes coverage for event detection, fetchers, API behavior, scheduler behavior, and mail/Discord notification formatting.

## Notes

- Mongo configuration is intentionally environment-driven.
- Scheduling, persistence, and notification delivery are injected so the app is easier to test without a live server or external services.
- The app avoids naive datetimes and compares calendar data deterministically for change detection.

