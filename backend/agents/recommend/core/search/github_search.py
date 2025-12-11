import logging
from backend.agents.recommend.adapters.github_client import github_instance as client
from backend.agents.recommend.core.github.parser import GitHubParser
from backend.agents.recommend.core.github.schema import GitHubSearchInput
from typing import List, Dict

logger = logging.getLogger(__name__)

class GitHubSearch:
    """GitHub Search API 호출 + 최소 파싱"""

    def __init__(self):
        self.client = client

    def search_repositories(self, params: dict) -> List[Dict]:
        print("\n🟢 [GitHubSearch] Starting API search process...")
        
        try:
            # 1. Pydantic 변환 및 유효성 검사
            print("   [Step 1] Validating input parameters with Pydantic...")
            input_model = GitHubSearchInput(**params)
            
        except Exception as e:
            logger.error(f"[GitHubSearch] Pydantic validation failed: {e}")
            print(f"❌ [Step 1] Validation failed: {e}")
            return []

        # 2. Search API 호출
        try:
            print(f"   [Step 2] Calling GitHub Search API. Query: '{input_model.q}'")
            raw_items = self.client.search_repos(input_model)
            
            item_count = len(raw_items) if raw_items and 'items' in raw_items else 0
            print(f"   [API Result] Received {item_count} raw items.")
            
        except Exception as e:
            logger.error(f"[GitHubSearch] API call failed: {e}")
            print(f"❌ [Step 2] GitHub API call failed: {e}")
            return []

        # 3. 최소 정보만 파싱
        try:
            print("   [Step 3] Parsing raw items into required schema.")
            parsed_results = GitHubParser.parse_github_search_results(raw_items)
            
            print(f"✅ [Result] Successfully parsed {len(parsed_results)} repositories.")
            return parsed_results
            
        except Exception as e:
            logger.error(f"[GitHubSearch] Parsing failed: {e}")
            print(f"❌ [Step 3] Final parsing failed: {e}")
            return []