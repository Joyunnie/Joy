import logging
from logging.handlers import RotatingFileHandler


def setup_logging(
    log_file: str | None = None,
    max_bytes: int = 10485760,
    backup_count: int = 5,
) -> logging.Logger:
    logger = logging.getLogger("agent1")
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s"
    )

    # Console handler
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)

    # File handler (optional)
    if log_file:
        file_handler = RotatingFileHandler(
            log_file, maxBytes=max_bytes, backupCount=backup_count
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
