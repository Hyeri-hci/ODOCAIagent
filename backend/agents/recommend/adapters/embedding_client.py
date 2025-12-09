# adapters/embedding_client.py

from typing import List
from abc import ABC, abstractmethod
from langchain_upstage import UpstageEmbeddings
from config.setting import settings

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


class UpstageEmbeddingClient(EmbeddingClient):
    def __init__(self):
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
    
embedding_client = UpstageEmbeddingClient()