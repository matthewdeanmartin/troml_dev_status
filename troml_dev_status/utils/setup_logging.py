import logging

logger = logging.getLogger(__name__)


def configure_logging(
    level: int = logging.INFO, app_name: str = "troml_dev_status"
) -> None:
    """
    Configure logging for the application.

    - Suppresses noisy logs from third-party libraries.
    - Only the given app's logger will log at the requested level.
    - Defaults to WARNING for all other libraries.

    Args:
        level: The log level for your app (e.g. logging.DEBUG, logging.INFO).
        app_name: The name of your application's logger.
    """
    # Clear existing handlers to avoid duplicate logs
    root_logger = logging.getLogger()
    for h in root_logger.handlers[:]:
        root_logger.removeHandler(h)

    # Set up a simple console handler
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    handler.setFormatter(formatter)

    root_logger.addHandler(handler)

    # By default, root only shows warnings and above
    root_logger.setLevel(logging.WARNING)

    # Set your app's logger to the requested level
    app_logger = logging.getLogger(app_name)
    app_logger.setLevel(level)

    # Optionally silence specific noisy libraries even harder
    for noisy in ["httpx", "urllib3", "asyncio"]:
        logging.getLogger(noisy).setLevel(logging.WARNING)
