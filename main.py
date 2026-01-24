from app import create_app
import sys
import logging

app = create_app()

# Logging configuration
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
formatter = logging.Formatter(
    "[%(asctime)s] [%(levelname)s] %(name)s - %(message)s"
)
handler.setFormatter(formatter)

# Configure Flask app logger
app.logger.handlers = []
app.logger.addHandler(handler)
app.logger.setLevel(logging.INFO)

# Configure root logger similarly
root_logger = logging.getLogger()
root_logger.handlers = []
root_logger.addHandler(handler)
root_logger.setLevel(logging.INFO)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3001)
