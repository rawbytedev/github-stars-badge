"""Contain the main Config and defaults values"""

import os

#pylint: disable=C0103
GITHUB_API_URL = "https://api.github.com/{}/{}/{}"
SHIELDS_IO_URL = "https://img.shields.io/badge/stars-{}-{}?style={}&logo=github"
COLOR = "brightgreen"
ERROR_COLOR = "lightgrey"
HEADERS = {}
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
if GITHUB_TOKEN:
    HEADERS = {"Authorization": f"token {GITHUB_TOKEN}"}
RATE_LIMIT = int(os.getenv("RATE_LIMIT", "10"))
RATE_LIMIT_COST = int(os.getenv("RATE_LIMIT_COST", "2"))
RATE_LIMIT_PERIOD = os.getenv("RATE_LIMIT_PERIOD", "minute")
RATE_LIMIT_STRING = f"{RATE_LIMIT}/{RATE_LIMIT_PERIOD}"
