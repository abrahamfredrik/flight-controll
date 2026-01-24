# conftest.py
import shutil
import os
import pytest
from app.rest import register_blueprints
from flask import Flask

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
    app = Flask(__name__)
    app.config.from_object(TestConfig)
    app.app_config = TestConfig()
    app.config['TESTING'] = True
    register_blueprints(app)
    return app

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def app_context(app):
    with app.app_context():
        yield

