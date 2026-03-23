"""dbmanager.py - Singleton manager for the LMDB database instance."""

from typing import Optional
from storage import DB

DB_PATH = "store.db"
INDEX_PATH = "index.db"

class DBManager:
    """Singleton manager for the LMDB database instance."""

    _instance: Optional[DB] = None

    @classmethod
    def get_db(cls) -> DB:
        """Get the shared database instance (singleton pattern for LMDB)."""
        if cls._instance is None:
            cls._instance = DB(path=DB_PATH, index_path=INDEX_PATH)
        return cls._instance

    @classmethod
    def close_db(cls):
        """Close the database instance if it exists."""
        if cls._instance is not None:
            cls._instance.close()
            cls._instance = None
