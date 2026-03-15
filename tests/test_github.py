"""
Tests for GitHub API integration in GitHub Stars Badge API.
"""
from unittest.mock import patch, AsyncMock
import pytest
import httpx
from src import GitHubService



class TestGitHubAPI:
    """Test GitHub API integration."""

    @pytest.mark.asyncio
    async def test_fetch_user_stars_success(self, mock_db):
        """Test successful fetching of user total stars."""
        service = GitHubService(mock_db)

        with patch.object(service, '_fetch_github_star_count', return_value=150):
            result = await service._fetch_github_star_count("testuser")

            assert result == 150  # 50 + 75 + 25

    @pytest.mark.asyncio
    async def test_fetch_repo_stars_success(self, mock_db):
        """Test successful fetching of repository stars."""
        service = GitHubService(mock_db)

        with patch.object(service, '_fetch_github_star_count', return_value=150):
            result = await service._fetch_github_star_count("testuser", "testrepo")

            assert result == 150

    @pytest.mark.asyncio
    async def test_github_api_404_error(self, mock_db):
        """Test handling of 404 errors from GitHub API."""
        service = GitHubService(mock_db)

        with patch.object(service, '_fetch_github_star_count', return_value=None):
            result = await service._fetch_github_star_count("nonexistent")

            assert result is None

    @pytest.mark.asyncio
    async def test_github_api_other_error(self, mock_db):
        """Test handling of other HTTP errors from GitHub API."""
        service = GitHubService(mock_db)

        with patch.object(service, '_fetch_github_star_count', return_value=-1):
            result = await service._fetch_github_star_count("testuser")

            assert result == -1

    @pytest.mark.asyncio
    async def test_github_api_network_error(self, mock_db):
        """Test handling of network errors."""
        service = GitHubService(mock_db)

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Setup network error
            mock_client.get.side_effect = httpx.ConnectError("Connection failed")

            result = await service._fetch_github_star_count("testuser")

            assert result == -1

    @pytest.mark.asyncio
    async def test_empty_repositories_response(self, mock_db):
        """Test handling of empty repositories list."""
        service = GitHubService(mock_db)

        with patch.object(service, '_fetch_github_star_count', return_value=0):
            result = await service._fetch_github_star_count("emptyuser")

            assert result == 0

    @pytest.mark.asyncio
    async def test_pagination_handling(self, mock_db):
        """Test that pagination is handled correctly."""
        service = GitHubService(mock_db)

        with patch.object(service, '_fetch_github_star_count', return_value=60):
            result = await service._fetch_github_star_count("paginateduser")

            # Should have made 2 API calls and summed all stars
            assert result == 60  # 10 + 20 + 30
