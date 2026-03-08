"""
Main entry point for the GitHub Stars Badge API.
"""
import os
from typing import Optional
from fastapi import FastAPI, HTTPException, Response
import httpx
import requests
import uvicorn
from storage import dighash, DB

GITHUB_API_URL = "https://api.github.com/{}/{}/{}"
SHIELDS_IO_URL = "https://img.shields.io/badge/stars-{}-brightgreen?style={}&logo=github"
HEADERS = {}
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
if GITHUB_TOKEN:
    HEADERS = {"Authorization": f"token {GITHUB_TOKEN}"}

app = FastAPI()
DB_PATH = "store.db"
INDEX_PATH = "index.db"
DB_INSTANCE = DB(path=DB_PATH, index_path=INDEX_PATH)
@app.get("/stars/{owner}/{repo}/count")
async def get_stars_count(owner: str, repo: str):
    """
    Return the number of stars for a given GitHub repository. 
    If repo is not provided, return total stars for the user.
    """
    stars = await fetch_star_count(owner, repo)
    if stars is None:
        raise HTTPException(status_code=404, detail="User or repository not found")
    if stars == -1:
        raise HTTPException(status_code=500, detail="Error fetching star count from GitHub")
    return {"stars": stars}

@app.get("/stars/{owner}/badge/{theme}")
async def get_all_star_badge(owner: str, theme: str):
    """
    Return a badge image showing the total number of stars for a given GitHub user.
    The badge is generated using shields.io with the specified theme.
    """
    if not theme:
        theme = "flat"  # default theme
    if theme not in ["flat", "flat-square", "for-the-badge", "plastic"]:
        raise HTTPException(status_code=400, detail="Invalid theme")

    stars = await fetch_star_count(owner)
    if stars is None:
        raise HTTPException(status_code=404, detail="User not found")
    if stars == -1:
        # GitHub API error → redirect to an error badge
        return (
            f"https://img.shields.io/badge/stars-error-lightgrey?style={theme}&logo=github")
    formatted_stars = f"{stars:,}"
    return await get_badge_image(SHIELDS_IO_URL.format(formatted_stars, theme))

@app.get("/stars/{owner}/badge/repo/{repo}/{theme}")
async def get_repo_star_badge(owner: str, repo: str, theme: str):
    """
    Return a badge image showing the total number of stars for a given GitHub repository.
    The badge is generated using shields.io with the specified theme.
    """
    if not theme:
        theme = "flat"  # default theme
    if theme not in ["flat", "flat-square", "for-the-badge", "plastic"]:
        raise HTTPException(status_code=400, detail="Invalid theme")

    stars = await fetch_star_count(owner, repo)
    if stars is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    if stars == -1:
        # GitHub API error → redirect to an error badge
        return (
            f"https://img.shields.io/badge/stars-error-lightgrey?style={theme}&logo=github")
    formatted_stars = f"{stars:,}"
    return await get_badge_image(SHIELDS_IO_URL.format(formatted_stars, theme))

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

async def fetch_star_count(owner: str, repo: Optional[str] = None) -> Optional[int]:
    """
    Fetch the star count for a given GitHub repository or user. 
    If repo is None, fetch total stars for the user.
    """
    stars = 0
    page = 1
    per_page = 100
    while True:
        if repo:
            url = GITHUB_API_URL.format("repos", owner, repo)
        else:
            url = GITHUB_API_URL.format("users", owner, "repos")
        print(f"Fetching from GitHub API: {url} (page {page})")
        params = {"page": page, "per_page": per_page}
        resp = requests.get(url, headers=HEADERS, params=params, timeout=10)
        if resp.status_code == 404:
            return None  # user not found
        if resp.status_code != 200:
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

def main():
    """
    Main function to run the FastAPI application.
    """
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    main()
