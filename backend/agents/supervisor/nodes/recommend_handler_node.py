"""
Recommend Handler Node
Supervisor에서 Recommend Agent를 호출하고 결과를 처리하는 노드입니다.
"""

import asyncio
import logging
import base64
from typing import Dict, Any

from backend.agents.supervisor.models import SupervisorState
from backend.agents.recommend.agent.graph import run_recommend
from backend.common.github_client import fetch_readme
from backend.core.docs_core import analyze_documentation
from backend.core.activity_core import analyze_activity_optimized
from backend.core.scoring_core import compute_onboarding_score

logger = logging.getLogger(__name__)

async def calculate_onboarding_score(owner: str, repo: str) -> int:
    """프로젝트의 온보딩 점수를 빠르게 계산"""
    try:
        # README 가져오기 (docs 분석에 필요)
        readme_task = asyncio.create_task(
            asyncio.to_thread(fetch_readme, owner, repo)
        )
        # Activity 분석 (owner, repo 문자열 직접 사용 가능)
        activity_task = asyncio.create_task(
            asyncio.to_thread(analyze_activity_optimized, owner, repo)
        )
        
        readme_content, activity_result = await asyncio.gather(
            readme_task, activity_task, return_exceptions=True
        )
        
        # 에러 처리
        docs_score = 50  # 기본값
        activity_score = 50  # 기본값
        
        # Docs 분석 (README 내용 직접 전달)
        # fetch_readme는 dict를 반환, content 필드에 base64 인코딩된 README가 있음
        if not isinstance(readme_content, Exception) and readme_content:
            try:
                # Base64 디코딩하여 실제 README 텍스트 추출
                encoded_content = readme_content.get("content", "")
                if encoded_content:
                    readme_text = base64.b64decode(encoded_content).decode("utf-8")
                    docs_result = analyze_documentation(readme_text)
                    docs_score = docs_result.total_score  # 문서 품질 점수 (0-100)
                else:
                    logger.warning(f"[ONBOARDING] README content is empty for {owner}/{repo}")
            except Exception as e:
                logger.warning(f"[ONBOARDING] docs_core failed for {owner}/{repo}: {e}")
        else:
            logger.warning(f"[ONBOARDING] README fetch failed for {owner}/{repo}: {readme_content}")
            
        # Activity 분석 결과 (ActivityCoreResult 객체)
        if not isinstance(activity_result, Exception):
            activity_score = activity_result.total_score  # 객체 속성 접근
        else:
            logger.warning(f"[ONBOARDING] activity_core failed for {owner}/{repo}: {activity_result}")
        
        onboarding = compute_onboarding_score(docs_score, activity_score)
        logger.info(f"[ONBOARDING] {owner}/{repo}: docs={docs_score}, activity={activity_score}, onboarding={onboarding}")
        return onboarding
        
    except Exception as e:
        logger.warning(f"Failed to calculate onboarding score for {owner}/{repo}: {e}")
        return 0  # 계산 실패시 0 반환 (필터링됨)

async def run_recommend_agent_node(state: SupervisorState) -> Dict[str, Any]:
    """추천 에이전트 실행 (onboarding 점수 기반 프로젝트 추천)
    
    Note: 추천은 진단 결과만 참고하며, 보안 분석은 제외합니다.
    유사도 0.3 이상 + 온보딩 점수 40점 이상인 프로젝트만 추천합니다.
    """
    logger.info("Running Recommend Agent (with onboarding score filter)")
    
    try:
        owner = state.get("owner", "")
        repo = state.get("repo", "")
        user_message = state.get("user_message", "")
        
        # 추천 에이전트 실행 (Intent Parsing 활성화: Trend vs Semantic 구분을 위해)
        result = await run_recommend(
            owner=owner,
            repo=repo,
            user_message=user_message,
            skip_intent_parsing=False
        )
        
        # 결과 포맷팅 - Pydantic 모델과 dict 모두 처리
        if hasattr(result, 'search_results'):
            search_results = result.search_results
        elif isinstance(result, dict):
            search_results = result.get("search_results", [])
        else:
            search_results = []
            
        if hasattr(result, 'final_summary'):
            final_summary = result.final_summary
        elif isinstance(result, dict):
            final_summary = result.get("final_summary", "")
        else:
            final_summary = ""
            
        logger.info(f"[RECOMMEND] Vector search returned {len(search_results)} candidates")
        
        # 1단계: 유사도 0.3 이상 필터링
        similarity_filtered = []
        for item in search_results:
            if hasattr(item, "score"):
                rerank_score = getattr(item, "score", 0) or 0
                if rerank_score >= 0.3:
                    similarity_filtered.append({
                        # 백엔드 필드
                        "owner": getattr(item, "owner", ""),
                        "name": getattr(item, "name", ""),
                        "full_name": f"{getattr(item, 'owner', '')}/{getattr(item, 'name', '')}",
                        "description": getattr(item, "description", ""),
                        "stars": getattr(item, "stars", 0),
                        "html_url": getattr(item, "html_url", ""),
                        "main_language": getattr(item, "main_language", ""),
                        "similarity_score": rerank_score,
                        "ai_reason": getattr(item, "ai_reason", "") or getattr(item, "match_snippet", ""),
                        # 프론트엔드 호환 필드
                        "url": getattr(item, "html_url", ""),
                        "language": getattr(item, "main_language", ""),
                        "reason": getattr(item, "ai_reason", "") or getattr(item, "match_snippet", ""),
                        "similarity": rerank_score,
                    })
            elif isinstance(item, dict):
                rerank_score = item.get("score", 0) or item.get("rerank_score", 0) or 0
                if rerank_score >= 0.3:
                    item["similarity_score"] = rerank_score
                    item["similarity"] = rerank_score  # 프론트엔드 호환
                    item["url"] = item.get("html_url", "")
                    item["language"] = item.get("main_language", "")
                    item["reason"] = item.get("ai_reason", "")
                    similarity_filtered.append(item)
        
        logger.info(f"[RECOMMEND] After similarity filter (>=0.3): {len(similarity_filtered)} candidates")
        
        # 2단계: 온보딩 점수 50점 이상 필터링, 상위 6개 추천
        formatted_result = {
            "type": "recommend",
            "recommendations": [],
            "summary": final_summary
        }
        
        if similarity_filtered:
            # 온보딩 점수 병렬 계산
            onboarding_tasks = [
                calculate_onboarding_score(item["owner"], item["name"])
                for item in similarity_filtered
            ]
            onboarding_scores = await asyncio.gather(*onboarding_tasks, return_exceptions=True)
            
            # 모든 항목에 온보딩 점수 추가 후 50점 이상만 필터링
            candidates_with_scores = []
            for item, onboarding in zip(similarity_filtered, onboarding_scores):
                if isinstance(onboarding, Exception):
                    onboarding = 0
                
                item["onboarding_score"] = onboarding
                
                if onboarding >= 40:
                    candidates_with_scores.append(item)
                    logger.info(f"[RECOMMEND] ✅ {item['full_name']}: similarity={item['similarity_score']:.2f}, onboarding={onboarding}")
                else:
                    logger.info(f"[RECOMMEND] ❌ {item['full_name']}: onboarding={onboarding} (filtered out, threshold=40)")
            
            # 온보딩 점수로 정렬 (내림차순), 상위 6개만 선택
            candidates_with_scores.sort(key=lambda x: x["onboarding_score"], reverse=True)
            formatted_result["recommendations"] = candidates_with_scores[:6]
            # 프론트엔드 리포트 호환성을 위해 similar_projects도 설정
            formatted_result["similar_projects"] = candidates_with_scores[:6]
        
        logger.info(f"[RECOMMEND] Final recommendations (onboarding>=40, top 6): {len(formatted_result['recommendations'])} projects")
        
        # 메타인지: 추천 품질 체크
        rec_count = len(formatted_result["recommendations"])
        if rec_count >= 5:
            quality = "high"
            confidence = 0.9
        elif rec_count >= 2:
            quality = "medium"
            confidence = 0.7
        else:
            quality = "low"
            confidence = 0.4
        
        logger.info(f"[METACOGNITION] Recommend completed:")
        logger.info(f"  - Recommendations: {rec_count}")
        logger.info(f"  - Quality: {quality} (confidence: {confidence:.02f})")
        
        # 사용자 메시지에 '온보딩' 키워드가 있으면 onboarding도 추가 실행
        user_message = state.get("user_message", "").lower()
        additional_agents = []
        if "온보딩" in user_message or "onboarding" in user_message or "기여" in user_message or "contribution" in user_message:
            additional_agents.append("onboarding")
            logger.info("Adding onboarding agent to recommend request (keyword detected)")
        
        return {
            "agent_result": formatted_result,
            "recommend_result": formatted_result,
            "additional_agents": additional_agents,
            "iteration": state.get("iteration", 0) + 1
        }
        
    except ImportError as e:
        logger.warning(f"Recommend agent import failed: {e}")
        return {
            "agent_result": {
                "type": "recommend",
                "message": f"추천 에이전트 모듈 로드 실패: {e}",
                "status": "import_error"
            },
            "additional_agents": [],  # security 제외
            "iteration": state.get("iteration", 0) + 1
        }
    except Exception as e:
        logger.error(f"Recommend agent failed: {e}")
        return {
            "agent_result": {
                "type": "recommend",
                "message": f"추천 에이전트 실행 오류: {e}",
                "status": "error"
            },
            "additional_agents": [],  # security 제외
            "iteration": state.get("iteration", 0) + 1
        }
