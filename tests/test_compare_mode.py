"""비교 모드 통합 테스트"""
import sys
sys.path.insert(0, ".")

from unittest.mock import patch, MagicMock
from backend.agents.supervisor.nodes.intent_classifier import classify_intent_node
from backend.agents.supervisor.models import SupervisorState


def mock_llm_response_compare():
    """비교 intent를 반환하는 mock LLM 응답"""
    return """{
  "task_type": "compare_two_repos",
  "repo_url": null,
  "compare_repo_url": null,
  "user_context": {}
}"""


def test_compare_intent_with_fallback():
    """
    비교 모드에서 LLM이 repo를 파싱하지 못했을 때 
    fallback으로 정규식이 두 저장소를 추출하는지 테스트
    """
    print("=== 비교 모드 fallback 테스트 ===\n")
    
    initial_state: SupervisorState = {
        "user_query": "facebook/react와 vuejs/vue를 비교해줘",
        "task_type": "",
        "intent": "",
        "history": [],
    }
    
    with patch(
        "backend.agents.supervisor.nodes.intent_classifier._call_intent_llm",
        return_value=mock_llm_response_compare()
    ):
        result = classify_intent_node(initial_state)
    
    print(f"Task type: {result.get('task_type')}")
    print(f"Repo: {result.get('repo')}")
    print(f"Compare repo: {result.get('compare_repo')}")
    
    # 검증
    assert result.get("task_type") == "compare_two_repos", f"Expected compare_two_repos, got {result.get('task_type')}"
    
    repo = result.get("repo")
    compare_repo = result.get("compare_repo")
    
    assert repo is not None, "repo가 None입니다"
    assert compare_repo is not None, "compare_repo가 None입니다"
    
    assert repo["name"] == "react", f"Expected react, got {repo['name']}"
    assert repo["owner"] == "facebook", f"Expected facebook, got {repo['owner']}"
    
    assert compare_repo["name"] == "vue", f"Expected vue, got {compare_repo['name']}"
    assert compare_repo["owner"] == "vuejs", f"Expected vuejs, got {compare_repo['owner']}"
    
    print("\n[PASS] 비교 모드 fallback 테스트 성공!")


def test_compare_intent_korean_suffixes():
    """다양한 한글 접미사 테스트"""
    print("\n=== 한글 접미사 테스트 ===\n")
    
    test_queries = [
        ("angular/angular과 sveltejs/svelte를 비교해줘", "angular", "svelte"),
        ("microsoft/vscode와 atom/atom 비교", "vscode", "atom"),
    ]
    
    for query, expected_repo, expected_compare in test_queries:
        initial_state: SupervisorState = {
            "user_query": query,
            "task_type": "",
            "intent": "",
            "history": [],
        }
        
        with patch(
            "backend.agents.supervisor.nodes.intent_classifier._call_intent_llm",
            return_value=mock_llm_response_compare()
        ):
            result = classify_intent_node(initial_state)
        
        repo = result.get("repo")
        compare_repo = result.get("compare_repo")
        
        print(f"Query: {query}")
        print(f"  repo: {repo['name'] if repo else None}")
        print(f"  compare_repo: {compare_repo['name'] if compare_repo else None}")
        
        assert repo is not None and repo["name"] == expected_repo, f"Expected {expected_repo}"
        assert compare_repo is not None and compare_repo["name"] == expected_compare, f"Expected {expected_compare}"
        print("  [PASS]")
    
    print("\n[PASS] 한글 접미사 테스트 성공!")


if __name__ == "__main__":
    test_compare_intent_with_fallback()
    test_compare_intent_korean_suffixes()
    print("\n" + "=" * 50)
    print("모든 비교 모드 테스트 통과!")
    print("=" * 50)
