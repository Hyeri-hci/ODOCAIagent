"""
Supervisor 통합 테스트

새로운 3 Intent + SubIntent 구조에 대한 유닛 테스트 + E2E 테스트를 수행합니다.

구조:
- intent: analyze | followup | general_qa
- sub_intent: health | onboarding | compare | explain | refine | concept | chat

테스트 항목:
1. 유닛 테스트 (Mock 사용, 빠름)
   - 라우팅 테스트 (INTENT_META 기반)
   - 프롬프트 매핑 테스트 (sub_intent 기반)
   - error_message 패턴 테스트
   - Intent/SubIntent 유효성 테스트
   - 비교 모드 정규식 테스트
   - 멀티턴 라우팅 테스트

2. E2E 테스트 (실제 LLM 호출, 느림)
   - Health 모드 (analyze + health)
   - Onboarding 모드 (analyze + onboarding)
   - Compare 모드 (analyze + compare)
   - Concept QA 모드 (general_qa + concept)
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
    """라우팅 테스트 - INTENT_META 기반 (새 구조: followup도 run_diagnosis)"""
    from backend.agents.supervisor.graph import route_after_mapping
    from backend.agents.supervisor.intent_config import INTENT_META, get_intent_meta
    from backend.agents.supervisor.models import DEFAULT_INTENT, DEFAULT_SUB_INTENT
    
    print("=" * 70)
    print("1. 라우팅 테스트 (intent, sub_intent)")
    print("=" * 70)
    
    for (intent, sub_intent), meta in INTENT_META.items():
        # 기본 상태 구성
        state = {
            "intent": intent,
            "sub_intent": sub_intent,
        }
        
        # repo 필수인 경우 repo 추가
        if meta["requires_repo"]:
            state["repo"] = {"owner": "test", "name": "repo"}
        
        route = route_after_mapping(state)
        
        # 기대 결과: runs_diagnosis=True면 run_diagnosis, 아니면 summarize
        if meta["runs_diagnosis"]:
            expected = "run_diagnosis"
        else:
            expected = "summarize"
        
        assert route == expected, f"({intent}, {sub_intent}): {route} != {expected}"
        print(f"[PASS] ({intent:12}, {sub_intent:10}) -> {route}")
    
    print()
    return True


def test_routing_error_message():
    """error_message 패턴 라우팅 테스트"""
    from backend.agents.supervisor.graph import route_after_mapping
    
    print("=" * 70)
    print("2. error_message 패턴 테스트")
    print("=" * 70)
    
    # error_message가 있으면 바로 summarize로
    state_with_error = {
        "intent": "analyze",
        "sub_intent": "health",
        "error_message": "어떤 저장소를 분석할까요?",
    }
    route = route_after_mapping(state_with_error)
    assert route == "summarize", f"With error_message: {route} != summarize"
    print(f"[PASS] error_message 있음 -> {route}")
    
    # requires_repo인데 repo 없으면 error_message 설정 후 summarize
    state_no_repo = {
        "intent": "analyze",
        "sub_intent": "health",
    }
    route = route_after_mapping(state_no_repo)
    assert route == "summarize", f"No repo: {route} != summarize"
    assert state_no_repo.get("error_message"), "error_message should be set"
    print(f"[PASS] (analyze, health) repo 없음 -> {route}, error_message 설정됨")
    
    # followup인데 repo 없으면 error_message 설정 후 summarize
    state_followup_no_repo = {
        "intent": "followup",
        "sub_intent": "explain",
    }
    route = route_after_mapping(state_followup_no_repo)
    assert route == "summarize", f"Followup no repo: {route} != summarize"
    assert state_followup_no_repo.get("error_message"), "error_message should be set for followup without repo"
    print(f"[PASS] (followup, explain) repo 없음 -> {route}, error_message 설정됨")
    
    print()
    return True


def test_prompt_mapping():
    """프롬프트 매핑 테스트 - sub_intent 기반"""
    from backend.agents.supervisor.nodes.summarize_node import _get_prompt_for_sub_intent
    from backend.agents.supervisor.intent_config import INTENT_META
    
    print("=" * 70)
    print("3. 프롬프트 매핑 테스트 (sub_intent)")
    print("=" * 70)
    
    sub_intents = ["health", "onboarding", "compare", "explain", "refine", "concept", "chat"]
    
    for sub_intent in sub_intents:
        prompt = _get_prompt_for_sub_intent(sub_intent, "beginner")
        has_prompt = prompt is not None and len(prompt) > 100
        assert has_prompt, f"sub_intent={sub_intent}: len={len(prompt) if prompt else 0}"
        print(f"[PASS] sub_intent={sub_intent:12} -> len={len(prompt)}")
    
    print()
    return True


def test_intent_validation():
    """intent/sub_intent 유효성 테스트"""
    from backend.agents.supervisor.intent_config import validate_intent, validate_sub_intent
    from backend.agents.supervisor.models import VALID_INTENTS, VALID_SUB_INTENTS, DEFAULT_INTENT, DEFAULT_SUB_INTENT
    
    print("=" * 70)
    print("4. Intent/SubIntent 유효성 테스트")
    print("=" * 70)
    
    # 유효한 intent
    for intent in VALID_INTENTS:
        result = validate_intent(intent)
        assert result == intent, f"validate_intent({intent}): {result} != {intent}"
        print(f"[PASS] validate_intent({intent:15}) -> {result}")
    
    # 유효하지 않은 intent → DEFAULT_INTENT
    invalid_intents = ["invalid", "", None, "analyze_repo"]
    for inv in invalid_intents:
        result = validate_intent(inv)
        assert result == DEFAULT_INTENT, f"validate_intent({repr(inv)}): {result} != {DEFAULT_INTENT}"
        print(f"[PASS] validate_intent({repr(inv):15}) -> {result} (default)")
    
    print()
    
    # 유효한 sub_intent
    for sub in VALID_SUB_INTENTS:
        result = validate_sub_intent(sub)
        assert result == sub, f"validate_sub_intent({sub}): {result} != {sub}"
        print(f"[PASS] validate_sub_intent({sub:12}) -> {result}")
    
    # 유효하지 않은 sub_intent → DEFAULT_SUB_INTENT
    invalid_subs = ["invalid", "", None, "detailed"]
    for inv in invalid_subs:
        result = validate_sub_intent(inv)
        assert result == DEFAULT_SUB_INTENT, f"validate_sub_intent({repr(inv)}): {result} != {DEFAULT_SUB_INTENT}"
        print(f"[PASS] validate_sub_intent({repr(inv):12}) -> {result} (default)")
    
    print()
    return True


def test_user_level_validation():
    """user_level 유효성 테스트"""
    from backend.agents.supervisor.nodes.summarize_node import _validate_user_level
    
    print("=" * 70)
    print("5. user_level 유효성 테스트")
    print("=" * 70)
    
    test_cases = [
        ("beginner", "beginner"),
        ("intermediate", "intermediate"),
        ("advanced", "advanced"),
        ("expert", "beginner"),
        ("", "beginner"),
        (None, "beginner"),
    ]
    
    for input_val, expected in test_cases:
        result = _validate_user_level(input_val)
        assert result == expected, f"_validate_user_level({repr(input_val)}): {result} != {expected}"
        print(f"[PASS] _validate_user_level({repr(input_val):15}) -> {result}")
    
    print()
    return True


def test_compare_regex():
    """비교 모드 정규식 테스트"""
    from backend.agents.supervisor.nodes.intent_classifier import _extract_all_repos_from_query
    
    print("=" * 70)
    print("6. 비교 모드 정규식 테스트")
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
    return True


def test_compare_fallback():
    """비교 모드 fallback 테스트 (LLM mock)"""
    from backend.agents.supervisor.nodes.intent_classifier import classify_intent_node
    
    print("=" * 70)
    print("7. 비교 모드 fallback 테스트")
    print("=" * 70)
    
    # 새로운 3 Intent + SubIntent 구조
    mock_response = """{
      "intent": "analyze",
      "sub_intent": "compare",
      "repo_url": null,
      "compare_repo_url": null,
      "is_followup": false,
      "user_context": {}
    }"""
    
    test_cases = [
        ("facebook/react와 vuejs/vue를 비교해줘", "react", "vue"),
        ("angular/angular과 sveltejs/svelte를 비교해줘", "angular", "svelte"),
    ]
    
    for query, expected_repo, expected_compare in test_cases:
        initial_state = {
            "user_query": query,
            "intent": "",
            "sub_intent": "",
            "history": [],
        }
        
        with patch(
            "backend.agents.supervisor.nodes.intent_classifier._call_intent_llm_with_context",
            return_value=mock_response
        ):
            result = classify_intent_node(initial_state)
        
        repo = result.get("repo")
        compare_repo = result.get("compare_repo")
        
        repo_name = repo["name"] if repo else None
        compare_name = compare_repo["name"] if compare_repo else None
        
        # 새 구조 검증
        assert result.get("intent") == "analyze", f"intent: {result.get('intent')} != analyze"
        assert result.get("sub_intent") == "compare", f"sub_intent: {result.get('sub_intent')} != compare"
        assert repo is not None and repo["name"] == expected_repo, f"repo: {repo_name} != {expected_repo}"
        assert compare_repo is not None and compare_repo["name"] == expected_compare, f"compare: {compare_name} != {expected_compare}"
        print(f"[PASS] '{query[:40]}...' -> (analyze, compare), repo={repo_name}, compare={compare_name}")
    
    print()
    return True


def test_multiturn_routing():
    """멀티턴 라우팅 테스트 - followup도 run_diagnosis로 라우팅 (새 구조)"""
    from backend.agents.supervisor.graph import route_after_mapping
    
    print("=" * 70)
    print("8. 멀티턴 라우팅 테스트 (새 구조: followup -> run_diagnosis)")
    print("=" * 70)
    
    # 케이스 1: followup + refine, repo 없음 → error_message 설정 후 summarize
    state_no_repo = {
        "intent": "followup",
        "sub_intent": "refine",
    }
    route = route_after_mapping(state_no_repo)
    assert route == "summarize", f"No repo: {route} != summarize"
    assert state_no_repo.get("error_message"), "error_message should be set"
    print(f"[PASS] (followup, refine) + no repo -> {route}, error_message 설정됨")
    
    # 케이스 2: followup + refine, repo 있음 → run_diagnosis (새 구조)
    state_with_repo = {
        "intent": "followup",
        "sub_intent": "refine",
        "repo": {"owner": "test", "name": "repo"},
    }
    route = route_after_mapping(state_with_repo)
    assert route == "run_diagnosis", f"With repo: {route} != run_diagnosis"
    print(f"[PASS] (followup, refine) + repo -> {route}")
    
    # 케이스 3: followup + explain, repo 있음 → run_diagnosis (새 구조)
    state_explain = {
        "intent": "followup",
        "sub_intent": "explain",
        "repo": {"owner": "test", "name": "repo"},
    }
    route = route_after_mapping(state_explain)
    assert route == "run_diagnosis", f"Explain with repo: {route} != run_diagnosis"
    print(f"[PASS] (followup, explain) + repo -> {route}")
    
    # 케이스 4: analyze + health, repo 있음 → run_diagnosis
    state_analyze = {
        "intent": "analyze",
        "sub_intent": "health",
        "repo": {"owner": "test", "name": "repo"},
    }
    route = route_after_mapping(state_analyze)
    assert route == "run_diagnosis", f"Analyze health: {route} != run_diagnosis"
    print(f"[PASS] (analyze, health) + repo -> {route}")
    
    # 케이스 5: general_qa + concept → summarize (Diagnosis 없이)
    state_concept = {
        "intent": "general_qa",
        "sub_intent": "concept",
    }
    route = route_after_mapping(state_concept)
    assert route == "summarize", f"Concept QA: {route} != summarize"
    print(f"[PASS] (general_qa, concept) -> {route}")
    
    print()
    return True


def run_unit_tests():
    """모든 유닛 테스트 실행"""
    print("\n" + "=" * 70)
    print("유닛 테스트 시작 (Mock 사용) - 새 구조: 3 Intent + SubIntent")
    print("=" * 70 + "\n")
    
    results = {}
    results["routing"] = test_routing()
    results["routing_error_message"] = test_routing_error_message()
    results["prompt_mapping"] = test_prompt_mapping()
    results["intent_validation"] = test_intent_validation()
    results["user_level_validation"] = test_user_level_validation()
    results["compare_regex"] = test_compare_regex()
    results["compare_fallback"] = test_compare_fallback()
    results["multiturn_routing"] = test_multiturn_routing()
    results["concept_qa_routing"] = test_concept_qa_routing()
    results["history_normalization"] = test_history_normalization()
    
    print("모든 유닛 테스트 통과!")
    return results


def test_concept_qa_routing():
    """Concept QA 라우팅 테스트 - Diagnosis 없이 바로 summarize"""
    from backend.agents.supervisor.graph import route_after_mapping
    from backend.agents.supervisor.intent_config import is_concept_qa, is_chat
    
    print("=" * 70)
    print("9. Concept QA / Chat 라우팅 테스트")
    print("=" * 70)
    
    # general_qa + concept → summarize (Diagnosis 없이)
    state_concept = {"intent": "general_qa", "sub_intent": "concept"}
    route = route_after_mapping(state_concept)
    assert route == "summarize", f"(general_qa, concept): {route} != summarize"
    assert is_concept_qa("general_qa", "concept"), "is_concept_qa should return True"
    print(f"[PASS] (general_qa, concept) -> {route}")
    
    # general_qa + chat → summarize (Diagnosis 없이)
    state_chat = {"intent": "general_qa", "sub_intent": "chat"}
    route = route_after_mapping(state_chat)
    assert route == "summarize", f"(general_qa, chat): {route} != summarize"
    assert is_chat("general_qa", "chat"), "is_chat should return True"
    print(f"[PASS] (general_qa, chat) -> {route}")
    
    # 일반 분석은 concept_qa가 아님
    assert not is_concept_qa("analyze", "health"), "is_concept_qa should return False for analyze"
    print(f"[PASS] (analyze, health) -> is_concept_qa=False")
    
    print()
    return True


def test_history_normalization():
    """history 정규화 테스트 - 비정상 입력 처리"""
    from backend.agents.supervisor.nodes.intent_classifier import _normalize_history
    
    print("=" * 70)
    print("10. history 정규화 테스트")
    print("=" * 70)
    
    test_cases = [
        # (입력, 예상 출력 길이)
        (None, 0),
        ([], 0),
        ("문자열", 0),  # 잘못된 타입
        (123, 0),  # 잘못된 타입
        ([{"role": "user", "content": "hi"}], 1),  # 정상
        (
            [
                {"role": "user", "content": "hi"},
                {"role": "assistant", "content": "hello"},
            ],
            2,
        ),
        (
            [
                {"role": "user", "content": "hi"},
                "invalid item",  # 잘못된 항목
                {"role": "assistant", "content": "hello"},
            ],
            2,  # 유효한 항목만 반환
        ),
        (
            [{"invalid": "dict"}],  # role/content 없음
            0,
        ),
    ]
    
    for input_val, expected_len in test_cases:
        result = _normalize_history(input_val)
        assert len(result) == expected_len, f"_normalize_history({repr(input_val)[:30]}...): len={len(result)} != {expected_len}"
        print(f"[PASS] _normalize_history({repr(input_val)[:30]:30}...) -> len={len(result)}")
    
    print()
    return True


# ============================================================================
# 2. E2E 테스트 (실제 LLM 호출)
# ============================================================================

def run_e2e_tests():
    """E2E 테스트 실행 (실제 LLM 호출) - 새 구조"""
    from backend.agents.supervisor.graph import build_supervisor_graph
    
    print("\n" + "=" * 70)
    print("E2E 테스트 시작 (실제 LLM 호출) - 새 구조: 3 Intent + SubIntent")
    print("=" * 70 + "\n")
    
    graph = build_supervisor_graph()
    results = {}
    
    # 테스트 케이스 정의 - 새 구조
    test_cases = [
        {
            "name": "Health 모드 (analyze + health)",
            "query": "facebook/react 건강 상태 분석해줘",
            "expected_intent": "analyze",
            "expected_sub_intent": "health",
        },
        {
            "name": "Onboarding 모드 (analyze + onboarding)",
            "query": "초보자인데 facebook/react에 기여하고 싶어요",
            "expected_intent": "analyze",
            "expected_sub_intent": "onboarding",
            "expected_level": "beginner",
        },
        {
            "name": "Compare 모드 (analyze + compare)",
            "query": "facebook/react와 vuejs/vue를 비교해줘",
            "expected_intent": "analyze",
            "expected_sub_intent": "compare",
        },
        {
            "name": "Concept QA 모드 (general_qa + concept)",
            "query": "온보딩 용이성이 뭐야?",
            "expected_intent": "general_qa",
            "expected_sub_intent": "concept",
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
            detected_sub_intent = result.get("sub_intent", "unknown")
            user_context = result.get("user_context", {})
            detected_level = user_context.get("level", "unknown")
            llm_summary = result.get("llm_summary", "")
            
            print(f"감지된 intent: {detected_intent}")
            print(f"감지된 sub_intent: {detected_sub_intent}")
            print(f"감지된 level: {detected_level}")
            print(f"응답 길이: {len(llm_summary)}자")
            
            # 검증
            intent_ok = detected_intent == tc["expected_intent"]
            sub_intent_ok = detected_sub_intent == tc["expected_sub_intent"]
            level_ok = True
            if "expected_level" in tc:
                level_ok = detected_level == tc["expected_level"]
            
            has_response = len(llm_summary) > 50
            
            passed = intent_ok and sub_intent_ok and level_ok and has_response
            status = "[PASS]" if passed else "[FAIL]"
            print(f"{status} intent_ok={intent_ok}, sub_intent_ok={sub_intent_ok}, level_ok={level_ok}, has_response={has_response}")
            
            # Compare 모드 추가 검증
            if tc["expected_sub_intent"] == "compare":
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


# ============================================================================
# v4.1 infer_explain_target 라우팅 테스트
# ============================================================================

def test_infer_explain_target_metric_keyword():
    """시나리오 1: Report 후 'health_score 설명해줘' → metric"""
    from backend.agents.supervisor.nodes.summarize_node import infer_explain_target
    
    state = {
        "user_query": "health_score 설명해줘",
        "last_answer_kind": "report",
        "last_explain_target": None,
        "explain_metrics": [],
    }
    result = infer_explain_target(state)
    assert result == "metric", f"Expected 'metric', got '{result}'"
    assert "health_score" in state["explain_metrics"]


def test_infer_explain_target_followup():
    """시나리오 2: metric explain 후 '그게 무슨 말이야?' → metric (재질문)"""
    from backend.agents.supervisor.nodes.summarize_node import infer_explain_target
    
    state = {
        "user_query": "그게 무슨 말이야?",
        "last_answer_kind": "explain",
        "last_explain_target": "metric",
        "explain_metrics": ["health_score"],
    }
    result = infer_explain_target(state)
    assert result == "metric", f"Expected 'metric', got '{result}'"


def test_infer_explain_target_multi_metric():
    """시나리오 3: Report 후 멀티메트릭 explain"""
    from backend.agents.supervisor.nodes.summarize_node import infer_explain_target
    
    state = {
        "user_query": "health_score랑 documentation_quality 둘 다 설명해줘",
        "last_answer_kind": "report",
        "last_explain_target": None,
        "explain_metrics": [],
    }
    result = infer_explain_target(state)
    assert result == "metric", f"Expected 'metric', got '{result}'"
    assert "health_score" in state["explain_metrics"]
    assert "documentation_quality" in state["explain_metrics"]


def test_infer_explain_target_task_recommendation():
    """시나리오 4: task 추천 후 '어떤 근거로 추천한 건데?' → task_recommendation"""
    from backend.agents.supervisor.nodes.summarize_node import infer_explain_target
    
    state = {
        "user_query": "어떤 근거로 추천한 건데?",
        "last_answer_kind": "explain",
        "last_explain_target": "task_recommendation",
        "explain_metrics": [],
    }
    result = infer_explain_target(state)
    assert result == "task_recommendation", f"Expected 'task_recommendation', got '{result}'"


def test_infer_explain_target_no_context():
    """시나리오 5: 맥락 없는 '설명해줘' → general"""
    from backend.agents.supervisor.nodes.summarize_node import infer_explain_target
    
    state = {
        "user_query": "설명해줘",
        "last_answer_kind": None,
        "last_explain_target": None,
        "explain_metrics": [],
    }
    result = infer_explain_target(state)
    assert result == "general", f"Expected 'general', got '{result}'"


def test_infer_explain_target_new_diagnosis_reset():
    """시나리오 6: Vue 분석 후 '왜 점수가 낮지?' → metric (리포트 직후)"""
    from backend.agents.supervisor.nodes.summarize_node import infer_explain_target
    
    # 새 Diagnosis 후 last_explain_target은 None으로 초기화됨
    state = {
        "user_query": "왜 점수가 낮지?",
        "last_answer_kind": "report",
        "last_explain_target": None,  # 새 Diagnosis로 초기화됨
        "explain_metrics": [],
    }
    result = infer_explain_target(state)
    assert result == "metric", f"Expected 'metric', got '{result}'"


# ============================================================================
# LLM 통제 v3.0 테스트
# ============================================================================

def test_metric_definitions_alias_lookup():
    """지표 정의 지식베이스: alias로 지표 조회"""
    from backend.agents.diagnosis.tools.scoring.metric_definitions import (
        get_metric_by_alias,
        METRIC_DEFINITIONS,
    )
    
    # 한글 alias
    m1 = get_metric_by_alias("온보딩 용이성")
    assert m1 is not None
    assert m1.key == "onboarding_score"
    
    # 영문 alias
    m2 = get_metric_by_alias("health")
    assert m2 is not None
    assert m2.key == "health_score"
    
    # 다른 표현
    m3 = get_metric_by_alias("진입장벽")
    assert m3 is not None
    assert m3.key == "onboarding_score"
    
    # 없는 지표
    m4 = get_metric_by_alias("없는지표")
    assert m4 is None


def test_onboarding_task_formatting():
    """Onboarding Task 포맷팅: Python에서 완전한 문자열 생성"""
    from backend.agents.supervisor.nodes.summarize_node import _format_onboarding_tasks
    from backend.agents.diagnosis.tools.onboarding.onboarding_tasks import TaskSuggestion
    
    tasks = [
        TaskSuggestion(
            kind="issue",
            difficulty="beginner",
            level=1,
            id="issue#123",
            title="Fix typo in README",
            url="https://github.com/test/repo/issues/123",
            reason_tags=["docs_issue", "small_change"],
        ),
        TaskSuggestion(
            kind="issue",
            difficulty="intermediate",
            level=3,
            id="issue#456",
            title="Add unit tests",
            url="https://github.com/test/repo/issues/456",
            reason_tags=["test_issue"],
        ),
    ]
    
    result, has_mismatch = _format_onboarding_tasks(tasks, user_level="beginner")
    
    # 포맷 확인
    assert "Fix typo in README" in result
    assert "Add unit tests" in result
    assert "⚠️" in result  # 두 번째 Task는 intermediate → 경고 표시
    assert has_mismatch is True


def test_compare_winner_computation():
    """Compare 모드: Python에서 승자 판정"""
    from backend.agents.supervisor.nodes.summarize_node import _compute_comparison_winners
    
    scores_a = {
        "health_score": 85,
        "documentation_quality": 90,
        "activity_maintainability": 80,
        "onboarding_score": 88,
    }
    scores_b = {
        "health_score": 75,
        "documentation_quality": 70,
        "activity_maintainability": 82,
        "onboarding_score": 72,
    }
    
    result = _compute_comparison_winners(scores_a, scores_b, "React", "Vue")
    
    # React가 여러 지표에서 우세
    assert result["overall_winner"] == "React"
    assert "React" in result["table_md"]
    assert "Vue" in result["table_md"]
    
    # 비슷한 경우 테스트
    scores_c = {"health_score": 80, "documentation_quality": 80, "activity_maintainability": 80, "onboarding_score": 80}
    scores_d = {"health_score": 82, "documentation_quality": 78, "activity_maintainability": 81, "onboarding_score": 79}
    
    result2 = _compute_comparison_winners(scores_c, scores_d, "A", "B")
    assert result2["overall_winner"] == "무승부"  # 모든 차이가 5점 미만





