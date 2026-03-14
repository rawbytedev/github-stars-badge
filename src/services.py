"""
Service layer for GitHub operations with dependency injection.
"""
import logging
from typing import Optional
import httpx

from models import CachedStarCount
from .storage import DB, DBError
# pylint: disable=E0402
from .config import GITHUB_API_URL,HEADERS
from .utils import current_timestamp

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())


class GitHubService:
    """
    Service class for GitHub operations with injected database dependency.

    This class encapsulates all GitHub-related business logic and database operations,
    making it easier to test and maintain.
    """

    def __init__(self, db: DB):
        """
        Initialize service with database dependency.

        Args:
            db: Database instance for caching operations
        """
        self.db = db

    async def fetch_star_count(self, owner: str, repo: Optional[str] = None) -> Optional[int]:
        """
        Fetch the star count for a user or repository, using cache when available.

        Args:
            owner: GitHub username
            repo: Repository name (optional, if None fetches total user stars)

        Returns:
            Star count, None if not found, -1 on error
        """
        key = f"{owner}/{repo}" if repo else owner
        stars = self._fetch_cached_star_count(key)

        if stars is not None:
            return stars

        logger.info("Cache miss for %s, fetching from GitHub API", key)
        stars = await self._fetch_github_star_count(owner, repo)

        if stars is not None and stars != -1:
            self._cache_star_count(key, stars)
        return stars

    def _fetch_cached_star_count(self, key: str) -> Optional[int]:
        """
        Fetch star count from cache.

        Args:
            key: Cache key (owner or owner/repo)

        Returns:
            Cached star count or None
        """
        try:
            cached = self.db.get(key)
            if cached is not None:
                stored = CachedStarCount.model_validate_json(cached)
                stars = stored.stars
                logger.info("Cache hit for %s: %s stars", key, f"{stars:,}")
                return stars
        except DBError:
            logger.info("Cache miss for %s", key)
            return None
        except ValueError:
            logger.warning("Invalid cache value for %s. Treating as cache miss.", key)
            return None

        return None

    def _cache_star_count(self, key: str, stars: int) -> None:
        """
        Cache star count in database.

        Args:
            key: Cache key
            stars: Star count to cache
        """
        try:
            stored = CachedStarCount(key=key, stars=stars, timestamp=current_timestamp())

            self.db.put(key, stored.model_dump_json())
            logger.info("Cached %s: %s stars", key, f"{stars:,}")
        except DBError as e:
            logger.error("Failed to cache %s: %s", key, e)

    async def _fetch_github_star_count(
            self, owner: str, repo: Optional[str] = None
            ) -> Optional[int]:
        """
        Fetch star count directly from GitHub API.

        Args:
            owner: GitHub username
            repo: Repository name (optional)

        Returns:
            Star count from GitHub API
        """
        stars = 0
        page = 1
        per_page = 100

        if repo:
            url = GITHUB_API_URL.format("repos", owner, repo)
        else:
            url = GITHUB_API_URL.format("users", owner, "repos")

        logger.info("Fetching from GitHub API: %s (page %d)", url, page)

        params = {"page": page, "per_page": per_page}

        async with httpx.AsyncClient() as client:
            while True:
                try:
                    resp = await client.get(url, headers=HEADERS, params=params, timeout=10)
                    resp.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code == 404:
                        logger.info("GitHub API returned 404 for %s", url)
                        return None
                    return -1

                repos = resp.json()
                if not repos:
                    break

                if repo:
                    stars += repos.get("stargazers_count", 0)
                    break
                stars += sum(repo.get("stargazers_count", 0) for repo in repos)
                page += 1
                params["page"] = page
        return stars

    def health_check(self) -> dict:
        """
        Perform database health check.

        Returns:
            Health status dictionary
        """
        try:
            # Test database connectivity
            test_key = "health_check"
            self.db.put(test_key, "test")
            val = self.db.get(test_key)
            if val.decode() != "test":
                raise DBError("DB read/write test failed")
            self.db.delete(test_key)

            return {
                "status": "healthy",
                "database": "connected"
            }
        except DBError as exc:
            logger.error("Database health check failed: %s", exc)
            return {
                "status": "unhealthy",
                "database": "error",
                "error": str(exc)
            }
