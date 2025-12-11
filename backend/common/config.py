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

# Redis Settings
REDIS_URL: str | None = os.getenv("REDIS_URL", "redis://localhost:6379")
REDIS_CONVERSATION_TTL: int = int(os.getenv("REDIS_CONVERSATION_TTL", "604800"))  # 7 days
REDIS_SUMMARY_TTL: int = int(os.getenv("REDIS_SUMMARY_TTL", "2592000"))  # 30 days

# Security Agent LLM Settings
SECURITY_LLM_BASE_URL: str | None = os.getenv("LLM_API_BASE")
SECURITY_LLM_API_KEY: str | None = os.getenv("LLM_API_KEY")
SECURITY_LLM_MODEL: str = os.getenv("LLM_MODEL_NAME", "kanana-2-30b-a3b-instruct")
SECURITY_LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.0"))

# CPE DB Settings
DB_CPE_HOST: str | None = os.getenv("DB_CPE_HOST")
DB_CPE_PORT: int = int(os.getenv("DB_CPE_PORT", "3306"))
DB_CPE_USER: str | None = os.getenv("DB_CPE_USER")
DB_CPE_PW: str | None = os.getenv("DB_CPE_PW")
DB_CPE_DB: str | None = os.getenv("DB_CPE_DB")
