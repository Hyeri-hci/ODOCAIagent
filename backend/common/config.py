from __future__ import annotations

import os
from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN: str | None = os.getenv("GITHUB_TOKEN")
GITHUB_API_BASE: str = os.getenv("GITHUB_API_BASE", "https://api.github.com")

DEFAULT_ACTIVITY_DAYS: int = 90

# LLM Settings
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "openai_compatible")
LLM_API_BASE: str | None = os.getenv("LLM_API_BASE", "http://localhost:8000/v1")
LLM_API_KEY: str | None = os.getenv("LLM_API_KEY")
LLM_MODEL_NAME: str = os.getenv("LLM_MODEL_NAME", "kanana-1.5-8b-instruct-2505")



