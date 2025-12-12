import logging
from typing import Dict, Any, List, Optional
from qdrant_client import models
from flashrank import Ranker, RerankRequest

from backend.agents.recommend.adapters.qdrant_client import qdrant_client
from backend.agents.recommend.adapters.embedding_client import get_embedding_client
from backend.agents.recommend.core.qdrant.schemas import RepoSchema, ReadmeSchema

logger = logging.getLogger(__name__)

# =================================================================
# FILTER BUILDER
# =================================================================
def build_qdrant_filter(filters: Dict[str, Any]) -> Optional[models.Filter]:
    """LLM이 추출한 filters 딕셔너리를 Qdrant Filter 객체로 변환"""
    must_conditions = []
    
    if filters:
        # 1. Language (Exact Match)
        if filters.get("language"):
            must_conditions.append(models.FieldCondition(
                key=RepoSchema.FIELD_MAIN_LANG, 
                match=models.MatchValue(value=filters["language"])
            ))

        # 2. Topics (하나라도 포함되면 OK - MatchAny)
        if filters.get("topics"):
            must_conditions.append(models.FieldCondition(
                key=RepoSchema.FIELD_TOPICS, 
                match=models.MatchAny(any=filters["topics"])
            ))

        # 3. Stars (Range: gte)
        # LLM이 숫자가 아닌 문자열("1000")로 줄 경우 대비해 안전하게 처리
        star_val = filters.get("min_stars") or filters.get("stars")
        if star_val:
            try:
                must_conditions.append(models.FieldCondition(
                    key=RepoSchema.FIELD_STARS, 
                    range=models.Range(gte=int(star_val))
                ))
            except ValueError:
                logger.warning(f"Invalid star count in filter: {star_val}")

    return models.Filter(must=must_conditions) if must_conditions else None


# =================================================================
# MAIN SEARCH ENGINE (Ensemble + Rerank)
# =================================================================
class VectorSearch:
    def __init__(self):
        self.db_client = qdrant_client
        self.embedding_client = get_embedding_client()  # lazy initialization
        
        # Reranker 모델 로딩 (최초 실행 시 다운로드 발생)
        # model_name을 명시하지 않으면 default(ms-marco-TinyBERT-L-2-v2) 사용
        self.ranker = Ranker(model_name="ms-marco-TinyBERT-L-2-v2", cache_dir="./model_cache")

    def search(
        self, 
        query: str, 
        filters: Dict[str, Any] = {},
        target_k: int = 10 
    ) -> Dict[str, Any]:
        """
        [Ensemble Search Pipeline]
        1. Description 검색 (Route A)
        2. Readme 검색 (Route B)
        3. 결과 병합 (Merge & Deduplication)
        4. Reranking -> Final Top-K
        """
        logger.info(f"🔍 [VectorSearch] Ensemble Search: '{query}' | Filters: {filters}")
        
        # 0. 쿼리 임베딩
        query_vector = self.embedding_client.embed_query(query)
        if not query_vector:
            logger.error("Query embedding failed.")
            return {"error": "Embedding failed", "final_recommendations": []}

        # 후보군 크기 설정 (Reranking 효과를 위해 3~4배수 확보)
        candidate_k = target_k * 10

        # ---------------------------------------------------------
        # [Route A & B] 병렬 검색
        # ---------------------------------------------------------
        common_filter = build_qdrant_filter(filters=filters)
        
        # 1. Description 검색 (리드미 없는 프로젝트도 여기서 잡힘)
        desc_hits = self.db_client.search(
            embedding=query_vector,
            collection_type='desc',
            top_k=candidate_k,
            qdrant_filter=common_filter
        )
        logger.info(f" 1️⃣ Description Hits: {len(desc_hits)}")

        # 2. Readme 검색 (상세 내용 기반 검색)
        # 주의: Readme Collection에도 Filter 필드(language 등)가 있어야 결과가 나옴
        readme_hits = self.db_client.search(
            embedding=query_vector,
            collection_type='readme',
            top_k=candidate_k,
            qdrant_filter=common_filter
        )
        logger.info(f" 2️⃣ Readme Hits: {len(readme_hits)}")

        # ---------------------------------------------------------
        # [Merge] 결과 병합 (전략: Description을 베이스로 하되, Readme 매칭 시 덮어쓰기)
        # ---------------------------------------------------------
        merged_candidates = {} 

        # A. Desc 결과 처리
        for hit in desc_hits:
            pid = hit['id']
            merged_candidates[pid] = {
                "id": pid,
                "content": f"[Project Description] {hit['content']}", 
                "meta": hit['meta'],
                "base_score": hit['score'],
                "source": "description"
            }

        # B. Readme 결과 병합
        for hit in readme_hits:
            pid = hit['id']
            
            # 메타데이터 Join에 실패한 Readme 결과는 신뢰할 수 없으므로 제외
            if not hit.get('meta'): 
                continue

            content_snippet = f"[Readme Snippet] {hit['content']}"

            if pid in merged_candidates:
                # 이미 Description으로 찾았지만, Readme 내용이 더 구체적이므로 업데이트
                # (선택사항: 둘 다 합쳐서 Reranking에 보낼 수도 있음)
                merged_candidates[pid]['content'] = content_snippet
                merged_candidates[pid]['source'] = "readme_and_desc"
                # 점수는 보통 Readme 매칭 점수가 더 의미 있을 수 있으므로 업데이트
                merged_candidates[pid]['base_score'] = max(merged_candidates[pid]['base_score'], hit['score'])
            else:
                # Description 검색엔 안 걸렸지만 Readme 내용으로 찾은 경우 (Hidden Gem)
                merged_candidates[pid] = {
                    "id": pid,
                    "content": content_snippet,
                    "meta": hit['meta'],
                    "base_score": hit['score'],
                    "source": "readme_only"
                }

        candidates_list = list(merged_candidates.values())
        logger.info(f" 3️⃣ Merged Unique Candidates: {len(candidates_list)}")
        
        if not candidates_list:
            return {
                "search_query": query, 
                "final_recommendations": [], 
                "message": "No matching projects found."
            }

        # ---------------------------------------------------------
        # [Rerank] 최종 순위 결정
        # ---------------------------------------------------------
        # FlashRank 포맷에 맞춰 데이터 변환
        passages = [
            {"id": str(c['id']), "text": c['content'], "meta": c['meta']}
            for c in candidates_list
        ]

        try:
            rerank_request = RerankRequest(query=query, passages=passages)
            ranked_results = self.ranker.rerank(rerank_request)
        except Exception as e:
            logger.error(f"Reranking failed: {e}. Returning vector search results.")
            # Rerank 실패 시 벡터 점수순 정렬로 대체
            ranked_results = sorted(passages, key=lambda x: x.get('score', 0), reverse=True)

        # 🎯 Final Top-K Cut
        final_top_k = ranked_results[:target_k]
        
        final_output = []
        for item in final_top_k:
            meta = item['meta']
            # Rerank 점수와 매칭된 스니펫을 메타에 추가 (UI 표시용)
            meta['rerank_score'] = item['score'] 
            # item['text']에는 "[Readme Snippet] ..." 태그가 붙어있으므로 그대로 사용
            meta['match_snippet'] = item['text'][:300] + "..." 
            final_output.append(meta)

        logger.info(f" ✅ Final Recommendations: {len(final_output)}")

        return {
            "search_query": query,
            "final_recommendations": final_output
        }

# 싱글톤 인스턴스 (lazy initialization)
_vector_search_engine = None

def get_vector_search_engine():
    """VectorSearch 싱글톤 인스턴스 반환 (lazy initialization)"""
    global _vector_search_engine
    if _vector_search_engine is None:
        _vector_search_engine = VectorSearch()
    return _vector_search_engine

# 하위 호환성을 위한 프로퍼티 (직접 접근 시에도 lazy init)
class _VectorSearchProxy:
    def __getattr__(self, name):
        return getattr(get_vector_search_engine(), name)

vector_search_engine = _VectorSearchProxy()