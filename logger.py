import logging
import os
import sys
from logging.handlers import TimedRotatingFileHandler, RotatingFileHandler

LOG_DIR = 'logs'
LOG_FILE_PATH = os.path.join(LOG_DIR, 'application.log')

os.makedirs(LOG_DIR, exist_ok=True)

time_format = "%Y-%m-%d %H:%M:%S"
FORMATTER = logging.Formatter(fmt='%(asctime)s — %(filename)s — %(lineno)d — %(levelname)s — %(message)s', datefmt=time_format)


def get_console_handler():
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(FORMATTER)
    console_handler.setLevel(logging.DEBUG)
    return console_handler


def get_file_handler():
    file_handler = RotatingFileHandler(LOG_FILE_PATH, maxBytes=1024*1024*5, backupCount=5, encoding='utf-8')
    file_handler.setFormatter(FORMATTER)
    file_handler.setLevel(logging.DEBUG)
    return file_handler


def get_logger(logger_name):
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(get_console_handler())
    logger.addHandler(get_file_handler())
    logger.propagate = False
    return logger
