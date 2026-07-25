import time
import logging
from functools import wraps
from django.db import OperationalError

logger = logging.getLogger(__name__)

def retry_on_db_error(max_retries=3, backoff=2.0):
    """Decorator to retry operations on transient DB errors."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except OperationalError as e:
                    if attempt < max_retries - 1:
                        sleep_time = backoff ** attempt
                        logger.warning(
                            f"DB error in {func.__name__}, retrying in {sleep_time}s",
                            extra={
                                "function": func.__name__,
                                "attempt": attempt + 1,
                                "error": str(e),
                            }
                        )
                        time.sleep(sleep_time)
                    else:
                        logger.error(
                            f"DB error in {func.__name__}, max retries exhausted",
                            extra={
                                "function": func.__name__,
                                "error": str(e),
                                "max_attempts": max_retries
                            }
                        )
                        raise
        return wrapper
    return decorator
