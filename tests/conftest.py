"""
Pytest configuration and shared fixtures for GitHub Stars Badge API tests.
"""
import pytest
import tempfile
import os
import sys
from unittest.mock import Mock, AsyncMock
from fastapi.testclient import TestClient

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from main import app
from storage import DB
from services import GitHubService


@pytest.fixture
def temp_db_path():
    """Create a temporary database path for testing."""
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test.db")
    yield db_path
    # Cleanup
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def mock_db(temp_db_path):
    """Create a mock database instance for testing."""
    # Ensure the directory exists
    os.makedirs(os.path.dirname(temp_db_path), exist_ok=True)
    return DB(path=temp_db_path, index_path=temp_db_path + ".index")


@pytest.fixture
def mock_github_service(mock_db):
    """Create a mock GitHub service with injected database."""
    return GitHubService(mock_db)


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def mock_httpx_client():
    """Mock httpx AsyncClient for GitHub API calls."""
    mock_client = AsyncMock()
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {"stargazers_count": 100},
        {"stargazers_count": 200},
    ]
    mock_client.get.return_value.__aenter__.return_value = mock_response
    mock_client.get.return_value.__aexit__.return_value = None
    return mock_client


@pytest.fixture
def sample_github_user_response():
    """Sample GitHub API response for user repositories."""
    return [
        {"name": "repo1", "stargazers_count": 50},
        {"name": "repo2", "stargazers_count": 75},
        {"name": "repo3", "stargazers_count": 25},
    ]


@pytest.fixture
def sample_github_repo_response():
    """Sample GitHub API response for single repository."""
    return {"name": "test-repo", "stargazers_count": 150}