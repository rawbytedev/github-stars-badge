"""
Utility functions for the GitHub Stars Badge API.
Includes input validation and other helper functions.
"""
import re
from fastapi import HTTPException

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
