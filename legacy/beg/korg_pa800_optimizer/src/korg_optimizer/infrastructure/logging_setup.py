"""Logging configuration.

Logs import, analysis, mapping, optimization, validation, errors,
warnings, and decisions (per the project master spec's Logging
section) without persisting file contents or other unnecessary
sensitive data -- only structural metadata (paths, hashes, counts).

Owning vertical: A.
"""

from __future__ import annotations

import logging

LOGGER_NAME = "korg_optimizer"


def configure_logging(level: int = logging.INFO) -> logging.Logger:
    """Configure and return the package-level logger. Idempotent --
    calling this more than once does not add duplicate handlers.
    """
    logger = logging.getLogger(LOGGER_NAME)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
        logger.addHandler(handler)
    logger.setLevel(level)
    return logger


def get_logger() -> logging.Logger:
    """Return the package-level logger, configuring it with defaults
    on first use.
    """
    logger = logging.getLogger(LOGGER_NAME)
    if not logger.handlers:
        configure_logging()
    return logger
