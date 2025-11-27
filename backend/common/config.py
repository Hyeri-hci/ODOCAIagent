from __future__ import annotations

import os
from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN: str | None = os.getenv("GITHUB_TOKEN")
GITHUB_API_BASE: str = os.getenv("GITHUB_API_BASE", "https://api.github.com")

DEFAULT_ACTIVITY_DAYS: int = 90