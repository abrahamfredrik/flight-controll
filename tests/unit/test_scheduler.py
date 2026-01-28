from unittest.mock import MagicMock, patch

from flight_controll.scheduler import scheduler as scheduler_module


class DummyApp:
    def __init__(self):
        class Cfg:
            WEBCAL_SCHEDULER_DELAY_MINUTES = 1
        self.app_config = Cfg()
        self.config = {}


@patch.object(scheduler_module, 'scheduler')
def test_init_scheduler_initializes_and_starts(mock_scheduler):
    app = DummyApp()

    # Ensure init_app and start are callable and don't run real scheduler
    mock_scheduler.init_app = MagicMock()
    mock_scheduler.start = MagicMock()

    scheduler_module.init_scheduler(app)

    mock_scheduler.init_app.assert_called_once_with(app)
    mock_scheduler.start.assert_called_once()
