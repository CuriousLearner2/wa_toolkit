import logging

def get_logger(name="wa_toolkit"):
    """
    Returns a logger named 'wa_toolkit' or a sub-logger.
    Host applications can control verbosity via logging.getLogger("wa_toolkit").setLevel().
    """
    return logging.getLogger(name)

logger = get_logger()
