# flight-controll

A small Flask service that fetches calendar events from iCal/webcal sources, persists them, detects added/removed/updated events, and sends a single summary email with changes.

Key features
- Periodically fetches events from configured webcal/iCal URLs
- Persists events into a Mongo-like collection
- Detects added, removed, and updated events (start/end changes)
- Only acts on future events but allows removals for events that started up to 10 hours ago
- Sends a single summary email containing added / removed / updated sections

This project was 100% made with vibe coding.

How to run locally

- Create and activate a virtual environment and install dependencies:

```bash
python -m venv .venv
& .venv\Scripts\Activate.ps1   # Windows PowerShell
pip install -r requirements.txt
pip install -r requirements-test.txt
```

- Run the app:

```bash
python main.py
```

Docker / docker-compose

- Build and start locally with docker-compose (the compose file is configured to build the local image):

```bash
docker-compose build
docker-compose up
```

Notes: the Dockerfile sets `PYTHONPATH=/app/src` so the `src/flight_controll` package is importable in the container.

Interacting with the service

- HTTP API: The app exposes a Flask blueprint under `/events` (see `src/flight_controll/rest/event_api.py`) with endpoints used for manual triggers and health checks:

	- `POST /events/trigger-check` – fetch events, persist new ones, detect add/remove/update, send summary email
	- `POST /events/fetch` – fetch events and return only those not yet stored (no persist)
	- `POST /events/fetch-persist` – fetch events, filter to new only, persist them (no email)

- Scheduler: The app registers a background scheduler job to fetch events periodically (interval configurable in `flight_controll.config`).

- Email: The app uses an SMTP-backed `EmailSender` (`src/flight_controll/mail/sender.py`) to send a single summary email of added/removed/updated events. Configure SMTP in `flight_controll.config`.

Testing

- Run tests with pytest:

```bash
pytest -q
```

- CI: The repository includes GitHub Actions workflows in `.github/workflows/` that run tests and build/publish a Docker image. The test workflow sets `PYTHONPATH=src` so the package in `src/` is found during CI.
