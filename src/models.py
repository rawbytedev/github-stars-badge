"""
Pydantic models for API responses.
"""
from typing import Optional
from pydantic import BaseModel


class StarsResponse(BaseModel):
    """Response model for user star count."""
    owner: str
    stars: int

class RepoStarsResponse(BaseModel):
    """Response model for repository star count."""
    owner: str
    repo: str
    stars: int

class CachedStarCount(BaseModel):
    """Model for cached star count in the database."""
    key: str
    stars: int
    timestamp: int
class Settings(BaseModel):
    """Application settings loaded from environment variables."""
    github_token: Optional[str] = None
    db_path: str = "store.db"
    cache_ttl: int = 10
    class Config:
        """Pydantic configuration for environment variable loading."""
        env_file = ".env"

settings = Settings()
