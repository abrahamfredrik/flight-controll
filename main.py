import logging
import sys

from flight_controll import create_app


def setup_logging(app):
    """Configure logging for the Flask app and root logger (handler, formatter, level)."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(name)s - %(message)s"
    )
    handler.setFormatter(formatter)

    app.logger.handlers = []
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)

    root_logger = logging.getLogger()
    root_logger.handlers = []
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)


app = create_app()
setup_logging(app)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3001)
