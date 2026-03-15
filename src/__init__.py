"""GitHub Stars Badge API - A FastAPI application to fetch GitHub star counts and generate badges.
This module serves as the entry point for the GitHub Stars Badge API application.
It imports the main FastAPI app and the GitHubService class, 
which contains the core logic for fetching star counts from GitHub. 
By importing these components here, 
we can easily access them when running the application or during testing."""
from .main import app, main
from .services import GitHubService
from .storage import DB, DBError
from .models import CachedStarCount

__all__ = ["app", "main", "GitHubService", "DB", "DBError", "CachedStarCount"]
