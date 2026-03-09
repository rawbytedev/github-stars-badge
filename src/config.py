"""
Contain the main Config and defaults values
"""
import os

GITHUB_API_URL = "https://api.github.com/{}/{}/{}"
SHIELDS_IO_URL = "https://img.shields.io/badge/stars-{}-{}?style={}&logo=github"
COLOR = "brightgreen"
ERROR_COLOR = "lightgrey"
HEADERS = {}
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
if GITHUB_TOKEN:
    HEADERS = {"Authorization": f"token {GITHUB_TOKEN}"}
