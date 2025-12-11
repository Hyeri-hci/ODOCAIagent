from __future__ import annotations

import os
from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN: str | None = os.getenv("GITHUB_TOKEN")
GITHUB_API_BASE: str = os.getenv("GITHUB_BASE_URL", "https://api.github.com")

DEFAULT_ACTIVITY_DAYS: int = 90

# LLM Settings
LLM_PROVIDER: str = os.getenv("LLM_MODEL_PROVIDER", "openai_compatible")
LLM_API_BASE: str | None = os.getenv("LLM_BASE_URL")
LLM_API_KEY: str | None = os.getenv("LLM_API_KEY")
LLM_MODEL_NAME: str = os.getenv("LLM_MODEL", "kanana-2-30b-a3b-instruct")
LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.0"))

# Redis Settings
REDIS_URL: str | None = os.getenv("REDIS_URL", "redis://localhost:6379")
REDIS_CONVERSATION_TTL: int = int(os.getenv("REDIS_CONVERSATION_TTL", "604800"))  # 7 days
REDIS_SUMMARY_TTL: int = int(os.getenv("REDIS_SUMMARY_TTL", "2592000"))  # 30 days

# Security Agent LLM Settings (same as main LLM)
SECURITY_LLM_BASE_URL: str | None = os.getenv("LLM_BASE_URL")
SECURITY_LLM_API_KEY: str | None = os.getenv("LLM_API_KEY")
SECURITY_LLM_MODEL: str = os.getenv("LLM_MODEL", "kanana-2-30b-a3b-instruct")
SECURITY_LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.0"))

# CPE DB Settings
DB_CPE_HOST: str | None = os.getenv("DB_CPE_HOST")
DB_CPE_PORT: int = int(os.getenv("DB_CPE_PORT", "3306"))
DB_CPE_USER: str | None = os.getenv("DB_CPE_USER")
DB_CPE_PW: str | None = os.getenv("DB_CPE_PW")
DB_CPE_DB: str | None = os.getenv("DB_CPE_DB")

# NVD API Settings
NVD_BASE_URL: str = os.getenv("NVD_BASE_URL", "https://services.nvd.nist.gov/rest/json/cves/2.0")
NVD_API_KEY: str | None = os.getenv("NVD_API_KEY")
NVD_MAX_RESULT_PER_CVE: int = int(os.getenv("NVD_MAX_RESULT_PER_CVE", "2000"))
NVD_TIMEOUT: int = int(os.getenv("NVD_TIMEOUT", "10"))

# Tavily API
TAVILY_API_KEY: str | None = os.getenv("TAVILY_API_KEY")

# LangSmith Settings
LANGSMITH_TRACING: bool = os.getenv("LANGSMITH_TRACING", "false").lower() == "true"
LANGSMITH_ENDPOINT: str | None = os.getenv("LANGSMITH_ENDPOINT")
LANGSMITH_API_KEY: str | None = os.getenv("LANGSMITH_API_KEY")
LANGSMITH_PROJECT: str | None = os.getenv("LANGSMITH_PROJECT")
