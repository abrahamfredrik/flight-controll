# conftest.py
import shutil
import os
import pytest
from unittest.mock import MagicMock
from flask import Flask
import sys
# ensure `src` is on path so tests can import the package at src/flight_controll
ROOT = os.path.dirname(os.path.dirname(__file__))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from flight_controll import create_app


def pytest_sessionfinish(session, exitstatus):
    for root, dirs, files in os.walk("."):
        for d in dirs:
            if d == "__pycache__":
                shutil.rmtree(os.path.join(root, d), ignore_errors=True)

class TestConfig:
    SCHEDULER_ENABLED = True

    SMTP_SERVER = "smtp.mail.testserver.com"
    SMTP_PORT =  587

    SMTP_USERNAME =  "test@mail.com"
    SMTP_PASSWORD = "testpassword"
    RECIPIENT_EMAIL = "recipient@mail.com"
    
    MONGO_HOST="host.com"
    MONGO_DB="testdb"
    MONGO_COLLECTION="col"
    MONGO_USERNAME="user"
    MONGO_PASSWORD="password123"

@pytest.fixture(scope='session')
def app():
    # use the application factory so tests exercise the same initialization
    app = create_app(config_object=TestConfig, enable_scheduler=False)
    app.config['TESTING'] = True
    return app

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def app_context(app):
    with app.app_context():
        yield

@pytest.fixture
def fake_collection():
    """Lightweight MagicMock collection used by tests to avoid repetition."""
    col = MagicMock()
    col.find_one.return_value = None
    col.find.return_value = []
    col.insert_one = MagicMock()
    col.delete_many = MagicMock()
    col.update_one = MagicMock()
    return col

@pytest.fixture
def fake_sender_cls():
    """Returns a (sender_cls, sender_instance) pair where the class constructs the instance."""
    inst = MagicMock()
    cls = MagicMock(return_value=inst)
    return cls, inst

