"""
Supervisor 통합 테스트

모든 Intent에 대한 유닛 테스트 + E2E 테스트를 수행합니다.

테스트 항목:
1. 유닛 테스트 (Mock 사용, 빠름)
   - 라우팅 테스트
   - 프롬프트 매핑 테스트
   - 미지원 Intent 가드 테스트
   - user_level/intent 유효성 테스트
   - Diagnosis task_type 매핑 테스트
   - 비교 모드 정규식 테스트
   - 비교 모드 fallback 테스트

2. E2E 테스트 (실제 LLM 호출, 느림)
   - Health 모드
   - Onboarding 모드 (레벨별)
   - Explain Scores 모드
   - Compare 모드
"""

import sys
import os
from pathlib import Path
from unittest.mock import patch

# 프로젝트 루트 경로 추가
sys.path.insert(0, str(Path(__file__).parent.parent.absolute()))

# Windows 콘솔 인코딩 설정
if sys.platform == "win32":
    os.system("chcp 65001 > nul 2>&1")

import logging
logging.basicConfig(level=logging.WARNING, format="%(name)s - %(message)s")


# ============================================================================
# 1. 유닛 테스트 (Mock 사용)
# ============================================================================

def test_routing():
    """라우팅 테스트 - INTENT_CONFIG 기반"""
    from backend.agents.supervisor.graph import route_after_mapping
    from backend.agents.supervisor.intent_config import INTENT_CONFIG, is_intent_ready, is_refine_intent
    
    print("=" * 70)
    print("1. 라우팅 테스트")
    print("=" * 70)
    
    for intent, config in INTENT_CONFIG.items():
        # refine_onboarding_tasks는 이전 컨텍스트에 따라 분기
        if is_refine_intent(intent):
            # 이전 컨텍스트 없을 때 → run_diagnosis
            state_no_context = {"task_type": intent}
            route = route_after_mapping(state_no_context)
            expected = "run_diagnosis"
            assert route == expected, f"{intent} without context: {route} != {expected}"
            print(f"[PASS] {intent:30} (no context) -> {route}")
            
            # 이전 컨텍스트 있을 때 → refine_tasks
            state_with_context = {
                "task_type": intent,
                "last_task_list": [{"title": "test task"}],
            }
            route = route_after_mapping(state_with_context)
            expected = "refine_tasks"
            assert route == expected, f"{intent} with context: {route} != {expected}"
            print(f"[PASS] {intent:30} (with context) -> {route}")
        else:
            state = {"task_type": intent}
            route = route_after_mapping(state)
            
            if not is_intent_ready(intent):
                expected = "summarize"
            elif config["needs_diagnosis"]:
                expected = "run_diagnosis"
            else:
                expected = "summarize"
            
            ready_note = "" if is_intent_ready(intent) else " (not ready)"
            assert route == expected, f"{intent}: {route} != {expected}"
            print(f"[PASS] {intent:30} -> {route}{ready_note}")
    
    print()


def test_prompt_mapping():
    """프롬프트 매핑 테스트 - INTENT_CONFIG 기반"""
    from backend.agents.supervisor.nodes.summarize_node import _get_prompt_for_intent
    from backend.agents.supervisor.intent_config import INTENT_CONFIG
    
    print("=" * 70)
    print("2. 프롬프트 매핑 테스트")
    print("=" * 70)
    
    for intent, config in INTENT_CONFIG.items():
        prompt = _get_prompt_for_intent(intent, "beginner")
        prompt_kind = config["prompt_kind"]
        
        has_prompt = prompt is not None and len(prompt) > 100
        assert has_prompt, f"{intent}: prompt_kind={prompt_kind}, len={len(prompt) if prompt else 0}"
        print(f"[PASS] {intent:30} -> prompt_kind={prompt_kind}, len={len(prompt) if prompt else 0}")
    
    print()


def test_not_ready_guard():
    """미지원 Intent 가드 테스트"""
    from backend.agents.supervisor.nodes.summarize_node import _get_not_ready_message
    from backend.agents.supervisor.intent_config import INTENT_CONFIG, is_intent_ready
    
    print("=" * 70)
    print("3. 미지원 Intent 가드 테스트")
    print("=" * 70)
    
    for intent, config in INTENT_CONFIG.items():
        ready = is_intent_ready(intent)
        
        if not ready:
            message = _get_not_ready_message(intent)
            has_message = "준비 중" in message or "개발 중" in message
            assert has_message, f"{intent}: message doesn't contain expected text"
            print(f"[PASS] {intent:30} -> is_ready=False, message_ok={has_message}")
        else:
            print(f"[SKIP] {intent:30} -> is_ready=True (가드 불필요)")
    
    print()


def test_user_level_validation():
    """user_level 유효성 테스트"""
    from backend.agents.supervisor.intent_config import validate_user_level
    
    print("=" * 70)
    print("4. user_level 유효성 테스트")
    print("=" * 70)
    
    test_cases = [
        ("beginner", "beginner"),
        ("intermediate", "intermediate"),
        ("advanced", "advanced"),
        ("expert", "beginner"),
        ("", "beginner"),
        (None, "beginner"),
        ("BEGINNER", "beginner"),
    ]
    
    for input_val, expected in test_cases:
        result = validate_user_level(input_val)
        assert result == expected, f"validate_user_level({repr(input_val)}): {result} != {expected}"
        print(f"[PASS] validate_user_level({repr(input_val):15}) -> {result}")
    
    print()


def test_intent_validation():
    """intent 유효성 테스트"""
    from backend.agents.supervisor.intent_config import validate_intent
    
    print("=" * 70)
    print("5. Intent 유효성 테스트")
    print("=" * 70)
    
    test_cases = [
        ("diagnose_repo_health", "diagnose_repo_health"),
        ("diagnose_repo_onboarding", "diagnose_repo_onboarding"),
        ("explain_scores", "explain_scores"),
        ("compare_two_repos", "compare_two_repos"),
        ("invalid_intent", "diagnose_repo_health"),
        ("", "diagnose_repo_health"),
        (None, "diagnose_repo_health"),
    ]
    
    for input_val, expected in test_cases:
        result = validate_intent(input_val)
        assert result == expected, f"validate_intent({repr(input_val)}): {result} != {expected}"
        print(f"[PASS] validate_intent({repr(input_val):30}) -> {result}")
    
    print()


def test_diagnosis_task_type_mapping():
    """Diagnosis task_type 매핑 테스트"""
    from backend.agents.supervisor.nodes.task_mapping import map_to_diagnosis_task_type
    from backend.agents.supervisor.intent_config import INTENT_CONFIG
    
    print("=" * 70)
    print("6. Diagnosis task_type 매핑 테스트")
    print("=" * 70)
    
    for intent, config in INTENT_CONFIG.items():
        result = map_to_diagnosis_task_type(intent)
        expected = config["diagnosis_task_type"]
        assert result == expected, f"{intent}: {result} != {expected}"
        print(f"[PASS] {intent:30} -> {result}")
    
    print()


def test_compare_regex():
    """비교 모드 정규식 테스트"""
    from backend.agents.supervisor.nodes.intent_classifier import _extract_all_repos_from_query
    
    print("=" * 70)
    print("7. 비교 모드 정규식 테스트")
    print("=" * 70)
    
    test_cases = [
        ("facebook/react와 vuejs/vue를 비교해줘", ["react", "vue"]),
        ("angular/angular과 sveltejs/svelte 비교", ["angular", "svelte"]),
        ("microsoft/vscode, electron/electron 비교", ["vscode", "electron"]),
    ]
    
    for query, expected_names in test_cases:
        repos = _extract_all_repos_from_query(query)
        actual_names = [r["name"] for r in repos]
        assert actual_names == expected_names, f"'{query}': {actual_names} != {expected_names}"
        print(f"[PASS] '{query[:40]}...' -> {actual_names}")
    
    print()


def test_compare_fallback():
    """비교 모드 fallback 테스트 (LLM mock)"""
    from backend.agents.supervisor.nodes.intent_classifier import classify_intent_node
    
    print("=" * 70)
    print("8. 비교 모드 fallback 테스트")
    print("=" * 70)
    
    mock_response = """{
      "task_type": "compare_two_repos",
      "repo_url": null,
      "compare_repo_url": null,
      "user_context": {}
    }"""
    
    test_cases = [
        ("facebook/react와 vuejs/vue를 비교해줘", "react", "vue"),
        ("angular/angular과 sveltejs/svelte를 비교해줘", "angular", "svelte"),
    ]
    
    for query, expected_repo, expected_compare in test_cases:
        initial_state = {
            "user_query": query,
            "task_type": "",
            "intent": "",
            "history": [],
        }
        
        with patch(
            "backend.agents.supervisor.nodes.intent_classifier._call_intent_llm",
            return_value=mock_response
        ):
            result = classify_intent_node(initial_state)
        
        repo = result.get("repo")
        compare_repo = result.get("compare_repo")
        
        repo_name = repo["name"] if repo else None
        compare_name = compare_repo["name"] if compare_repo else None
        
        assert repo is not None and repo["name"] == expected_repo, f"repo: {repo_name} != {expected_repo}"
        assert compare_repo is not None and compare_repo["name"] == expected_compare, f"compare: {compare_name} != {expected_compare}"
        print(f"[PASS] '{query[:40]}...' -> repo={repo_name}, compare={compare_name}")
    
    print()


def test_multiturn_routing():
    """멀티턴 라우팅 테스트 - refine 시 이전 컨텍스트 체크"""
    from backend.agents.supervisor.graph import route_after_mapping
    
    print("=" * 70)
    print("9. 멀티턴 라우팅 테스트")
    print("=" * 70)
    
    # 케이스 1: refine_onboarding_tasks + 이전 컨텍스트 없음 → run_diagnosis
    state_no_context = {
        "task_type": "refine_onboarding_tasks",
        "is_followup": True,
        "followup_type": "refine_easier",
    }
    route = route_after_mapping(state_no_context)
    assert route == "run_diagnosis", f"No context: {route} != run_diagnosis"
    print(f"[PASS] refine + no context -> {route}")
    
    # 케이스 2: refine_onboarding_tasks + last_task_list 있음 → refine_tasks
    state_with_tasks = {
        "task_type": "refine_onboarding_tasks",
        "is_followup": True,
        "followup_type": "refine_easier",
        "last_task_list": [{"title": "test", "difficulty": "beginner"}],
    }
    route = route_after_mapping(state_with_tasks)
    assert route == "refine_tasks", f"With last_task_list: {route} != refine_tasks"
    print(f"[PASS] refine + last_task_list -> {route}")
    
    # 케이스 3: refine_onboarding_tasks + diagnosis_result.onboarding_tasks 있음 → refine_tasks
    state_with_diagnosis = {
        "task_type": "refine_onboarding_tasks",
        "is_followup": True,
        "followup_type": "refine_harder",
        "diagnosis_result": {
            "onboarding_tasks": {
                "beginner": [{"title": "task1"}],
                "intermediate": [],
                "advanced": [],
            }
        },
    }
    route = route_after_mapping(state_with_diagnosis)
    assert route == "refine_tasks", f"With diagnosis_result: {route} != refine_tasks"
    print(f"[PASS] refine + diagnosis_result -> {route}")
    
    # 케이스 4: follow-up이지만 이전 컨텍스트 필요 없는 경우 → run_diagnosis
    state_followup_no_refine = {
        "task_type": "diagnose_repo_health",
        "is_followup": True,
        "followup_type": "continue_same",
    }
    route = route_after_mapping(state_followup_no_refine)
    assert route == "run_diagnosis", f"Follow-up health: {route} != run_diagnosis"
    print(f"[PASS] follow-up health -> {route}")
    
    print()


def run_unit_tests():
    """모든 유닛 테스트 실행"""
    print("\n" + "=" * 70)
    print("유닛 테스트 시작 (Mock 사용)")
    print("=" * 70 + "\n")
    
    test_routing()
    test_prompt_mapping()
    test_not_ready_guard()
    test_user_level_validation()
    test_intent_validation()
    test_diagnosis_task_type_mapping()
    test_compare_regex()
    test_compare_fallback()
    test_multiturn_routing()
    
    print("모든 유닛 테스트 통과!")


# ============================================================================
# 2. E2E 테스트 (실제 LLM 호출)
# ============================================================================

def run_e2e_tests():
    """E2E 테스트 실행 (실제 LLM 호출)"""
    from backend.agents.supervisor.graph import build_supervisor_graph
    
    print("\n" + "=" * 70)
    print("E2E 테스트 시작 (실제 LLM 호출)")
    print("=" * 70 + "\n")
    
    graph = build_supervisor_graph()
    results = {}
    
    # 테스트 케이스 정의
    test_cases = [
        {
            "name": "Health 모드",
            "query": "facebook/react 건강 상태 분석해줘",
            "expected_intent": "diagnose_repo_health",
        },
        {
            "name": "Onboarding 모드 (초보자)",
            "query": "초보자인데 facebook/react에 기여하고 싶어요",
            "expected_intent": "diagnose_repo_onboarding",
            "expected_level": "beginner",
        },
        {
            "name": "Onboarding 모드 (중급자)",
            "query": "React 2년 사용 경험이 있는데 facebook/react에 기여하고 싶습니다",
            "expected_intent": "diagnose_repo_onboarding",
            "expected_level": "intermediate",
        },
        {
            "name": "Explain Scores 모드",
            "query": "facebook/react 점수가 왜 이렇게 나왔어?",
            "expected_intent": "explain_scores",
        },
        {
            "name": "Compare 모드",
            "query": "facebook/react와 vuejs/vue를 비교해줘",
            "expected_intent": "compare_two_repos",
        },
    ]
    
    for tc in test_cases:
        print("=" * 70)
        print(f"E2E 테스트: {tc['name']}")
        print("=" * 70)
        print(f"질문: {tc['query']}")
        print("-" * 50)
        
        try:
            result = graph.invoke({
                "user_query": tc["query"],
                "history": [],
            })
            
            detected_intent = result.get("intent", "unknown")
            user_context = result.get("user_context", {})
            detected_level = user_context.get("level", "unknown")
            llm_summary = result.get("llm_summary", "")
            
            print(f"감지된 intent: {detected_intent}")
            print(f"감지된 level: {detected_level}")
            print(f"응답 길이: {len(llm_summary)}자")
            
            # 검증
            intent_ok = detected_intent == tc["expected_intent"]
            level_ok = True
            if "expected_level" in tc:
                level_ok = detected_level == tc["expected_level"]
            
            has_response = len(llm_summary) > 100
            
            passed = intent_ok and level_ok and has_response
            status = "[PASS]" if passed else "[FAIL]"
            print(f"{status} intent_ok={intent_ok}, level_ok={level_ok}, has_response={has_response}")
            
            # Compare 모드 추가 검증
            if tc["expected_intent"] == "compare_two_repos":
                repo = result.get("repo")
                compare_repo = result.get("compare_repo")
                compare_ok = repo is not None and compare_repo is not None
                print(f"     repo={repo.get('name') if repo else None}, compare_repo={compare_repo.get('name') if compare_repo else None}")
                passed = passed and compare_ok
            
            results[tc["name"]] = passed
            
        except Exception as e:
            print(f"[ERROR] {e}")
            results[tc["name"]] = False
        
        print()
    
    return results


# ============================================================================
# 메인 실행
# ============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Supervisor 통합 테스트")
    parser.add_argument("--unit-only", action="store_true", help="유닛 테스트만 실행")
    parser.add_argument("--e2e-only", action="store_true", help="E2E 테스트만 실행")
    args = parser.parse_args()
    
    all_results = {}
    
    # 유닛 테스트
    if not args.e2e_only:
        unit_results = run_unit_tests()
        all_results.update({f"[Unit] {k}": v for k, v in unit_results.items()})
    
    # E2E 테스트
    if not args.unit_only:
        e2e_results = run_e2e_tests()
        all_results.update({f"[E2E] {k}": v for k, v in e2e_results.items()})
    
    # 결과 요약
    print("=" * 70)
    print("테스트 결과 요약")
    print("=" * 70)
    
    all_passed = True
    for name, passed in all_results.items():
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{status} {name}")
        if not passed:
            all_passed = False
    
    print()
    if all_passed:
        print("모든 테스트 통과!")
    else:
        print("일부 테스트 실패. 위 결과를 확인하세요.")
    
    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
