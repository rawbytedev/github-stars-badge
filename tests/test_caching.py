"""
Tests for caching functionality in GitHub Stars Badge API.
"""
import time
from unittest.mock import patch
import pytest
from src import GitHubService, CachedStarCount
from storage import DBError


class TestCaching:
    """Test caching functionality."""

    def test_cache_hit(self, mock_db):
        """Test that cached values are returned correctly."""
        # Setup
        service = GitHubService(mock_db)
        key = "testuser"
        expected_stars = 42

        # Pre-populate cache with proper CachedStarCount JSON
        cached_data = CachedStarCount(key=key, stars=expected_stars, timestamp=int(time.time()))
        mock_db.put(key, cached_data.model_dump_json())

        # Test
        result = service._fetch_cached_star_count(key)

        # Assert
        assert result == expected_stars

    def test_cache_miss(self, mock_db):
        """Test that None is returned when key is not in cache."""
        service = GitHubService(mock_db)
        key = "nonexistent"

        result = service._fetch_cached_star_count(key)

        assert result is None

    def test_corrupted_cache_value(self, mock_db):
        """Test handling of corrupted cache values."""
        service = GitHubService(mock_db)
        key = "corrupted"

        # Put invalid data in cache
        mock_db.put(key, "not_a_number")

        result = service._fetch_cached_star_count(key)

        # Should treat as cache miss
        assert result is None

    def test_cache_storage(self, mock_db):
        """Test that values are properly stored in cache."""
        service = GitHubService(mock_db)
        key = "store_test"
        stars = 123

        # Store value
        service._cache_star_count(key, stars)

        # Retrieve and verify
        result = service._fetch_cached_star_count(key)
        assert result == stars

    def test_db_error_handling(self, mock_db):
        """Test that DB errors are handled gracefully."""
        service = GitHubService(mock_db)
        key = "error_test"

        # Mock DB to raise error
        with patch.object(
            mock_db, 'get', side_effect=DBError("Value for key b'error_test' not found")):
            with pytest.raises(DBError, match="Value for key b'error_test' not found"):
                mock_db.get(key)
            result = service._fetch_cached_star_count(key)

        # Should return None on DB error
        assert result is None

    @pytest.mark.asyncio
    async def test_full_cache_workflow(self, mock_db):
        """Test the complete cache workflow with GitHub API fallback."""
        service = GitHubService(mock_db)

        # Mock the GitHub API call
        with patch.object(service, '_fetch_github_star_count', return_value=99) as mock_api:
            # First call should hit API and cache
            result1 = await service.fetch_star_count("testuser")
            assert result1 == 99
            mock_api.assert_called_once()

            # Second call should use cache
            mock_api.reset_mock()
            result2 = await service.fetch_star_count("testuser")
            assert result2 == 99
            mock_api.assert_not_called()  # Should not call API again

    def test_health_check_success(self, mock_db):
        """Test successful database health check."""
        service = GitHubService(mock_db)

        result = service.health_check()

        assert result["status"] == "healthy"
        assert result["database"] == "connected"

    def test_health_check_failure(self, mock_db):
        """Test database health check failure."""
        service = GitHubService(mock_db)
        key = "health_check"
        value = "test"
        # Mock DB to raise error
        with patch.object(
            mock_db, 'put',
            side_effect=DBError(f"Can't insert item: {key}:{value}")):
            result = service.health_check()  # This should handle the error and return unhealthy status

        assert result["status"] == "unhealthy"
        assert result["database"] == "error"
        assert "error" in result
