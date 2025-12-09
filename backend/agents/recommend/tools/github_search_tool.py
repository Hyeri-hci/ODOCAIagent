# tools/github_search_tool.py

import json
from langchain.tools import tool
from core.search.github_search import GitHubSearch
from typing import List, Dict, Any

@tool
def github_search_tool(params: Dict[str, Any]) -> str:
    """
    [Search Tool]
    GitHub API를 사용하여 리포지토리를 검색합니다.
    입력된 params('q', 'sort', 'order')를 기반으로 검색을 수행하고,
    핵심 정보만 요약된 리포지토리 목록(최대 15~20개)을 반환합니다.
    """
    
    try:
        # Core 로직 호출
        search = GitHubSearch()
        results = search.search_repositories(params) # List[ParsedRepo] 반환됨

        # 1. Pydantic 객체 -> List[Dict] 변환
        data = [repo.model_dump() for repo in results]
        
        # 2. [수정] List[Dict] -> JSON String 변환
        # Agent가 텍스트로 읽을 수 있도록 변환해줍니다.
        return json.dumps(data, ensure_ascii=False, default=str)

    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)