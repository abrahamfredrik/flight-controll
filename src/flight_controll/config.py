import os


def str_to_bool(val: str) -> bool:
    return val.lower() == "true"


class Config:
    SCHEDULER_ENABLED = str_to_bool(os.getenv("SCHEDULER_ENABLED", "True"))

    SMTP_SERVER = os.environ.get("SMTP_SERVER")
    SMTP_PORT: int = int(os.environ.get("SMTP_PORT", 587))

    SMTP_USERNAME = os.environ.get("SMTP_USERNAME")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
    RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL")

    WEB_CAL_URL = os.environ.get("WEB_CAL_URL")
    WEBCAL_SCHEDULER_DELAY_MINUTES: int = int(
        os.environ.get("WEBCAL_SCHEDULER_DELAY_MINUTES", 15)
    )

    MONGO_HOST = os.environ.get("MONGO_HOST")
    MONGO_DB = os.environ.get("MONGO_DB")
    MONGO_COLLECTION = os.environ.get("MONGO_COLLECTION")
    MONGO_USERNAME = os.environ.get("MONGO_USERNAME")
    MONGO_PASSWORD = os.environ.get("MONGO_PASSWORD")
