"""Cryptographic utilities for hashing data."""

from typing import Union
import hashlib

def hash_sha256_bytes(data: Union[bytes, str]) -> bytes:
    """
    Hash data with SHA256 and return bytes.

    Args:
        data: Data to hash (string or bytes).

    Returns:
        SHA256 hash as bytes.
    """
    if isinstance(data, str):
        data = data.encode()
    return hashlib.sha256(data).digest()


def dighash(data: Union[bytes, str]) -> bytes:
    """Deprecated: use hash_sha256_bytes() instead."""
    return hash_sha256_bytes(data)
