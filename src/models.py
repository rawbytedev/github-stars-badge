"""
Pydantic models for API responses.
"""

import os
from typing import Optional
from pydantic import BaseModel

class Config:

    """Pydantic configuration for environment variable loading."""
    env_file = ".env"
    default_env_file_encoding = "utf-8"

    def load_env_file(self):
        """Load environment variables from the .env file."""
        env_file = self.envfile()
        if os.path.exists(env_file):
            with open(env_file, encoding=self.env_file_encoding()) as f:
                for line in f:
                    if line.strip() and not line.startswith("#"):
                        key, value = line.strip().split("=", 1)
                        os.environ[key] = value

    def env_file_encoding(self):
        """Determine the encoding for the .env file."""

        return os.getenv("ENV_FILE_ENCODING", "utf-8")
    
    def envfile(self):
        """Determine the path to the .env file."""

        return os.getenv("ENV_FILE_PATH",   ".env")

class RateLimitResponse(BaseModel):
    """Response model for rate limit information."""

    error: str
    status_code: int
    detail: str

class HealthCheckResponse(BaseModel):
    """Response model for health check endpoint."""

    status: str
    database: str
    timestamp: str
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


settings = Settings()
