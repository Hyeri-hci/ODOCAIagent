import json
from langchain_core.tools import tool
from typing import Dict, Any, List, Annotated
from langgraph.prebuilt import InjectedState # 👈 핵심: State 주입용

# core 모듈 임포트
from core.search.repo_filter import RepoFilter
from core.github.schema import ParsedRepo

@tool
def github_filter_tool(state: Annotated[dict, InjectedState]) -> str:
    """
    [Verification & Filtering Tool]
    검색된 결과(raw_candidates)에 대해 LLM이 생성한 추가 조건(issue, pr, update 등)을 기반으로
    정밀 필터링 및 검증을 수행하고, 점수 정렬 후 결과를 반환합니다.
    """
    try:
        # 1. State에서 데이터 직접 꺼내기
        repos = state.get("raw_candidates", [])
        queries = state.get("search_queries", [])
        
        if not queries or not repos:
            # 쿼리가 없거나 리포지토리가 없으면 빈 리스트 반환
            return json.dumps({"filtered_candidates": []}, ensure_ascii=False)

        query_result = queries[-1]

        # 2. 'other' 조건이 없으면 필터링 불필요 (성능 최적화)
        if not query_result.get("other"):
            return json.dumps({"filtered_candidates": repos}, ensure_ascii=False, default=str)

        # 3. 필터링 로직 수행 (RepoFilter는 Dict 리스트를 받아 필터링 한다고 가정)
        repo_filter = RepoFilter()
        
        # 💡 [최적화] 필터링 내부에서 Dict -> Pydantic -> Dict 변환 과정을 수행합니다.
        #    RepoFilter는 Dict 리스트를 반환한다고 가정합니다.
        filtered_results_dict = repo_filter.filter_repositories(repos, query_result)

        # 4. 결과 반환 (State의 필드명과 일치시켜 final_rec 노드로 전달)
        data_to_return = {
            "filtered_candidates": filtered_results_dict
        }
        
        return json.dumps(data_to_return, ensure_ascii=False, default=str)

    except Exception as e:
        # 에러 발생 시 에러 메시지 반환
        return json.dumps({"error": f"Filter tool error: {str(e)}"}, ensure_ascii=False)