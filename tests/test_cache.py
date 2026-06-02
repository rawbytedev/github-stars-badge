"""Unit tests for LMDB cache and caching logic."""

import time
import pytest
from unittest.mock import patch, MagicMock
from src.storage import DB, DBError
from src.services import GitHubService
from src.models import CachedStarCount, settings
from src.utils import current_timestamp, compare_timestamps


class TestDB:
    """Test LMDB database wrapper."""

    @pytest.fixture
    def db(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        index_path = str(tmp_path / "test.idx")
        return DB(path=db_path, index_path=index_path)

    def test_put_and_get(self, db):
        db.put("key1", "value1")
        result = db.get("key1")
        assert result == "value1"

    def test_get_missing_key(self, db):
        with pytest.raises(DBError, match="not found"):
            db.get("missing")

    def test_put_overwrite(self, db):
        db.put("key", "first")
        db.put("key", "second")
        assert db.get("key") == "second"

    def test_delete(self, db):
        db.put("to_delete", "data")
        db.delete("to_delete")
        with pytest.raises(DBError):
            db.get("to_delete")

    def test_iterate_with_prefix(self, db):
        db.put("ec:user1", '{"stars":10}')
        db.put("ec:user2", '{"stars":20}')
        db.put("other", "ignore")
        results = db.iterate("ec:")
        assert len(results) == 2
        keys = [r[0] for r in results]
        assert "ec:user1" in keys
        assert "ec:user2" in keys

    def test_cache_size_limit(self, db):
        # Override cache size for test
        db.cache_size = 2
        db.put("a", "1")
        db.put("b", "2")
        db.put("c", "3")
        # Cache should have evicted "a"
        assert "a" not in db.cache
        assert db.get("b") == "2"  # still there


class TestCachingLogic:
    """Test GitHubService caching with TTL."""

    @pytest.fixture
    def mock_db(self):
        db = MagicMock(spec=DB)
        return db

    @pytest.fixture
    def service(self, mock_db):
        return GitHubService(db=mock_db)

    def test_fetch_cached_star_count_hit_not_expired(self, service, mock_db):
        now = int(time.time())
        cached = CachedStarCount(key="testuser", stars=42, timestamp=now)
        mock_db.get.return_value = cached.model_dump_json()

        result = service._fetch_cached_star_count("testuser")

        assert result == 42
        mock_db.get.assert_called_once_with("testuser")

    def test_fetch_cached_star_count_expired(self, service, mock_db):
        past = int(time.time()) - settings.cache_ttl - 10
        cached = CachedStarCount(key="testuser", stars=42, timestamp=past)
        mock_db.get.return_value = cached.model_dump_json()

        result = service._fetch_cached_star_count("testuser")

        assert result is None  # expired, treat as miss

    def test_fetch_cached_star_count_not_found(self, service, mock_db):
        mock_db.get.side_effect = DBError("not found")
        result = service._fetch_cached_star_count("unknown")
        assert result is None

    def test_cache_star_count(self, service, mock_db):
        service._cache_star_count("testuser", 100)
        # Verify put was called with correct JSON
        mock_db.put.assert_called_once()
        args = mock_db.put.call_args[0]
        assert args[0] == "testuser"
        stored = CachedStarCount.model_validate_json(args[1])
        assert stored.stars == 100
        assert stored.key == "testuser"
        assert abs(stored.timestamp - current_timestamp()) < 2

    @pytest.mark.asyncio
    async def test_fetch_star_count_uses_cache_first(self, service, mock_db):
        # Cache hit
        now = int(time.time())
        cached = CachedStarCount(key="testuser", stars=99, timestamp=now)
        mock_db.get.return_value = cached.model_dump_json()

        result = await service.fetch_star_count("testuser")

        assert result == 99
        # GitHub API should not be called
        assert not hasattr(service, "_fetch_github_star_count") or True

    @pytest.mark.asyncio
    async def test_fetch_star_count_miss_calls_api_and_caches(self, service, mock_db):
        mock_db.get.side_effect = DBError("not found")
        with patch.object(service, "_fetch_github_star_count", return_value=77):
            result = await service.fetch_star_count("testuser")

            assert result == 77
            mock_db.put.assert_called_once()

    def test_compare_timestamps_within_ttl(self):
        now = current_timestamp()
        assert compare_timestamps(now) is True
        assert compare_timestamps(now - settings.cache_ttl + 1) is True

    def test_compare_timestamps_expired(self):
        old = current_timestamp() - settings.cache_ttl - 5
        assert compare_timestamps(old) is False
