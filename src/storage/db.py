"""
Wrapper around lmdb for storage(store + index)
"""

from collections import OrderedDict
from typing import Optional, Union
import lmdb as tool
from .hashcrypto import dighash

CACHESIZE = 30

class DBError(Exception):
    """
    Error class for DB
    """

class DB:
    """
    DB wrapper around lmdb

    :var Returns: Description
    :var prefix_bytes: Description
    :vartype prefix_bytes: Any
    """
    
    def __init__(self, path="store.db", index_path="index.db", max_dbs=2):
        """
        Initialize the wrapper
        
        :param self: Description
        :param path: Path for store
        :param index_path: Path for index
        :param max_dbs: Max number of db
        """
        self.cache = OrderedDict()
        self.cache_size = CACHESIZE
        self.db = tool.open(path, max_dbs=max_dbs)
        self.index = tool.open(index_path, max_dbs=max_dbs)

    def _cache_set(self, key, value):
        if len(self.cache) >= self.cache_size:
            self.cache.popitem(last=False)
        self.cache[key] = value

    def get(self, key:Union[bytes,str]):
        """
        Retrieve the value using a key from db
        
        :param self: Description
        :param key: key to retrieve
        """
        if not key:
            raise DBError("Key can't be empty")
        key ,_=self._encode_key_value(key)
        if key in self.cache:
            return self.cache[key]
        with self.db.begin(write=False) as txn:
            hash_key = dighash(key)
            val = txn.get(hash_key)
            if val is None:
                raise DBError(f"Value for key {key} not found")
            decoded = val.decode()
            self._cache_set(key, decoded)
            return decoded

    def put(self, key:Union[bytes,str], value:Optional[Union[bytes,str]]):
        """
        Stores a value into DB using specified key
        replaces a value if the key is already present

        :param self: Description
        :param key: key to use
        :param value: value to store
        """
        if not key:
            raise DBError("Key can't be empty")
        if not value:
            raise DBError("Value can't be empty")
        key ,value = self._encode_key_value(key, value)
        if value is None:
            raise DBError("Value can't be empty")
        if key is None:
            raise DBError("Key can't be empty")
        self._cache_set(key, value)

        hash_key = dighash(key)
        try:
            with self.db.begin(write=True) as txn:
                txn.put(hash_key, value)
            with self.index.begin(write=True) as txn:
                txn.put(key, hash_key)
        except Exception as e:
            raise DBError(f"Can't insert item: {key}:{value}") from e

    def _encode_key_value(self,key:Union[bytes,str],
                          value:Optional[Union[bytes,str]]=None) -> tuple[bytes,Optional[bytes]]:
        if key is not None:
            if isinstance(key, str):
                key = key.encode()
        if value is not None:
            if isinstance(value, str):
                value = value.encode()
        return (key, value)

    def iterate(self, prefix: str):
        """
        Iterate over all keys in the index database with a given prefix (e.g. 'ec:').

        Returns:
            prefix_bytes = prefix.encode()  # LMDB keys must be bytes, so encode the prefix
        """
        results = []
        with self.index.begin(write=False) as txn:
            cursor = txn.cursor()
            prefix_bytes = prefix.encode()
            if cursor.set_range(prefix_bytes):
                with self.db.begin(write=False) as dtxn:
                    # iterate from the current cursor position and
                    # stop when keys no longer match the prefix
                    for k, v in cursor:
                        if not k.startswith(prefix_bytes):
                            break
                        # v is the hash_key, fetch from main DB
                        val = dtxn.get(v)
                        if val:
                            # Decode key and value before appending for clarity
                            decoded_key = k.decode()
                            decoded_val = val.decode()
                            results.append((decoded_key, decoded_val))
        return results

    def delete(self, key:Union[bytes,str]):
        """
        Deletes a key from the DB and index
        
        :param self: Description
        :param key: key to delete
        """
        if not key:
            raise DBError("Key can't be empty")
        key ,_=self._encode_key_value(key)
        hash_key = dighash(key)
        try:
            with self.db.begin(write=True) as txn:
                txn.delete(hash_key)
            with self.index.begin(write=True) as txn:
                txn.delete(key)
            if key in self.cache:
                del self.cache[key]
        except Exception as e:
            raise DBError(f"Can't delete item: {key}") from e

    def close(self):
        """
        closes the DB, clear caches
        
        :param self: Description
        """
        self.cache.clear()
        self.db.close()
        self.index.close()
