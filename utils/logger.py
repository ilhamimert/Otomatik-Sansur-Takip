import sys
from loguru import logger


def setup_logger(log_file: str = "data/app.log"):
    logger.remove()
    logger.add(sys.stderr, level="DEBUG",
               format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}")
    logger.add(log_file, level="DEBUG", rotation="10 MB", retention="7 days",
               format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{line} | {message}")
    return logger
