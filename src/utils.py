"""
Utility functions for the GitHub Stars Badge API.
Includes input validation and other helper functions.
"""
import re
import time
from fastapi import HTTPException
from models import settings

def validate_owner_repo(value: str, field: str) -> str:

    """
    Validate the owner and repo parameters to prevent injection attacks.
    Only allow alphanumeric characters, hyphens, underscores, and periods.
    """
    if not re.match(r'^[a-zA-Z0-9\-_\.]+$', value):
        raise HTTPException(400,
                             f"Invalid {field}:"\
                            "only alphanumeric, hyphens, underscores, periods allowed")
    return value

def current_timestamp() -> int:
    """
    Get the current timestamp in seconds.
    """
    return int(time.time())

def compare_timestamps(ts1: int) -> bool:
    """
    Compare current with ts1 timestamps and return True if it is within the cache TTL.
    """
    return abs(ts1 - current_timestamp()) < settings.cache_ttl
