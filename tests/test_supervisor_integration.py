"""
Supervisor 통합 테스트

모든 Intent에 대한 통합 테스트를 수행합니다.
- 라우팅 테스트 (mock 없이 빠르게)
- 프롬프트 매핑 테스트
- 미지원 Intent 가드 테스트
- user_level 유효성 테스트
"""

import sys
import os
from pathlib import Path

# 프로젝트 루트 경로 추가
sys.path.insert(0, str(Path(__file__).parent.parent.absolute()))

# Windows 콘솔 인코딩 설정
if sys.platform == "win32":
    os.system("chcp 65001 > nul 2>&1")


def test_routing():
    """라우팅 테스트 - INTENT_CONFIG 기반"""
    from backend.agents.supervisor.graph import route_after_mapping
    from backend.agents.supervisor.intent_config import INTENT_CONFIG, needs_diagnosis, is_intent_ready
    
    print("=" * 70)
    print("1. 라우팅 테스트")
    print("=" * 70)
    
    all_passed = True
    for intent, config in INTENT_CONFIG.items():
        state = {"task_type": intent}
        route = route_after_mapping(state)
        
        # 미지원 Intent는 summarize로 라우팅
        if not is_intent_ready(intent):
            expected = "summarize"
        elif config["needs_diagnosis"]:
            expected = "run_diagnosis"
        else:
            expected = "summarize"
        
        passed = route == expected
        
        ready_note = "" if is_intent_ready(intent) else " (not ready)"
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{status} {intent:30} -> {route} (expected: {expected}){ready_note}")
        
        if not passed:
            all_passed = False
    
    print()
    return all_passed


def test_prompt_mapping():
    """프롬프트 매핑 테스트 - INTENT_CONFIG 기반"""
    from backend.agents.supervisor.nodes.summarize_node import _get_prompt_for_intent
    from backend.agents.supervisor.intent_config import INTENT_CONFIG
    
    print("=" * 70)
    print("2. 프롬프트 매핑 테스트")
    print("=" * 70)
    
    all_passed = True
    for intent, config in INTENT_CONFIG.items():
        prompt = _get_prompt_for_intent(intent, "beginner")
        prompt_kind = config["prompt_kind"]
        
        # 프롬프트가 None이 아니고 적절한 길이인지 확인
        has_prompt = prompt is not None and len(prompt) > 100
        
        status = "[PASS]" if has_prompt else "[FAIL]"
        print(f"{status} {intent:30} -> prompt_kind={prompt_kind}, len={len(prompt) if prompt else 0}")
        
        if not has_prompt:
            all_passed = False
    
    print()
    return all_passed


def test_not_ready_guard():
    """미지원 Intent 가드 테스트"""
    from backend.agents.supervisor.nodes.summarize_node import _get_not_ready_message
    from backend.agents.supervisor.intent_config import INTENT_CONFIG, is_intent_ready
    
    print("=" * 70)
    print("3. 미지원 Intent 가드 테스트")
    print("=" * 70)
    
    all_passed = True
    for intent, config in INTENT_CONFIG.items():
        ready = is_intent_ready(intent)
        
        if not ready:
            message = _get_not_ready_message(intent)
            has_message = "준비 중" in message or "개발 중" in message
            status = "[PASS]" if has_message else "[FAIL]"
            print(f"{status} {intent:30} -> is_ready=False, message_ok={has_message}")
            if not has_message:
                all_passed = False
        else:
            print(f"[SKIP] {intent:30} -> is_ready=True (가드 불필요)")
    
    print()
    return all_passed


def test_user_level_validation():
    """user_level 유효성 테스트"""
    from backend.agents.supervisor.intent_config import validate_user_level, VALID_USER_LEVELS
    
    print("=" * 70)
    print("4. user_level 유효성 테스트")
    print("=" * 70)
    
    test_cases = [
        ("beginner", "beginner"),
        ("intermediate", "intermediate"),
        ("advanced", "advanced"),
        ("expert", "beginner"),      # 잘못된 값 -> beginner
        ("", "beginner"),            # 빈 문자열 -> beginner
        (None, "beginner"),          # None -> beginner
        ("BEGINNER", "beginner"),    # 대문자 -> beginner (대소문자 구분)
    ]
    
    all_passed = True
    for input_val, expected in test_cases:
        result = validate_user_level(input_val)
        passed = result == expected
        
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{status} validate_user_level({repr(input_val):15}) -> {result} (expected: {expected})")
        
        if not passed:
            all_passed = False
    
    print()
    return all_passed


def test_intent_validation():
    """intent 유효성 테스트"""
    from backend.agents.supervisor.intent_config import validate_intent, VALID_INTENTS
    
    print("=" * 70)
    print("5. Intent 유효성 테스트")
    print("=" * 70)
    
    test_cases = [
        ("diagnose_repo_health", "diagnose_repo_health"),
        ("diagnose_repo_onboarding", "diagnose_repo_onboarding"),
        ("explain_scores", "explain_scores"),
        ("invalid_intent", "diagnose_repo_health"),  # 잘못된 값 -> 기본값
        ("", "diagnose_repo_health"),                 # 빈 문자열 -> 기본값
        (None, "diagnose_repo_health"),               # None -> 기본값
    ]
    
    all_passed = True
    for input_val, expected in test_cases:
        result = validate_intent(input_val)
        passed = result == expected
        
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{status} validate_intent({repr(input_val):30}) -> {result}")
        
        if not passed:
            all_passed = False
    
    print()
    return all_passed


def test_diagnosis_task_type_mapping():
    """Diagnosis task_type 매핑 테스트"""
    from backend.agents.supervisor.nodes.task_mapping import map_to_diagnosis_task_type
    from backend.agents.supervisor.intent_config import INTENT_CONFIG
    
    print("=" * 70)
    print("6. Diagnosis task_type 매핑 테스트")
    print("=" * 70)
    
    all_passed = True
    for intent, config in INTENT_CONFIG.items():
        result = map_to_diagnosis_task_type(intent)
        expected = config["diagnosis_task_type"]
        passed = result == expected
        
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{status} {intent:30} -> {result}")
        
        if not passed:
            all_passed = False
    
    print()
    return all_passed


def run_all_tests():
    """모든 테스트 실행"""
    print("\n" + "=" * 70)
    print("Supervisor 통합 테스트 시작")
    print("=" * 70 + "\n")
    
    results = {
        "라우팅": test_routing(),
        "프롬프트 매핑": test_prompt_mapping(),
        "미지원 Intent 가드": test_not_ready_guard(),
        "user_level 유효성": test_user_level_validation(),
        "Intent 유효성": test_intent_validation(),
        "Diagnosis task_type 매핑": test_diagnosis_task_type_mapping(),
    }
    
    print("=" * 70)
    print("테스트 결과 요약")
    print("=" * 70)
    
    all_passed = True
    for name, passed in results.items():
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
    success = run_all_tests()
    sys.exit(0 if success else 1)
