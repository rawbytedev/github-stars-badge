"""
Service layer for GitHub operations with dependency injection.
"""

import logging
from typing import Optional
import httpx

from .models import CachedStarCount
from .storage import DB, DBError
from .config import GITHUB_API_URL, HEADERS
from .utils import compare_timestamps, current_timestamp

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())


class GitHubService:
    """
    Service class for GitHub operations with injected database dependency.

    This class encapsulates all GitHub-related business logic and database operations,
    making it easier to test and maintain.
    """

    def __init__(self, db: DB, timeout: float = 10.0):
        """
        Initialize service with database dependency.

        Args:
            db: Database instance for caching operations
            timeout: Timeout for GitHub API requests (seconds)
        """
        self.db = db
        self.timeout = timeout

    async def fetch_star_count(
            self, owner: str, repo: Optional[str] = None
    ) -> Optional[int]:
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
                # Ensure cached is a string
                if isinstance(cached, bytes):
                    cached = cached.decode()
                stored = CachedStarCount.model_validate_json(cached)
                stars = stored.stars
                logger.info("Cache hit for %s: %s stars", key, f"{stars:,}")
                if not compare_timestamps(stored.timestamp):
                    logger.info("Cache TTL expired for %s", key)
                    return None
                return stars
        except DBError:
            logger.info("Cache miss for %s", key)
            return None
        except ValueError:
            logger.warning("Invalid cache value for %s. Treating as cache miss.", key)
            return None
        # #pylint: disable=broad-exception-caught
        except Exception as e:
            logger.error("Unexpected error fetching from cache for %s: %s", key, e)
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
            stored = CachedStarCount(
                key=key, stars=stars, timestamp=current_timestamp()
            )

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

        async with httpx.AsyncClient() as client:
            try:
                if repo:
                    # Single repository: fetch once, no pagination needed
                    resp = await client.get(url, headers=HEADERS, timeout=10)
                    resp.raise_for_status()
                    repo_data = resp.json()
                    stars = repo_data.get("stargazers_count", 0)
                else:
                    params = {"page": page, "per_page": per_page}
                    # User repositories: paginate through all repos
                    while True:
                        resp = await client.get(
                            url, headers=HEADERS, params=params, timeout=10
                        )
                        resp.raise_for_status()
                        repos = resp.json()
                        if not repos:
                            break
                        stars += sum(r.get("stargazers_count", 0) for r in repos)
                        page += 1
                        params["page"] = page
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 404:
                    logger.info("GitHub API returned 404 for %s", url)
                    return None
            except httpx.RequestError as exc:
                logger.info("GitHub API request error for %s: %s", url, exc)
                return -1
            #pylint: disable=broad-exception-caught
            except Exception as exc:
                logger.error("Unexpected error fetching from GitHub API for %s: %s", url, exc)
                return -1
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
            logger.info("Performing health check: testing DB connectivity")
            self.db.put(test_key, "test")
            logger.info("DB put successful for health check key")
            val = self.db.get(test_key)
            if val.decode() != "test":
                raise DBError("DB read/write test failed")
            self.db.delete(test_key)
            logger.info("DB delete successful for health check key")

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
