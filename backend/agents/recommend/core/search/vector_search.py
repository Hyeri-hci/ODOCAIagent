# core/search/vector_search.py
import json
import logging
import numpy as np
from typing import Dict, Any, List, Optional, Union
from qdrant_client import models
from flashrank import Ranker, RerankRequest
from datetime import timedelta, timezone # build_qdrant_filter에서 필요할 수 있음

# 어댑터 및 스키마 임포트 (경로는 프로젝트 구조에 맞게 조정 필요)
from adapters.qdrant_client import qdrant_client
from adapters.embedding_client import embedding_client
from core.qdrant.schemas import RepoSchema, ReadmeSchema

logger = logging.getLogger(__name__)

# =================================================================
# HELPER 1: JSON 직렬화 오류 방지 (float32 -> float 변환)
# =================================================================
def convert_to_standard_types(data):
    """NumPy/Numpy 기반의 float32/64 등을 표준 Python float/int로 변환"""
    if isinstance(data, dict):
        return {k: convert_to_standard_types(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [convert_to_standard_types(item) for item in data]
        
    # 🌟 [핵심 수정] np.float 대신 표준 float을 사용하거나, 명시적인 np.float64를 사용합니다.
    # 표준 float과 명시적인 NumPy 타입만 체크하도록 수정합니다.
    elif isinstance(data, (np.float32, np.float64, float)): 
        return float(data)
        
    elif isinstance(data, (np.integer, np.int64)):
        return int(data)
    else:
        return data

# -------------------------------------------------------------------
# HELPER 2: 필터 빌더 (Metadata + Keyword + ID)
# -------------------------------------------------------------------
def build_qdrant_filter(
    filters: Dict[str, Any] = None, 
    keywords: List[str] = None, 
    target_field: str = None,
    candidate_ids: List[int] = None
) -> Optional[models.Filter]:
    """
    Qdrant 필터 객체를 생성합니다. (이전 제공 코드와 동일)
    """
    must_conditions = []
    
    # --- Helper Function for Range Logic ---
    def _create_range_condition(key: str, value: Any) -> Optional[models.FieldCondition]:
        range_obj = None
        if isinstance(value, (int, float)) or (isinstance(value, str) and value.isdigit()):
            range_obj = models.Range(gte=int(value))
        elif isinstance(value, list) and len(value) == 2:
            range_obj = models.Range(gte=value[0], lte=value[1])
        elif isinstance(value, dict):
            range_obj = models.Range(**value)
            
        if range_obj:
            return models.FieldCondition(key=key, range=range_obj)
        return None
    # ---------------------------------------

    # 1. ID 필터링
    if candidate_ids:
        must_conditions.append(models.FieldCondition(
            key=RepoSchema.FIELD_PROJECT_ID, 
            match=models.MatchAny(any=candidate_ids)
        ))

    # 2. 메타데이터 필터 (Language, Stars, Forks 등)
    if filters:
        if filters.get("language"):
             # ... (언어 필터링 로직 생략) ...
             lang_input = filters["language"]
             if isinstance(lang_input, list):
                 corrected_langs = []
                 for l in lang_input:
                     if isinstance(l, str):
                         if l.lower() == 'javascript': l = 'JavaScript'
                         elif l.lower() == 'typescript': l = 'TypeScript'
                         else: l = l.capitalize()
                         corrected_langs.append(l)
                 must_conditions.append(models.FieldCondition(
                     key=RepoSchema.FIELD_MAIN_LANG,
                     match=models.MatchAny(any=corrected_langs)
                 ))
             else:
                 lang = lang_input
                 if isinstance(lang, str):
                     if lang.lower() == 'javascript': lang = 'JavaScript'
                     elif lang.lower() == 'typescript': lang = 'TypeScript'
                     else: lang = lang.capitalize() 
                 must_conditions.append(models.FieldCondition(
                     key=RepoSchema.FIELD_MAIN_LANG,
                     match=models.MatchValue(value=lang) 
                 ))
        
        # License
        if filters.get("license"):
            must_conditions.append(models.FieldCondition(
                key=RepoSchema.FIELD_LICENSE,
                match=models.MatchValue(value=filters["license"])
            ))

        # Stars & Forks
        stars_val = filters.get("stars") or filters.get("min_stars")
        if stars_val:
            cond = _create_range_condition(RepoSchema.FIELD_STARS, stars_val)
            if cond: must_conditions.append(cond)
            
        forks_val = filters.get("forks") or filters.get("min_forks")
        if forks_val:
            cond = _create_range_condition(RepoSchema.FIELD_FORKS, forks_val)
            if cond: must_conditions.append(cond)

        # Topics
        if filters.get("topics"):
            must_conditions.append(models.FieldCondition(
                key=RepoSchema.FIELD_TOPICS,
                match=models.MatchAny(any=filters["topics"])
            ))

    # 3. 키워드 필터 (Step 2에서 본문 검색용)
    min_should_obj = None
    if keywords and target_field:
        kw_conditions = []
        for kw in keywords:
            kw_conditions.append(models.FieldCondition(
                key=target_field,
                match=models.MatchText(text=kw)
            ))
        
        if kw_conditions:
            min_should_obj = models.MinShould(
                conditions=kw_conditions,
                min_count=1 
            )

    if must_conditions or min_should_obj:
        return models.Filter(
            must=must_conditions if must_conditions else None,
            min_should=min_should_obj
        )
    return None

# -------------------------------------------------------------------
# VectorSearch Class
# -------------------------------------------------------------------
class VectorSearch:
    def __init__(self, broad_k: int = 100, fine_k: int = 5):
        self.embedding_client = embedding_client
        self.db_client = qdrant_client
        self.broad_k = broad_k
        self.fine_k = fine_k
        
        print("🚀 [VectorSearch] Reranker 모델 로딩 중...")
        # Ranker 객체 초기화 (AttributeError 해결)
        self.ranker = Ranker(model_name="ms-marco-TinyBERT-L-2-v2", cache_dir="./model_cache")
        print("✅ [VectorSearch] Reranker 모델 로딩 완료.")

    def search(self, query: str, filters: Optional[Dict[str, Any]] = None, keywords: List[str] = None) -> Dict[str, Any]:
        try:
            print(f"\n=========================================================================")
            print(f"🔍 [VectorSearch] Starting 3-Step Semantic Search for: '{query}'")
            print(f"=========================================================================")
            
            # ... (Step 1, 2, 3, 4 검색 및 재순위 지정 로직 유지) ...
            
            # 1. 쿼리 벡터화
            query_vector = self.embedding_client.embed_query(query)
            
            
            # =========================================================
            # [Step 1] Broad Search (Desc DB)
            # =========================================================
            print(f"\n[Step 1] Broad Search (Desc DB, K={self.broad_k})...")
            
            broad_filter = build_qdrant_filter(
                filters=filters, 
                keywords=None, 
                target_field=RepoSchema.FIELD_DESC
            )
            
            print(f"   - Qdrant Filter applied: {'Yes' if broad_filter else 'No'}")

            candidates = self.db_client.search(
                embedding=query_vector, 
                collection_type='desc', 
                top_k=self.broad_k, 
                qdrant_filter=broad_filter,
                hnsw_ef=1024
            )
            
            print(f"   - Initial candidates found: {len(candidates)}.")
            
            # 1-2. [확장 검색] 결과가 너무 적으면 필터 완화
            min_candidates_needed = self.broad_k // 2
            
            if len(candidates) < min_candidates_needed and filters:
                print(f"   ⚠️ 1차 후보 부족 ({len(candidates)}개). 필터를 완화하여 확장 검색합니다.")
                
                relaxed_filters = filters.copy()
                relaxed_filters.pop("min_stars", None)
                relaxed_filters.pop("stars", None)
                relaxed_filters.pop("min_forks", None)
                relaxed_filters.pop("forks", None)
                
                if relaxed_filters != filters:
                    relaxed_filter_obj = build_qdrant_filter(
                        filters=relaxed_filters,
                        keywords=None,
                        target_field=RepoSchema.FIELD_DESC
                    )
                    
                    fill_count = self.broad_k - len(candidates)
                    extra_candidates = self.db_client.search(
                        embedding=query_vector, 
                        collection_type='desc', 
                        top_k=fill_count, 
                        qdrant_filter=relaxed_filter_obj,
                        hnsw_ef=512
                    )
                    
                    existing_ids = {c['id'] for c in candidates}
                    for extra in extra_candidates:
                        if extra['id'] not in existing_ids:
                            candidates.append(extra)
                            existing_ids.add(extra['id'])
                            
                    print(f"   ✅ 확장 검색 후 총 후보: {len(candidates)}개")

            if not candidates:
                print("❌ [Step 1 Fail] 최종 후보 확보 실패.")
                return {
                    "search_query": query, 
                    "message": "조건에 맞는 프로젝트를 전혀 찾지 못했습니다.",
                    "final_recommendations": []
                }

            candidate_ids = [item['id'] for item in candidates]
            print(f"   - IDs passed to Step 2: {len(candidate_ids)}.")

            # =========================================================
            # [Step 2] Fine Search (Readme DB)
            # =========================================================
            print(f"\n[Step 2] Fine Search (Readme DB, Target K={self.fine_k * 3})...")
            
            fine_filter = build_qdrant_filter(
                filters=None, 
                keywords=keywords, 
                target_field=ReadmeSchema.FIELD_CONTENT,
                candidate_ids=candidate_ids 
            )
            
            print(f"   - Readme Filter applied: {'Yes' if fine_filter else 'No'}. Keywords used: {keywords is not None}")

            raw_results = self.db_client.search(
                embedding=query_vector, 
                collection_type='readme', 
                top_k=self.fine_k * 3, 
                qdrant_filter=fine_filter,
                hnsw_ef=512
            )
            print(f"   - Step 2 Readme results found: {len(raw_results)}.")

            # [Fallback] Readme 키워드 매칭 실패 시 ID로만 재검색
            if (not raw_results or len(raw_results) < self.fine_k) and keywords:
                print(f"   ⚠️ Readme 매칭 부족. 키워드 필터 없이 보충 검색 수행.")
                
                found_ids = {r['id'] for r in raw_results}
                remaining_ids = [cid for cid in candidate_ids if cid not in found_ids]
                
                if remaining_ids:
                    fallback_filter = build_qdrant_filter(
                        filters=None, 
                        keywords=None, 
                        candidate_ids=remaining_ids
                    )
                    needed = (self.fine_k * 2) - len(raw_results)
                    fallback_results = self.db_client.search(
                        embedding=query_vector, 
                        collection_type='readme', 
                        top_k=max(needed, 5),
                        qdrant_filter=fallback_filter,
                        hnsw_ef=512
                    )
                    raw_results.extend(fallback_results)
                    print(f"   ✅ 보충 검색 후 Readme 총 결과: {len(raw_results)}개.")


            if not raw_results:
                print("   ⚠️ Readme 데이터 없음. Description 결과로 대체합니다.")
                final_fallback = []
                for cand in candidates[:self.fine_k]:
                     cand_filled = cand.copy()
                     desc_text = cand.get('desc', '설명 없음')
                     cand_filled['content'] = f"[Description] {desc_text}"
                     final_fallback.append(cand_filled)
                        
                return {
                     "search_query": query,
                     "final_recommendations": final_fallback
                }

            # =========================================================
            # [Step 3] Grouping & Reranking
            # =========================================================
            print(f"\n[Step 3] Grouping & Reranking (Fine K={self.fine_k})...")
            
            seen_project_ids = set()
            unique_results = []
            
            for res in raw_results:
                pid = res.get('id')
                if pid not in seen_project_ids:
                    seen_project_ids.add(pid)
                    unique_results.append({
                        "id": pid,
                        "text": res.get('content', ''), 
                        "meta": res 
                    })
            
            print(f"   - Unique projects for Reranking: {len(unique_results)}.")

            final_recommendations = []
            if unique_results:
                # 3-1. Reranking 수행
                rerank_request = RerankRequest(query=query, passages=unique_results)
                ranked_results = self.ranker.rerank(rerank_request)
                
                final_top_k = ranked_results[:self.fine_k]
                
                for item in final_top_k:
                    original_data = item['meta']
                    original_data['rerank_score'] = item['score'] 
                    
                    # [Source Marking] Readme에서 찾은 경우 출처 표시
                    raw_content = original_data.get('content', '')
                    original_data['content'] = f"[Readme] {raw_content}"
                    
                    final_recommendations.append(original_data)
            else:
                print("   ⚠️ Rerank할 유효 데이터 없음. Description 결과로 대체합니다.")
                for cand in candidates[:self.fine_k]:
                     cand_filled = cand.copy()
                     desc_text = cand.get('desc', '설명 없음')
                     cand_filled['content'] = f"[Description] {desc_text}"
                     final_recommendations.append(cand_filled)

            # =========================================================
            # [Step 4] Final Padding (최종 보충)
            # =========================================================
            if len(final_recommendations) < self.fine_k:
                print(f"   ⚠️ 최종 결과 부족 ({len(final_recommendations)}/{self.fine_k}). Desc 후보군에서 보충합니다.")
                existing_final_ids = {item.get('id') for item in final_recommendations}
                
                for cand in candidates:
                    if len(final_recommendations) >= self.fine_k:
                        break
                    
                    if cand['id'] not in existing_final_ids:
                        cand_filled = cand.copy()
                        desc_text = cand.get('desc', '설명 없음')
                        cand_filled['content'] = f"[Description] {desc_text}"
                        
                        final_recommendations.append(cand_filled)

            print(f"✅ [VectorSearch Complete] Total final recommendations: {len(final_recommendations)}.")

            return {
                "search_query": query,
                "final_recommendations": final_recommendations
            }

        except Exception as e:
            logger.error(f"❌ [VectorSearch] Critical Error: {e}")
            return {"error": str(e), "final_recommendations": []}

# 싱글톤 인스턴스
vector_search_engine = VectorSearch()