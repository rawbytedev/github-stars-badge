"""
This module provides storage-related functionality for the GitHub Stars Badge application.
It includes the database implementation and hashing utilities.
"""
from .db import DB, DBError
from .hashcrypto import dighash

__all__ = ["DB", "dighash", "DBError"]
