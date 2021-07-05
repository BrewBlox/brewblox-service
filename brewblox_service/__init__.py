import logging
import traceback


class DuplicateFilter(logging.Filter):
    """
    Logging filter to prevent long-running errors from flooding the log.
    When set, repeated log messages are blocked.
    This will not block alternating messages, and is module-specific.
    """

    def filter(self, record):
        current_log = (record.module, record.levelno, record.msg)
        if current_log != getattr(self, 'last_log', None):
            self.last_log = current_log
            return True
        return False


def brewblox_logger(name: str, dedupe=False):
    """
    Convenience function for creating a module-specific logger.
    """
    logger = logging.getLogger('...'+name[-27:] if len(name) > 30 else name)
    if dedupe:
        logger.addFilter(DuplicateFilter())
    return logger


def strex(ex: Exception, tb=False):
    """
    Generic formatter for exceptions.
    A formatted traceback is included if `tb=True`.
    """
    msg = f'{type(ex).__name__}({str(ex)})'
    if tb:
        trace = ''.join(traceback.format_exception(None, ex, ex.__traceback__))
        return f'{msg}\n\n{trace}'
    else:
        return msg
