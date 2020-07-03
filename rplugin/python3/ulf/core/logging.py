from .typing import Any
import traceback
import logging
import sys


log_debug = False
log_exceptions = True
log_file = None
logger = None


def set_log_file(file: str) -> None:
    if file is None:
        return
    global log_file
    log_file = file
    setup_log()


def setup_log() -> None:
    global logger
    logger = logging.getLogger('ULF_LOG')
    logger.setLevel(logging.DEBUG)
    if log_file:
        handler = logging.FileHandler(log_file)
    else:
        handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)


def set_debug_logging(logging_enabled: bool) -> None:
    global log_debug
    log_debug = logging_enabled


def set_exception_logging(logging_enabled: bool) -> None:
    global log_exceptions
    log_exceptions = logging_enabled


def debug(*args: Any) -> None:
    """Print args to the console if the "debug" setting is True."""
    if logger is not None and log_debug:
        printf(*args)


def exception_log(message: str, ex: Exception) -> None:
    if logger is not None and log_exceptions:
        logger.error(message)
        ex_traceback = ex.__traceback__
        logger.debug(''.join(traceback.format_exception(ex.__class__, ex, ex_traceback)))


def printf(*args: Any, prefix: str = 'LSP') -> None:
    """Print args to the console, prefixed by the plugin name."""
    if logger is not None:
        logger.debug(*args)
