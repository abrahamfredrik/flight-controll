# Copilot Instructions — Flask + MongoDB Scheduler Project

## Project Overview

This is a Python backend application built with Flask.
It uses MongoDB for persistence.

The application runs a scheduled job that:
1. Fetches calendar data from an external calendar provider
2. Compares it with persisted state in MongoDB
3. Detects changes (added, removed, or modified events)
4. Sends email notifications when changes occur

The system must be:
- Deterministic
- Idempotent
- Testable
- Secure
- Production-ready
- Observable

Copilot must follow all architectural and coding rules defined below.

---

# Core Architecture Rules

## 1. Application Structure

Always follow this structure:

app/
    __init__.py
    config.py
    extensions.py
    routes/
    services/
    repositories/
    models/
    scheduler/
    utils/

tests/

### Responsibilities

- routes/ → HTTP layer only (no business logic)
- services/ → business logic
- repositories/ → MongoDB interaction only
- models/ → schema definitions and domain models
- scheduler/ → background job orchestration
- utils/ → pure helper functions only

Never mix responsibilities.

---

## 2. Flask App Factory Pattern

Always use the app factory pattern.

Never create a global Flask app instance.
Use:

def create_app(config_object: str) -> Flask:

Initialize:
- Mongo client
- Scheduler
- Mail service
- Logging
- Configuration

Do not initialize extensions inside business logic.

---

## 3. MongoDB Usage Rules

Use PyMongo (or MongoEngine only if explicitly required).

Rules:
- All DB access must go through repository classes
- Never access Mongo directly inside routes or services
- Use indexes where appropriate
- Use atomic updates when possible
- Avoid full collection scans
- Always project only required fields

Document structure must be explicit and validated.

Every collection must define:
- Indexes
- Unique constraints (if applicable)
- Created_at and updated_at timestamps

---

## 4. Scheduler Design

Use APScheduler or a production-safe scheduler.

Rules:
- Scheduler must be initialized in app factory
- Jobs must be idempotent
- Jobs must log start, success, and failure
- No business logic inside scheduler definition
- Scheduler calls service layer only

Example pattern:

scheduler → service.compare_calendar_state()

Never:
- Send emails directly inside scheduler file
- Access Mongo directly inside scheduler file

---

## 5. Calendar Sync Logic

Calendar comparison must:

- Normalize external calendar data
- Convert timezones to UTC
- Compare using stable identifiers
- Detect:
    - Added events
    - Removed events
    - Modified events

Never rely on naive datetime objects.
Always use timezone-aware datetimes.

Comparison logic must be deterministic and testable.

---

## 6. Email Sending Rules

Email logic must:

- Be encapsulated in a service
- Support dependency injection for testing
- Be retry-safe
- Log failures
- Never block scheduler indefinitely

Never embed SMTP credentials in code.
Use environment variables.

---

# Code Quality Standards

## Typing

All new code must use type hints.
Use:

from __future__ import annotations

Use typing for:
- Function signatures
- Return values
- Complex dict structures

Avoid untyped dicts when possible.

---

## Docstrings

Every public function must include a docstring:

- What it does
- Arguments
- Returns
- Raises (if applicable)

Use Google-style docstrings.

---

## Error Handling

Never swallow exceptions.

Use:
- Specific exception handling
- Structured logging
- Custom domain exceptions when appropriate

Do not use bare `except:` blocks.

---

## Logging

Use structured logging.

Every scheduler run must log:
- Start time
- Number of events fetched
- Number of changes detected
- Email sent status
- Execution duration

Never use print().

---

## Configuration Management

All configuration must come from:

- Environment variables
- config.py classes

Never hardcode:
- API keys
- DB URLs
- Email credentials
- Secrets

---

## Testing Requirements

All business logic must be testable without:

- Running Flask server
- Running scheduler
- Real Mongo instance
- Real email server

Use:
- Dependency injection
- Repository abstraction
- Mock calendar provider
- Mock email service

Every comparison function must have unit tests covering:
- No changes
- Added event
- Removed event
- Modified event
- Timezone edge cases

---

## Security Requirements

- Validate all external data
- Sanitize email content
- Avoid injection risks
- Use TLS for email
- Never log secrets
- Avoid exposing stack traces in production

---

## Performance Rules

- Avoid N+1 queries
- Batch Mongo operations when possible
- Avoid loading entire collections into memory
- Use projections
- Use proper indexing

---

## Idempotency Rules

Scheduler runs must:

- Not duplicate emails
- Not duplicate DB entries
- Not reprocess unchanged events

Use versioning or hash comparison if necessary.

---

## Style Conventions

Follow:
- PEP8
- Black formatting
- isort imports
- 88 character line limit

Prefer:
- Small functions
- Pure functions where possible
- Explicit over implicit

Avoid:
- Deep nesting
- Large God classes
- Hidden side effects

---

# Patterns Copilot Should Prefer

When writing code, prefer:

- Service classes over large procedural scripts
- Repository pattern for persistence
- Explicit dependency injection
- UTC internally, local time only at boundaries
- Immutable data comparison logic

Avoid:

- Global state
- Tight coupling
- Direct DB access in routes
- Logic inside Flask route handlers

---

# Example Architectural Flow

Scheduler Trigger
    ↓
CalendarService.fetch_external_events()
    ↓
CalendarComparisonService.compare_with_db()
    ↓
CalendarRepository.save_changes()
    ↓
NotificationService.send_change_email()

Each layer must be independent and testable.

---

# When Generating Code

Copilot must:

- Follow folder structure
- Use clear separation of concerns
- Add type hints
- Add docstrings
- Include logging
- Avoid shortcuts
- Prefer explicit over clever

If unclear, generate clean, maintainable, testable code rather than concise code.

---

# Anti-Patterns to Avoid

- Business logic inside routes
- Mongo queries inside scheduler
- Using naive datetime
- Hardcoded secrets
- Sending emails synchronously inside comparison logic
- Unbounded retries
- Silent failures

---

End of instructions.