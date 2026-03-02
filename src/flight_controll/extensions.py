from __future__ import annotations

from typing import Optional
from flask import Flask
import logging

logger = logging.getLogger(__name__)


def init_extensions(app: Flask) -> None:
    """Initialize long-lived extensions and attach them to the Flask app.

    Currently this will create and attach a Mongo client and a reference to the
    configured events collection as `app.extensions['events_collection']`.

    The function is safe to call when Mongo configuration is incomplete — in
    that case no client/collection is created and the application can still run
    in test mode where callers inject fake collections.

    Args:
        app: the Flask application instance
    """
    # Lazily import PyMongo to avoid import-time side effects in tests
    try:
        from pymongo import MongoClient
    except Exception:
        MongoClient = None  # type: ignore

    cfg = getattr(app, "app_config", None)
    if cfg is None:
        logger.info("No app_config on app; skipping extension initialization")
        return

    host = getattr(cfg, "MONGO_HOST", None)
    db_name = getattr(cfg, "MONGO_DB", None)
    coll_name = getattr(cfg, "MONGO_COLLECTION", None)
    username = getattr(cfg, "MONGO_USERNAME", None)
    password = getattr(cfg, "MONGO_PASSWORD", None)

    if not (host and db_name and coll_name and MongoClient):
        logger.info("Mongo configuration incomplete or pymongo missing; skipping Mongo init")
        return

    # Build a Mongo URI that supports username/password when provided
    if username and password:
        mongo_uri = f"mongodb+srv://{username}:{password}@{host}/{db_name}?retryWrites=true&w=majority"
    else:
        mongo_uri = host

    try:
        client = MongoClient(mongo_uri)
        db = client[db_name]
        events_collection = db[coll_name]
        # attempt to create recommended indexes for the events collection
        try:
            from .event import repository as event_repository

            event_repository.create_indexes(events_collection)
        except Exception:
            logger.exception("Failed to create indexes on events collection; continuing")
        # attach to app.extensions for consumption by services and blueprints
        app.extensions = getattr(app, "extensions", {})
        app.extensions["mongo_client"] = client
        app.extensions["events_collection"] = events_collection
        logger.info("Mongo client and events collection attached to app.extensions")
    except Exception:
        logger.exception("Failed to initialize Mongo client; continuing without DB")
