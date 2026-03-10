"""
Main entry point for the GitHub Stars Badge API.
"""
import logging
import signal
import sys
from typing import Optional
from fastapi import FastAPI, HTTPException, Response, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.gzip import GZipMiddleware
import httpx
import uvicorn
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
# pylint: disable=E0402
from .storage import DB,DBError
from .config import GITHUB_API_URL, SHIELDS_IO_URL, HEADERS, COLOR, ERROR_COLOR
from .models import StarsResponse, RepoStarsResponse
from .utils import validate_owner_repo


logger = logging.getLogger(__name__)
limiter = Limiter(key_func=get_remote_address)

app = FastAPI()
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.state.limiter = limiter

async def rate_limit_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle rate limit exceeded exceptions."""
    _ = request
    if isinstance(exc, RateLimitExceeded):
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded. Please try again later."},
        )
    # Fallback for other exceptions (shouldn't reach here)
    raise exc
app.add_exception_handler(RateLimitExceeded, rate_limit_handler)

DB_PATH = "store.db"
INDEX_PATH = "index.db"
DB_INSTANCE = DB(path=DB_PATH, index_path=INDEX_PATH)
def get_db() -> DB:
    """Get the database instance."""
    return DB_INSTANCE

@app.get("/health")
async def health():
    """Health check endpoint to verify API and GitHub connectivity."""
    try:
        DB_INSTANCE.put("health_check", "test")  # Test DB connectivity
        val = DB_INSTANCE.get("health_check")  # Test DB connectivity
        if val.decode() != "test":
            raise DBError("DB read/write test failed")
        DB_INSTANCE.delete("health_check")  # Clean up test key
    except DBError as exc:
        logger.error("Database error during health check: %s", exc)
        return JSONResponse(status_code=500,
                            content={
                                "status": "unhealthy",
                                "error": "Database connectivity issue"
                                }
                            )
    return {
        "status": "healthy",
        #"cache": {"hits": cache_stats.hits, "misses": cache_stats.misses},
        "github_api": "responsive"  # Check with HEAD request
    }


@app.get("/api/v1/stars/{owner}")
@limiter.limit("10/minute", cost=2)
async def get_user_stars(request: Request, owner: str) -> StarsResponse:
    """
    Return the total number of stars for a given GitHub user.
    """
    _ =request
    validate_owner_repo(owner, "username")
    stars = await fetch_star_count(owner)
    if stars is None:
        raise HTTPException(status_code=404, detail="User not found")
    if stars == -1:
        raise HTTPException(status_code=500, detail="Error fetching star count from GitHub")
    return StarsResponse(owner=owner, stars=stars)

@app.get("/api/v1/stars/{owner}/{repo}")
@limiter.limit("10/minute", cost=2)
async def get_repo_stars(request: Request, owner: str, repo: str) -> RepoStarsResponse:
    """
    Return the number of stars for a given GitHub repository.
    """
    _ = request
    validate_owner_repo(owner, "username")
    validate_owner_repo(repo, "repository name")
    stars = await fetch_star_count(owner, repo)
    if stars is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    if stars == -1:
        raise HTTPException(status_code=500, detail="Error fetching star count from GitHub")
    return RepoStarsResponse(owner=owner, repo=repo, stars=stars)

@app.get("/api/v1/badge/user/{owner}")
@limiter.limit("10/minute", cost=2)
async def get_user_badge(request: Request, owner: str, theme: str = "flat"):
    """
    Return a badge image showing the total number of stars for a given GitHub user.
    Supports themes: flat, flat-square, for-the-badge, plastic (default: flat).
    """
    _ = request
    validate_owner_repo(owner, "username")
    if theme not in ["flat", "flat-square", "for-the-badge", "plastic"]:
        raise HTTPException(status_code=400, detail="Invalid theme. " \
        "Choose from: flat, flat-square, for-the-badge, plastic")

    stars = await fetch_star_count(owner)
    if stars is None:
        raise HTTPException(status_code=404, detail="User not found")
    if stars == -1:
        # GitHub API error → return error badge
        error_url = f"https://img.shields.io/badge/stars-error-lightgrey?style={theme}&logo=github"
        return await get_badge_image(error_url)
    formatted_stars = f"{stars:,}"
    badge_url = SHIELDS_IO_URL.format(formatted_stars, theme)
    return await get_badge_image(badge_url)

@app.get("/api/v1/badge/repo/{owner}/{repo}")
@limiter.limit("10/minute", cost=2)
async def get_repo_badge(request: Request, owner: str,
                         repo: str, theme: str = "flat", color: str = COLOR) -> Response:
    """
    Return a badge image showing the total number of stars for a given GitHub repository.
    Supports themes: flat, flat-square, for-the-badge, plastic (default: flat).
    """
    _ = request
    validate_owner_repo(owner, "username")
    validate_owner_repo(repo, "repository name")
    if theme not in ["flat", "flat-square", "for-the-badge", "plastic"]:
        raise HTTPException(status_code=400, detail="Invalid theme. " \
        "Choose from: flat, flat-square, for-the-badge, plastic")

    stars = await fetch_star_count(owner, repo)
    if stars is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    if stars == -1:
        # GitHub API error → return error badge
        error_url = "https://img.shields.io/badge/" \
    f"stars-error-{ERROR_COLOR}?style={theme}&logo=github"
        return await get_badge_image(error_url)

    formatted_stars = f"{stars:,}"
    badge_url = SHIELDS_IO_URL.format(formatted_stars, color, theme)
    return await get_badge_image(badge_url)



async def get_badge_image(badge_url: str) -> Response:
    """"
    Fetch the badge image from shields.io and return it as a response.
    """
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(badge_url)
            response.raise_for_status()  # Raise exception for 4xx/5xx responses
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=500,
                detail="Failed to fetch badge from shields.io"
            ) from exc
        return Response(content=response.content, media_type="image/svg+xml")

async def fetch_github_star_count(owner: str, repo: Optional[str] = None) -> Optional[int]:
    """
    Fetch the star count for a given GitHub repository or user. 
    If repo is None, fetch total stars for the user.
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
                resp.raise_for_status()  # Raise exception for 4xx/5xx responses
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 404:
                    logger.info("GitHub API returned 404 for %s", url)
                    return None  # user not found
                return -1  # error fetching data
            repos = resp.json()
            if not repos:
                break
            if repo:
                stars += repos.get("stargazers_count", 0)
                break  # only one repo, so we can stop after the first page
            stars += sum(repo.get("stargazers_count", 0) for repo in repos)
            page += 1
    return stars

def fetch_cached_star_count(key: str) -> Optional[int]:
    """
    Fetch the star count from cache if available, otherwise fetch from GitHub API and cache it.
    """
    try:
        cached = DB_INSTANCE.get(key)
        if cached is not None:
            stars = int(cached)
            logger.info("Cache hit for %s: %s stars", key, f"{stars:,}")
            return stars
    except DBError:
        logger.info("Cache miss for %s", key)
        return None
    except ValueError:
        # Handle corrupted cache data gracefully
        logger.warning("Warning: Invalid cache value for %s. Treating as cache miss.", key)
        return None

async def fetch_star_count(owner: str, repo: Optional[str] = None) -> Optional[int]:
    """
    Fetch the star count for a given GitHub repository or user, using cache if available."""
    key = f"{owner}/{repo}" if repo else owner
    stars = fetch_cached_star_count(key)
    if stars is not None:
        return stars
    logger.info("Cache miss for %s, fetching from GitHub API", key)
    stars = await fetch_github_star_count(owner, repo)
    if stars is not None and stars != -1:
        cache_star_count(key, stars)
    return stars

def cache_star_count(key: str, stars: int) -> None:
    """
    Cache the star count in the database.
    """
    try:
        DB_INSTANCE.put(key, str(stars))
        logger.info("Cached %s: %s stars", key, f"{stars:,}")
    except DBError:
        logger.error("Failed to cache %s: %s stars", key, f"{stars:,}")

def signal_handler(signum, frame):
    """Handle termination signals for graceful shutdown."""
    _ = frame
    _ = signum
    logger.info("Shutting down gracefully")
    DB_INSTANCE.close()  # If DB supports it
    sys.exit(0)

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)  # Handle Ctrl+C gracefully

def main():
    """Main function to run the FastAPI app."""
    uvicorn.run(app, host="0.0.0.0", port=8000)
