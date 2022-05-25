import logging

logger_level = logging.DEBUG


def logger(logger_name="reports"):
    log_format = "%(asctime)s api=%(name)s.%(funcName)s [level=%(levelname)-7s]: %(message)s"

    _logger = logging.getLogger(logger_name)
    _logger.propagate = False
    _logger.setLevel(logger_level)
    con_handler = logging.StreamHandler()
    con_handler.setLevel(logger_level)
    formatter = logging.Formatter(log_format)

    # stdout
    con_handler.setFormatter(formatter)
    if not _logger.handlers:
        _logger.addHandler(con_handler)

    # Return
    return _logger
