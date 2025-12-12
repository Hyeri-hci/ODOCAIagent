# config/settings.py

from pathlib import Path
import os
import logging
from typing import List, Optional, ClassVar
from pydantic import Field
from pydantic_settings import BaseSettings
from pydantic import PrivateAttr, field_validator
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Optional import - langchain_upstage 없으면 fallback 사용
try:
    from langchain_upstage import UpstageEmbeddings
    UPSTAGE_AVAILABLE = True
except ImportError:
    UPSTAGE_AVAILABLE = False
    UpstageEmbeddings = None
    logger.warning("langchain_upstage not installed. Recommend agent features will be limited.")

# ==========================
# 루트 디렉토리 기준으로 .env 로드
# ==========================
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent
load_dotenv(BASE_DIR / ".env")

# ==========================
# 경로 관련 설정
# ==========================
class BasePaths(BaseSettings):
    BASE_DIR: Path = BASE_DIR
    LOCK_DIR: Path = Field(default_factory=lambda: BASE_DIR / "locks")
    TOPIC_FILE: Path = Field(default_factory=lambda: BASE_DIR / "data/topic.json")
    PROJECT_DIR: Path = Field(default_factory=lambda: BASE_DIR / "data/projects")
    DB_DIR: Path = Field(default_factory=lambda: BASE_DIR / "db")

    # 디렉토리 자동 생성
    def __init__(self, **data):
        super().__init__(**data)
        for path_attr in ["LOCK_DIR", "PROJECT_DIR", "DB_DIR"]:
            path = getattr(self, path_attr)
            #path.mkdir(parents=True, exist_ok=True)

# ==========================
# GitHub 설정 (토큰 순환 로직 개선)
# ==========================
class GitHubSettings(BaseSettings):
    tokens: List[str] = []
    graphql_url: str = "https://api.github.com/graphql"
    search_url: str = "https://api.github.com/search/repositories"
    base_search_query: str = 'pushed:>=2023-01-01 stars:>=50 forks:>=5'
    base_search_query_template: str = 'topic:"{}" forks:>=5 pushed:>=2023-01-01'
    DEFAULT_MIN_STARS: ClassVar[int] = 50
    DEFAULT_MIN_FORKS: ClassVar[int] = 5
    DEFAULT_PUSHED_AFTER: ClassVar[str] = "2023-01-01"

    _token_index: int = 0  # 순환용

    def __init__(self, **data):
        # 기존 GITHUB_TOKEN 우선, 그 다음 GITHUB_TOKEN_1~4 시도
        tokens = []
        
        # 1. 메인 GITHUB_TOKEN 확인
        main_token = os.getenv("GITHUB_TOKEN")
        if main_token:
            tokens.append(main_token)
        
        # 2. 추가 토큰들 확인 (순환용)
        for i in range(1, 5):
            token = os.getenv(f"GITHUB_TOKEN_{i}")
            if token:
                tokens.append(token)
        
        if not tokens:
            logger.warning("No GitHub tokens found in .env. Recommend agent will have limited functionality.")
            tokens = [""]  # 빈 토큰으로 fallback (일부 기능 제한)
        
        data["tokens"] = tokens
        super().__init__(**data)

    # 다음 토큰 반환 (순환)
    def get_next_token(self) -> str:
        token = self.tokens[self._token_index]
        self._token_index = (self._token_index + 1) % len(self.tokens)
        return token

# ==========================
# Qdrant 설정
# ==========================
class QdrantSettings(BaseSettings):
    # 1. Field(alias="...")를 쓰면 해당 환경변수를 자동으로 찾아 매핑합니다.
    # Qdrant는 기본 포트 6333을 사용합니다.
    host: str = os.getenv("QDRANT_HOST", "localhost").strip('"')
    
    # 2. 타입이 int로 지정되어 있으므로, 문자열로 들어와도 자동으로 숫자로 변환해줍니다.
    port: int = Field(default=6333, alias="QDRANT_PORT")
    
    # 1. Description/Metadata 저장용 컬렉션
    collection_desc: str = Field(default="repo_descriptions", alias="QDRANT_COLLECTION_DESC")
    
    # 2. Readme Chunk 저장용 컬렉션
    collection_readme: str = Field(default="repo_readmes", alias="QDRANT_COLLECTION_README")
    
    # [중요] Solar Large 모델 차원인 4096으로 변경!
    embedding_dim: int = Field(default=4096, alias="QDRANT_EMBEDDING_DIM")

# ==========================
# Upstage 설정
# ==========================
class UpstageSettings(BaseSettings):
    # 환경변수에서 로드할 키 리스트
    api_keys: List[str] = []
    
    # 내부 상태 관리용 (스키마 제외)
    _api_index: int = PrivateAttr(default=0)

    base_url: str = "https://api.upstage.ai/v1/solar"
    query_model_name: str = "solar-embedding-1-large-query"
    passage_model_name: str = "solar-embedding-1-large-passage"

    # 1. 초기화 시 환경변수 로드 로직 (validator 사용)
    @field_validator("api_keys", mode="before")
    @classmethod
    def load_api_keys(cls, v):
        # 만약 생성자에 직접 api_keys를 넣었다면 그대로 사용
        if v:
            return v
        
        # 입력이 없으면 환경변수에서 찾음
        found_keys = [
            #os.getenv("UPSTAGE_API_1"),
            os.getenv("UPSTAGE_API_2"),
            os.getenv("UPSTAGE_API_3"),
            os.getenv("UPSTAGE_API_4"),
            os.getenv("UPSTAGE_API_5")
            # 필요하다면 더 추가
        ]
        # None이나 빈 문자열 제거
        valid_keys = [k for k in found_keys if k]
        
        if not valid_keys:
            logger.warning("No upstage tokens found in .env (UPSTAGE_API_2~5). Recommend agent embedding will use fallback.")
            return []  # 빈 리스트 반환 (fallback 사용)
        
        return valid_keys

    # 2. 다음 토큰 반환 (Round-Robin)
    def get_next_api(self) -> str:
        if not self.api_keys:
            raise ValueError("API keys list is empty. langchain_upstage features not available.")
            
        current_key = self.api_keys[self._api_index]
        # 인덱스 순환 업데이트
        self._api_index = (self._api_index + 1) % len(self.api_keys)
        return current_key

    # 3. 모델 생성 프로퍼티
    @property
    def passage_model(self):
        # self.api_key가 아니라 self.get_next_api()를 호출해야 함
        if not UPSTAGE_AVAILABLE:
            raise ImportError("langchain_upstage is not installed. Recommend agent requires this package.")
        return UpstageEmbeddings(
            api_key=self.get_next_api(),
            model=self.passage_model_name,
            upstage_api_base=self.base_url
        )

    @property
    def query_model(self):
        if not UPSTAGE_AVAILABLE:
            raise ImportError("langchain_upstage is not installed. Recommend agent requires this package.")
        return UpstageEmbeddings(
            api_key=self.get_next_api(),
            model=self.query_model_name,
            upstage_api_base=self.base_url
        )

# ==========================
# LLM 설정
# ==========================
class LLMSettings(BaseSettings):
    provider: str = os.getenv("LLM_PROVIDER", "openai_compatible")
    # LLM_BASE_URL과 LLM_API_BASE 둘 다 지원 (common/config.py와 호환)
    api_base: str = os.getenv("LLM_BASE_URL") or os.getenv("LLM_API_BASE", "http://localhost:8000/v1")
    api_key: Optional[str] = os.getenv("LLM_API_KEY")
    model_name: str = os.getenv("LLM_MODEL", os.getenv("LLM_MODEL_NAME", "gpt-4"))
    max_tokens: int = 1024
    temperature: float = 0.2
    top_p: float = 0.9

# ==========================
# OSS Insight 설정
# ==========================
class OSSInsightSettings(BaseSettings):
    base_url: str = "https://api.ossinsight.io/v1"
    timeout: int = 10
    user_agent: str = "ODOC-Agent/1.0"

# ==========================
# 전체 Settings 싱글톤
# ==========================
class Settings(BaseSettings):
    paths: BasePaths = BasePaths()
    github: GitHubSettings = GitHubSettings()
    qdrant: QdrantSettings = QdrantSettings()
    upstage: UpstageSettings = UpstageSettings()
    llm: LLMSettings = LLMSettings()
    oss_insight: OSSInsightSettings = OSSInsightSettings()

# 싱글톤 인스턴스
settings = Settings()