"""비교 모드 정규식 테스트"""
import sys
sys.path.insert(0, ".")

from backend.agents.supervisor.nodes.intent_classifier import _extract_all_repos_from_query

def test_extract_all_repos():
    """여러 저장소 추출 테스트"""
    test_cases = [
        ("facebook/react와 vuejs/vue를 비교해줘", ["react", "vue"]),
        ("angular/angular과 sveltejs/svelte 비교", ["angular", "svelte"]),
        ("microsoft/vscode, electron/electron 비교", ["vscode", "electron"]),
    ]
    
    for query, expected_names in test_cases:
        repos = _extract_all_repos_from_query(query)
        actual_names = [r["name"] for r in repos]
        
        print(f"Query: {query}")
        print(f"  Expected: {expected_names}")
        print(f"  Actual:   {actual_names}")
        
        if actual_names == expected_names:
            print("  [PASS]")
        else:
            print("  [FAIL]")
        print()

if __name__ == "__main__":
    test_extract_all_repos()
