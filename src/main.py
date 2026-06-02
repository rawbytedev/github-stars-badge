"""
Main entry point for the GitHub Stars Badge API.
"""

import json
import logging
import signal
import sys
import datetime
from fastapi import (
    BackgroundTasks,
    FastAPI,
    HTTPException,
    Response,
    Request,
    Depends,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import JSONResponse
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.logger import logger as fastLog
import httpx
import uvicorn
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# pylint: disable=E0402
from .storage import DB
from .config import (
    SHIELDS_IO_URL,
    COLOR,
    ERROR_COLOR,
    RATE_LIMIT_STRING,
    RATE_LIMIT_COST,
    PORT,
)
from .models import (
    HealthCheckResponse,
    RateLimitResponse,
    StarsResponse,
    RepoStarsResponse,
)
from .utils import validate_owner_repo
from .services import GitHubService
from .dbmanager import DBManager
from .web_connections import SubscriptionManager

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
logger.addHandler(handler)
fastLog.addHandler(handler)

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[RATE_LIMIT_STRING],
)


# Global database instance - LMDB should be opened once and reused
def get_db() -> DB:
    """Helper: Get the shared database instance (singleton pattern for LMDB)."""
    return DBManager.get_db()


_github_service = GitHubService(get_db())
manager = SubscriptionManager(service=_github_service)


async def startup():  ## must set it so user can choose whether to enable or not
    """Startup Function to run worker"""
    await manager.start_worker()


app = FastAPI(startup=startup)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.state.limiter = limiter


def get_rate_limit_string():
    """Get the rate limit string for slowapi based on configuration."""
    return RATE_LIMIT_STRING


async def rate_limit_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle rate limit exceeded exceptions."""
    _ = request
    if isinstance(exc, RateLimitExceeded):
        return JSONResponse(
            content=RateLimitResponse(
                error="Rate limit exceeded",
                status_code=429,
                detail="Rate limit exceeded. Please try again later.",
            ).model_dump()
        )
    # Fallback for other exceptions (shouldn't reach here)
    raise exc


app.add_exception_handler(RateLimitExceeded, rate_limit_handler)


# Service dependency - injects DB into service
def get_github_service(db: DB = Depends(get_db)) -> GitHubService:
    """Get GitHub service with injected database."""
    return GitHubService(db)


# WebSocket
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Websocket endpoint - Handle websocket registration
    """
    conn_id = await manager.conn.connect(websocket)
    try:
        while True:
            # Wait for messages from the client (subscription / unsubscription)
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({"error": "Invalid JSON"}))
                continue
            action = msg.get("action")
            events = msg.get("events", [])
            if action == "subscribe":
                await manager.conn.subscribe(conn_id, events)
                await websocket.send_text(
                    json.dumps({"status": "subscribed", "events": events})
                )
            elif action == "unsubscribe":
                await manager.conn.unsubscribe(conn_id, events)
                await websocket.send_text(
                    json.dumps({"status": "unsubscribed", "events": events})
                )
            else:
                await websocket.send_text(json.dumps({"error": "unknown action"}))
    except WebSocketDisconnect:
        manager.conn.disconnect(conn_id)
    except Exception as e:
        manager.conn.disconnect(conn_id)
        print(f"{e}")


async def call_event(owner: str, stars: int, repo: str = ""):
    """Helper that parse events, results and emit them"""
    event = owner if repo == "" else f"{owner}:{repo}"
    await manager.emit_event(event, {"stars": stars})


@app.get(
    "/health",
    description="Health check endpoint to verify API and database connectivity",
    response_model=HealthCheckResponse,
    tags=["Health"],
)
async def health(service: GitHubService = Depends(get_github_service)):
    """Health check endpoint to verify API and database connectivity."""
    db_status = service.health_check()

    return HealthCheckResponse(
        status="healthy" if db_status["status"] == "healthy" else "unhealthy",
        database=db_status["database"],
        timestamp=json.dumps(datetime.datetime.now().isoformat()),
    )


@app.get(
    "/api/v1/stars/{owner}",
    description="Get total star count for a GitHub user",
    response_model=StarsResponse,
    tags=["Stars"],
)
@limiter.limit(get_rate_limit_string(), cost=RATE_LIMIT_COST)
async def get_user_stars(
    request: Request,
    owner: str,
    background_tasks: BackgroundTasks,
    exclude_fork=False,
    service: GitHubService = Depends(get_github_service),
) -> StarsResponse:
    """
    Return the total number of stars for a given GitHub user.
    """
    _ = request
    validate_owner_repo(owner, "username")
    stars = await service.fetch_star_count(owner, exclude_fork=exclude_fork)
    if stars is None:
        raise HTTPException(status_code=404, detail="User not found")
    if stars == -1:
        raise HTTPException(
            status_code=500, detail="Error fetching star count from GitHub"
        )
    background_tasks.add_task(call_event, owner=owner, stars=stars)
    return StarsResponse(owner=owner, stars=stars)


@app.get(
    "/api/v1/stars/{owner}/{repo}",
    description="Get star count for a GitHub repository",
    response_model=RepoStarsResponse,
    tags=["Stars"],
)
@limiter.limit(get_rate_limit_string(), cost=RATE_LIMIT_COST)
async def get_repo_stars(
    request: Request,
    owner: str,
    repo: str,
    background_task: BackgroundTasks,
    service: GitHubService = Depends(get_github_service),
) -> RepoStarsResponse:
    """
    Return the number of stars for a given GitHub repository.
    """
    _ = request
    validate_owner_repo(owner, "username")
    validate_owner_repo(repo, "repository name")
    stars = await service.fetch_star_count(owner, repo)
    if stars is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    if stars == -1:
        raise HTTPException(
            status_code=500, detail="Error fetching star count from GitHub"
        )
    background_task.add_task(call_event, owner, stars=stars, repo=repo)
    return RepoStarsResponse(owner=owner, repo=repo, stars=stars)


@app.get(
    "/api/v1/badge/user/{owner}",
    description="Get badge image showing total stars for a GitHub user",
    tags=["Badge"],
)
@limiter.limit(get_rate_limit_string(), cost=RATE_LIMIT_COST)
# pylint: disable=too-many-arguments,too-many-positional-arguments
async def get_user_badge(
    request: Request,
    owner: str,
    theme: str = "flat",
    color: str = COLOR,
    exclude_fork: bool = False,
    service: GitHubService = Depends(get_github_service),
):
    """
    Return a badge image showing the total number of stars for a given GitHub user.
    Supports themes: flat, flat-square, for-the-badge, plastic (default: flat).
    """
    _ = request
    validate_owner_repo(owner, "username")
    if theme not in ["flat", "flat-square", "for-the-badge", "plastic"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid theme. "
            "Choose from: flat, flat-square, for-the-badge, plastic",
        )

    stars = await service.fetch_star_count(owner, exclude_fork=exclude_fork)
    if stars is None:
        raise HTTPException(status_code=404, detail="User not found")
    if stars == -1:
        # GitHub API error → return error badge
        error_url = f"https://img.shields.io/badge/stars-error-lightgrey?style={theme}&logo=github"
        return await get_badge_image(error_url)
    formatted_stars = f"{stars:,}"
    badge_url = SHIELDS_IO_URL.format(formatted_stars, color, theme)
    return await get_badge_image(badge_url)


# pylint: disable=too-many-arguments
# pylint: disable=too-many-positional-arguments
@app.get(
    "/api/v1/badge/repo/{owner}/{repo}",
    description="Get badge image showing stars for a GitHub repository",
    tags=["Badge"],
)
@limiter.limit(get_rate_limit_string(), cost=RATE_LIMIT_COST)
async def get_repo_badge(
    request: Request,
    owner: str,
    repo: str,
    theme: str = "flat",
    color: str = COLOR,
    service: GitHubService = Depends(get_github_service),
) -> Response:
    """
    Return a badge image showing the total number of stars for a given GitHub repository.
    Supports themes: flat, flat-square, for-the-badge, plastic (default: flat).
    """
    _ = request
    validate_owner_repo(owner, "username")
    validate_owner_repo(repo, "repository name")
    if theme not in ["flat", "flat-square", "for-the-badge", "plastic"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid theme. "
            "Choose from: flat, flat-square, for-the-badge, plastic",
        )

    stars = await service.fetch_star_count(owner, repo)
    if stars is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    if stars == -1:
        # GitHub API error → return error badge
        error_url = SHIELDS_IO_URL.format("error", ERROR_COLOR, theme)
        return await get_badge_image(error_url)

    formatted_stars = f"{stars:,}"
    badge_url = SHIELDS_IO_URL.format(formatted_stars, color, theme)
    return await get_badge_image(badge_url)


async def get_badge_image(badge_url: str) -> Response:
    """ "
    Fetch the badge image from shields.io and return it as a response.
    """
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(badge_url)
            response.raise_for_status()  # Raise exception for 4xx/5xx responses
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=500, detail="Failed to fetch badge from shields.io"
            ) from exc
        return Response(content=response.content, media_type="image/svg+xml")


def signal_handler(signum, frame):
    """Handle termination signals for graceful shutdown."""
    _ = frame
    _ = signum
    logger.info("Shutting down gracefully")
    # Close the global DB instance on shutdown
    DBManager.close_db()
    sys.exit(0)


signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)  # Handle Ctrl+C gracefully


def main():
    """Main function to run the FastAPI app."""
    uvicorn.run(app, host="0.0.0.0", port=PORT)
