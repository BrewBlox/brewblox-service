import logging


def brewblox_logger(name):
    return logging.getLogger('...'+name[-27:] if len(name) > 30 else name)
