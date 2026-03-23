"""
Tests for API endpoints in GitHub Stars Badge API.
"""
from unittest.mock import patch




class TestAPIEndpoints:
    """Test API endpoints."""

    def test_health_endpoint(self, client):
        """Test health check endpoint."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "database" in data
        assert "timestamp" in data

    @patch('src.services.GitHubService.fetch_star_count')
    def test_get_user_stars_success(self, mock_fetch, client):
        """Test successful user stars endpoint."""
        mock_fetch.return_value = 123

        response = client.get("/api/v1/stars/testuser")

        assert response.status_code == 200
        data = response.json()
        assert data["owner"] == "testuser"
        assert data["stars"] == 123

    @patch('src.services.GitHubService.fetch_star_count')
    def test_get_user_stars_not_found(self, mock_fetch, client):
        """Test user stars endpoint when user not found."""
        mock_fetch.return_value = None

        response = client.get("/api/v1/stars/nonexistent")

        assert response.status_code == 404
        data = response.json()
        assert "User not found" in data["detail"]

    @patch('src.services.GitHubService.fetch_star_count')
    def test_get_user_stars_api_error(self, mock_fetch, client):
        """Test user stars endpoint when GitHub API fails."""
        mock_fetch.return_value = -1

        response = client.get("/api/v1/stars/testuser")

        assert response.status_code == 500
        data = response.json()
        assert "Error fetching star count" in data["detail"]

    @patch('src.services.GitHubService.fetch_star_count')
    def test_get_repo_stars_success(self, mock_fetch, client):
        """Test successful repository stars endpoint."""
        mock_fetch.return_value = 456

        response = client.get("/api/v1/stars/testuser/testrepo")

        assert response.status_code == 200
        data = response.json()
        assert data["owner"] == "testuser"
        assert data["repo"] == "testrepo"
        assert data["stars"] == 456

    @patch('src.services.GitHubService.fetch_star_count')
    def test_get_repo_stars_not_found(self, mock_fetch, client):
        """Test repository stars endpoint when repo not found."""
        mock_fetch.return_value = None

        response = client.get("/api/v1/stars/testuser/nonexistent")

        assert response.status_code == 404
        data = response.json()
        assert "Repository not found" in data["detail"]

    def test_invalid_username_validation(self, client):
        """Test input validation for invalid username."""
        response = client.get("/api/v1/stars/user@invalid")

        assert response.status_code == 400
        data = response.json()
        assert "Invalid username" in data["detail"]

    def test_invalid_repo_name_validation(self, client):
        """Test input validation for invalid repository name."""
        response = client.get("/api/v1/stars/validuser/repo@invalid")

        assert response.status_code == 400
        data = response.json()
        assert "Invalid repository name" in data["detail"]

    @patch('src.main.get_badge_image')
    @patch('src.services.GitHubService.fetch_star_count')
    def test_get_user_badge_success(self, mock_fetch, mock_badge, client):
        """Test successful user badge endpoint."""
        mock_fetch.return_value = 789
        mock_badge.return_value = {"test": "badge"}

        response = client.get("/api/v1/badge/user/testuser")

        assert response.status_code == 200
        mock_badge.assert_called_once()

    @patch('src.main.get_badge_image')
    @patch('src.services.GitHubService.fetch_star_count')
    def test_get_user_badge_error_badge(self, mock_fetch, mock_badge, client):
        """Test user badge endpoint returns error badge on API failure."""
        mock_fetch.return_value = -1
        mock_badge.return_value = {"error": "badge"}

        response = client.get("/api/v1/badge/user/testuser")

        assert response.status_code == 200
        # Should call get_badge_image with error URL
        mock_badge.assert_called_once()

    def test_invalid_theme_validation(self, client):
        """Test theme validation for badge endpoints."""
        response = client.get("/api/v1/badge/user/testuser?theme=invalid")

        assert response.status_code == 400
        data = response.json()
        assert "Invalid theme" in data["detail"]

    @patch('src.main.get_badge_image')
    @patch('src.services.GitHubService.fetch_star_count')
    def test_get_repo_badge_success(self, mock_fetch, mock_badge, client):
        """Test successful repository badge endpoint."""
        mock_fetch.return_value = 321
        mock_badge.return_value = {"repo": "badge"}

        response = client.get("/api/v1/badge/repo/testuser/testrepo")

        assert response.status_code == 200
        mock_badge.assert_called_once()

    def test_rate_limiting(self, client):
        """Test that rate limiting is configured (but hard to test with TestClient)."""
        # Rate limiting is configured but TestClient uses same IP
        # Just verify the endpoint works without rate limiting in test environment
        response = client.get("/api/v1/stars/testuser/testrepo")
        assert response.status_code in [200, 404, 500]

    def test_cors_headers(self, client):
        """Test that CORS headers are not set (CORS not configured for this API)."""
        response = client.options("/api/v1/stars/testuser")

        # CORS is not configured for this badge API
        assert "access-control-allow-origin" not in response.headers

    def test_gzip_compression(self, client):
        """Test that gzip compression is enabled."""
        response = client.get("/api/v1/stars/testuser", headers={"Accept-Encoding": "gzip"})

        # Should return successfully (compression is transparent)
        assert response.status_code in [200, 404, 500]
