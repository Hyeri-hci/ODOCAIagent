# adapters/embedding_client.py

from typing import List, Optional
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)

# Optional import - langchain_upstage 없으면 fallback 사용
try:
    from langchain_upstage import UpstageEmbeddings
    UPSTAGE_AVAILABLE = True
except ImportError:
    UPSTAGE_AVAILABLE = False
    logger.warning("langchain_upstage not installed. Recommend agent will use fallback.")


class EmbeddingClient(ABC):
    """추상 인터페이스 — 모든 recommend/search 모듈이 이걸 통해 호출."""

    @abstractmethod
    def embed_query(self, text: str) -> List[float]:
        """검색을 위한 query embedding"""
        pass

    @abstractmethod
    def embed_passage(self, text: str) -> List[float]:
        """문서/문장 자체의 embedding (단건)"""
        pass

    @abstractmethod
    def embed_passage_batch(self, texts: List[str]) -> List[List[float]]:
        """batch embedding (속도 향상)"""
        pass


class FallbackEmbeddingClient(EmbeddingClient):
    """langchain_upstage 없을 때 사용하는 fallback 클라이언트"""
    
    def embed_query(self, text: str) -> List[float]:
        # 빈 임베딩 반환 (추천 기능 비활성화)
        return [0.0] * 768
    
    def embed_passage(self, text: str) -> List[float]:
        return [0.0] * 768
    
    def embed_passage_batch(self, texts: List[str]) -> List[List[float]]:
        return [[0.0] * 768 for _ in texts]


class UpstageEmbeddingClient(EmbeddingClient):
    def __init__(self):
        if not UPSTAGE_AVAILABLE:
            raise ImportError("langchain_upstage is not installed")
        
        from backend.agents.recommend.config.setting import settings
        api_key = settings.upstage.get_next_api()
        
        self.query_model = UpstageEmbeddings(
            api_key=api_key,
            model=settings.upstage.query_model_name
        )
        self.passage_model = UpstageEmbeddings(
            api_key=api_key,
            model=settings.upstage.passage_model_name
        )

    def embed_query(self, text: str) -> List[float]:
        """검색용 — cosine/IP search에 최적화"""
        return self.query_model.embed_query(text)

    def embed_passage(self, text: str) -> List[float]:
        """문서/README chunk embedding — 단일 문자열"""
        # embed_documents는 list를 받고 list를 반환하므로 [0] 처리
        return self.passage_model.embed_documents([text])[0]

    def embed_passage_batch(self, texts: List[str]) -> List[List[float]]:
        """문서/README chunk embedding — 여러 문장 한번에"""
        return self.passage_model.embed_documents(texts)


# 클라이언트 인스턴스 생성 (fallback 지원)
embedding_client: Optional[EmbeddingClient] = None

def get_embedding_client() -> EmbeddingClient:
    """Lazy initialization of embedding client"""
    global embedding_client
    if embedding_client is None:
        if UPSTAGE_AVAILABLE:
            try:
                embedding_client = UpstageEmbeddingClient()
            except Exception as e:
                logger.warning(f"Failed to initialize UpstageEmbeddingClient: {e}")
                embedding_client = FallbackEmbeddingClient()
        else:
            embedding_client = FallbackEmbeddingClient()
    return embedding_client