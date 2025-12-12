import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# Optional import - qdrant-client 없으면 fallback 사용
try:
    from qdrant_client import QdrantClient, models
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False
    QdrantClient = None
    models = None
    logger.warning("qdrant-client not installed. Recommend agent will be disabled.")

# Lazy import to avoid circular imports and missing module errors
def _get_settings():
    from backend.agents.recommend.config.setting import settings
    return settings

def _get_schemas():
    from backend.agents.recommend.core.qdrant.schemas import RepoSchema, ReadmeSchema
    return RepoSchema, ReadmeSchema

def _get_collection_names():
    settings = _get_settings()
    return settings.qdrant.collection_desc, settings.qdrant.collection_readme


class QdrantDBClient:
    def __init__(self):
        if not QDRANT_AVAILABLE:
            raise ImportError("qdrant-client is not installed. Please install it with: pip install qdrant-client")
        
        settings = _get_settings()
        self.host = settings.qdrant.host
        self.port = settings.qdrant.port
        self.client: Optional[QdrantClient] = None
        self._connect()

    def _connect(self):
        try:
            self.client = QdrantClient(host=self.host, port=self.port, timeout=10)
            # 연결 확인용 가벼운 호출
            self.client.get_collections() 
            logger.info(f"✅ [Qdrant] Connected to {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"❌ [Qdrant] Connection Failed: {e}")
            self.client = None

    def _get_collection_name(self, collection_type: str) -> str:
        repo_collection, readme_collection = _get_collection_names()
        if collection_type == 'desc': return repo_collection
        elif collection_type == 'readme': return readme_collection
        raise ValueError(f"Invalid collection_type: {collection_type}")

    def get_repo_metadata(self, project_ids: List[int]) -> Dict[int, Dict[str, Any]]:
        """ID 리스트로 Repo 메타데이터 조회"""
        if not project_ids or not self.client: 
            return {}

        try:
            # Lazy import로 스키마 가져오기
            RepoSchema, _ = _get_schemas()
            repo_collection, _ = _get_collection_names()
            
            # 중복 ID 제거
            unique_ids = list(set(project_ids))
            
            repo_filter = models.Filter(
                must=[models.FieldCondition(
                    key=RepoSchema.FIELD_PROJECT_ID,
                    match=models.MatchAny(any=unique_ids)
                )]
            )
            
            # ID 개수만큼 Limit 설정하여 한 번에 가져오기
            results, _ = self.client.scroll(
                collection_name=repo_collection,
                scroll_filter=repo_filter,
                limit=len(unique_ids) + 10, # 넉넉하게
                with_payload=True,
                with_vectors=False
            )
            
            meta_map = {}
            for res in results:
                if res.payload:
                    pid = res.payload.get(RepoSchema.FIELD_PROJECT_ID)
                    if pid: meta_map[pid] = res.payload
            return meta_map

        except Exception as e:
            logger.error(f"[Qdrant] Metadata fetch failed: {e}")
            return {}

    def search(
        self, 
        embedding: List[float], 
        collection_type: str, 
        top_k: int = 10, 
        qdrant_filter: Optional[models.Filter] = None,
        hnsw_ef: int = 128
    ) -> List[Dict[str, Any]]:
        
        if not self.client: 
            logger.error("[Qdrant] Client not connected.")
            return []

        # Lazy import로 스키마 가져오기
        RepoSchema, ReadmeSchema = _get_schemas()
        
        target_col = self._get_collection_name(collection_type)
        
        try:
            search_params = models.SearchParams(hnsw_ef=hnsw_ef, exact=False)
            
            response = self.client.query_points(
                collection_name=target_col,
                query=embedding,
                query_filter=qdrant_filter,
                limit=top_k,
                search_params=search_params,
                with_payload=True
            )

            hits = response.points
        except Exception as e:
            logger.error(f"[Qdrant] Search failed in {target_col}: {e}")
            return []

        # 결과 처리
        parsed_results = []
        
        # Readme 검색일 경우: Repo 메타데이터 Join 필요
        meta_map = {}
        if collection_type == 'readme':
            pids = []
            for hit in hits:
                if hit.payload:
                    pid = hit.payload.get(ReadmeSchema.FIELD_PROJECT_ID)
                    if pid: pids.append(pid)
            
            if pids:
                meta_map = self.get_repo_metadata(pids)

        for hit in hits:
            payload = hit.payload or {}
            score = hit.score
            
            if collection_type == 'desc':
                # Repo Description
                parsed_results.append({
                    "id": payload.get(RepoSchema.FIELD_PROJECT_ID),
                    "content": payload.get(RepoSchema.FIELD_DESC),
                    "meta": payload, # 원본 페이로드 자체가 메타데이터
                    "score": score
                })
            else:
                # Readme Chunk
                pid = payload.get(ReadmeSchema.FIELD_PROJECT_ID)
                # Join된 메타데이터 가져오기 (없으면 빈 dict -> 나중에 필터링됨)
                repo_meta = meta_map.get(pid, {}) 
                
                parsed_results.append({
                    "id": pid,
                    "content": payload.get(ReadmeSchema.FIELD_CONTENT),
                    "chunk_idx": payload.get(ReadmeSchema.FIELD_CHUNK_IDX),
                    "meta": repo_meta,
                    "score": score
                })

        return parsed_results

# 싱글톤 인스턴스
qdrant_client = QdrantDBClient()