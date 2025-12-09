import logging
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient, models
from config.setting import settings
from core.qdrant.schemas import RepoSchema, ReadmeSchema
import uuid

# 💡 [필수] requests.exceptions를 임포트하여 ConnectionError를 처리할 수 있도록 가정
from requests.exceptions import ConnectionError

logger = logging.getLogger(__name__)

# 환경 변수에서 컬렉션 이름 가져오기
REPO_COLLECTION_NAME = settings.qdrant.collection_desc
README_COLLECTION_NAME = settings.qdrant.collection_readme

class QdrantDBClient:
    def __init__(self):
        self.host = settings.qdrant.host
        self.port = settings.qdrant.port
        self.client: Optional[QdrantClient] = None
        self.connect()

    def connect(self):
        """Qdrant 연결 및 클라이언트 인스턴스 생성"""
        if self.client is None:
            try:
                self.client = QdrantClient(host=self.host, port=self.port, timeout=10)
                # 🌟 [DEBUG] 연결 확인 시 health check 수행
                self.client.get_collections() 
                logger.info(f"[Qdrant] Connected to {self.host}:{self.port}")
            except ConnectionError as ce:
                # 🌟 [CRITICAL LOG] 연결 오류는 여기서 포착
                logger.error(f"[Qdrant CRITICAL ERROR] Connection Failed: {ce}")
                raise ce
            except Exception as e:
                logger.error(f"[Qdrant] Connection Error: {e}")
                raise e

    def _get_collection_name(self, collection_type: str) -> str:
        if collection_type == 'desc':
            return REPO_COLLECTION_NAME
        elif collection_type == 'readme':
            return README_COLLECTION_NAME
        else:
            raise ValueError(f"Invalid collection_type: {collection_type}")

    # ==========================================================
    # 1. 데이터 삽입 (Insert/Upsert)
    # ... (기존 코드와 동일) ...
    # ==========================================================
    def insert_data(self, collection_type: str, data: List[Dict[str, Any]]):
        if not data or self.client is None:
            return

        target_col_name = self._get_collection_name(collection_type)
        points_to_upsert = []
        
        for item in data:
            # 1. 벡터 필드 분리
            vector_field_name = RepoSchema.FIELD_EMBEDDING if collection_type == 'desc' else ReadmeSchema.FIELD_EMBEDDING
            vector = item.pop(vector_field_name)
            
            # 2. Point ID 결정
            point_id = None
            if collection_type == 'desc':
                # Repo DB: project_id를 고유 ID로 사용 (INT64)
                point_id = item.pop(RepoSchema.FIELD_PROJECT_ID)
                # Payload에 project_id 복구 (조회용)
                item[RepoSchema.FIELD_PROJECT_ID] = point_id 
            else:
                # Readme DB: UUID 생성
                point_id = str(uuid.uuid4())
            
            # 3. PointStruct 생성
            points_to_upsert.append(
                models.PointStruct(
                    id=point_id, 
                    vector=vector,
                    payload=item
                )
            )

        try:
            self.client.upsert(
                collection_name=target_col_name,
                points=points_to_upsert,
                wait=True
            )
            # logger.info(f"[Qdrant] Inserted {len(data)} items into {target_col_name}")
        except Exception as e:
            logger.error(f"[Qdrant] Insert failed: {e}")
            raise e

    # ==========================================================
    # 2. 데이터 개수 확인 (Count)
    # ... (기존 코드와 동일) ...
    # ==========================================================
    def count_entities(self, collection_type: str) -> int:
        if self.client is None: return 0
        target_col_name = self._get_collection_name(collection_type)
        try:
            count_result = self.client.count(
                collection_name=target_col_name,
                exact=True 
            )
            return count_result.count
        except Exception as e:
            logger.error(f"[Qdrant] Count failed: {e}")
            return 0

    # ==========================================================
    # 3. ID로 메타데이터 조회 (Join용 Helper)
    # ... (기존 코드와 동일) ...
    # ==========================================================
    def get_repo_metadata(self, project_ids: List[int]) -> Dict[int, Dict[str, Any]]:
        if not project_ids or self.client is None:
            return {}
        
        col_name = REPO_COLLECTION_NAME
        
        # Payload Filter 구성
        repo_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key=RepoSchema.FIELD_PROJECT_ID,
                    match=models.MatchAny(any=list(set(project_ids)))
                )
            ]
        )
        
        try:
            # Metadata 조회는 scroll 사용이 효율적
            results, _ = self.client.scroll(
                collection_name=col_name,
                scroll_filter=repo_filter,
                limit=len(project_ids) * 2,
                with_payload=True,
                with_vectors=False
            )
            
            meta_map = {}
            for res in results:
                payload = res.payload if res.payload else {}
                p_id = payload.get(RepoSchema.FIELD_PROJECT_ID)
                if p_id is not None:
                    meta_map[p_id] = payload
            return meta_map

        except Exception as e:
            logger.error(f"[Qdrant] Metadata query failed: {e}")
            return {}

    # ==========================================================
    # 4. 검색 (Search) - hnsw_ef 파라미터 추가 🚀
    # ==========================================================
    def search(
        self, 
        embedding: List[float], 
        collection_type: str, 
        top_k: int = 3, 
        qdrant_filter: Optional[models.Filter] = None,
        hnsw_ef: int = 512 
    ) -> List[Dict[str, Any]]:
        
        if not embedding or self.client is None: 
            logger.warning("[Qdrant] Search skipped: Embedding or client is missing.")
            return []

        target_col_name = self._get_collection_name(collection_type)
        
        # 🌟 [DEBUG LOG] 검색 시작 정보 출력
        logger.info(f"[Qdrant DEBUG] Starting search in {target_col_name}. top_k: {top_k}")
        
        try:
            # 🔍 [Search Params 설정]
            search_params = models.SearchParams(
                hnsw_ef=hnsw_ef,
                exact=False
            )

            search_result_obj = self.client.query_points(
                collection_name=target_col_name,
                query=embedding,
                query_filter=qdrant_filter,
                limit=top_k,
                search_params=search_params,
                with_payload=True,
                with_vectors=False,
            )
            results = search_result_obj.points
            
        except Exception as e:
            # 🌟 [ERROR LOG] 검색 API 호출 중 발생하는 오류 포착
            logger.error(f"[Qdrant CRITICAL SEARCH ERROR] in {target_col_name}: {e}")
            return []

        # 🌟 [DEBUG LOG] 검색 결과 개수 확인
        if not results:
             logger.info(f"[Qdrant DEBUG] Search completed, found 0 results in {target_col_name}.")
        else:
             logger.info(f"[Qdrant DEBUG] Search successful, retrieved {len(results)} points.")
        
        parsed_results = []
        meta_map = {} 

        # [Step 1] Readme 검색인 경우 -> 메타데이터 Join 준비
        if collection_type == 'readme':
            found_ids = []
            for hit in results:
                payload = hit.payload if hit.payload else {}
                pid = payload.get(ReadmeSchema.FIELD_PROJECT_ID)
                if pid: found_ids.append(pid)
            
            if hasattr(self, 'get_repo_metadata') and found_ids:
                meta_map = self.get_repo_metadata(found_ids)

        # [Step 2] 결과 파싱
        for hit in results:
            data = hit.payload if hit.payload else {}
            score = round(hit.score, 4)

            if collection_type == 'desc':
                item = {
                    "type": "project_info",
                    "id": data.get(RepoSchema.FIELD_PROJECT_ID),
                    "name": data.get(RepoSchema.FIELD_NAME),
                    "owner": data.get(RepoSchema.FIELD_OWNER),
                    "url": data.get(RepoSchema.FIELD_REPO_URL),
                    "desc": data.get(RepoSchema.FIELD_DESC),
                    "topics": data.get(RepoSchema.FIELD_TOPICS, []),
                    "language": data.get(RepoSchema.FIELD_MAIN_LANG),
                    "stars": data.get(RepoSchema.FIELD_STARS, 0),
                    "score": score
                }
            else:
                p_id = data.get(ReadmeSchema.FIELD_PROJECT_ID)
                meta = meta_map.get(p_id, {}) 
                
                item = {
                    "type": "code_detail",
                    "id": p_id,
                    "name": meta.get(RepoSchema.FIELD_NAME, "Unknown"),
                    "url": meta.get(RepoSchema.FIELD_REPO_URL, "#"),
                    "stars": meta.get(RepoSchema.FIELD_STARS, 0),
                    "chunk_idx": data.get(ReadmeSchema.FIELD_CHUNK_IDX),
                    "content": data.get(ReadmeSchema.FIELD_CONTENT) or "", 
                    "score": score
                }
            parsed_results.append(item)

        return parsed_results
    
qdrant_client = QdrantDBClient()