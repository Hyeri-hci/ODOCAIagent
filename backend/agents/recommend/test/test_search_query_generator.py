# test/test_search_query_generator.py

import pytest
from tools.search_query_generator_tool import github_search_query_generator

# =============================================================================
# 1. 키워드 보존 및 따옴표 규칙 (Space Rule) 테스트
# =============================================================================
@pytest.mark.parametrize("user_input, expected_keywords", [
    ("React state management 라이브러리", ['"state management"', "react"]),
    ("Python machine learning tools", ['"machine learning"', "python"]),
    ("dashboard template", ["dashboard", "template"]),
    ("최근 유행하는 typescript boilerplate", ["typescript", "boilerplate"]),
])
def test_keyword_preservation_and_quoting(user_input, expected_keywords):
    """
    일반 검색어가 q 필드에 사라지지 않고 남아있는지,
    특히 공백이 있는 경우 따옴표 처리가 되는지 검증
    """
    print(f"\n[Keyword Test] Input: {user_input}")
    
    result = github_search_query_generator.invoke(user_input)
    print(f"👉 Result: {result}")

    q_lower = result["q"].lower()
    
    for keyword in expected_keywords:
        assert keyword.lower() in q_lower, f"키워드 '{keyword}'가 q 필드에서 소실되었습니다."

# =============================================================================
# 2. 정렬(Sorting) 로직 테스트 (기준 완화)
# =============================================================================
@pytest.mark.parametrize("user_input, requirement_type, expected_key", [
    # (입력, 검증타입, 기대값)
    # 1. Filter로 충분한 경우 (stars:>100 등) -> sort는 None이어도 됨
    ("Python 스타 많은 프로젝트", "filter", "stars:"),
    ("최근 업데이트된(latest) 장고 프로젝트", "filter", "pushed:"),
    
    # 2. Sort가 필수인 경우 (Best, Popular 등)
    ("가장 인기있는(popular) 리액트 라이브러리", "sort", "stars"),
    ("Best Java frameworks", "sort", "stars"),
    
    # 3. 아무것도 필요 없는 경우
    ("Just python libraries", "none", None), 
])
def test_sorting_logic(user_input, requirement_type, expected_key):
    """
    사용자의 의도에 따라 Sort가 설정되거나, 혹은 강력한 Filter가 적용되었는지 검증
    """
    print(f"\n[Sort Test] Input: {user_input}")
    
    result = github_search_query_generator.invoke(user_input)
    print(f"👉 Result: {result}")

    if requirement_type == "sort":
        # 반드시 정렬 파라미터가 있어야 함
        assert result["sort"] == expected_key
        assert result["order"] == "desc"
        
    elif requirement_type == "filter":
        # 정렬이 없더라도 q 안에 필터 조건(stars:, pushed:)이 있으면 합격
        if result["sort"] is None:
            assert expected_key in result["q"], f"정렬이 없다면 q에 '{expected_key}' 조건이라도 있어야 합니다."
        else:
            # 정렬이 있어도 합격
            pass
            
    elif requirement_type == "none":
        assert result["sort"] is None

# =============================================================================
# 3. 'other' 필드 및 복합 로직 테스트 (수정됨)
# =============================================================================
@pytest.mark.parametrize("user_input, expected_tokens", [
    ("이슈가 많은 프로젝트", ["many_issues"]),
    ("버그(이슈)가 적은 프로젝트", ["few_issues"]),
    ("최근 1년 내 커밋이 활발한", ["many_commits_recently_1y"]),
    
    # [수정] '활동이 있는'은 many가 아니라 has로 해석되는 것이 맞음
    ("최근 3개월간 활동(커밋)이 있는", ["has_commits", "3m"]), 
    
    ("PR이 10개 이상인", ["has_prs_10"]),
    ("이슈는 적고 커밋은 많은", ["few_issues", "many_commits"]),
])
def test_other_field_logic(user_input, expected_tokens):
    """
    자연어 조건이 other 필드의 snake_case 토큰으로 잘 변환되는지 검증
    """
    print(f"\n[Other Field Test] Input: {user_input}")
    
    result = github_search_query_generator.invoke(user_input)
    print(f"👉 Result: {result}")

    other_val = result.get("other")
    
    assert other_val is not None, "other 필드가 비어있습니다."
    assert isinstance(other_val, str), "other 필드는 문자열이어야 합니다."
    
    for token in expected_tokens:
        assert token in other_val, f"토큰 '{token}'이 other 필드에 없습니다."

# =============================================================================
# 4. 할루시네이션 및 포맷 방지 테스트 (Safety Check)
# =============================================================================
def test_hallucination_prevention():
    """
    LLM이 없는 문법(issues:, commits:)을 q에 넣거나, 
    빈 topic: 을 남기는지 확인
    """
    user_input = "커밋이 많고 이슈가 적은 타입스크립트 프로젝트"
    print(f"\n[Safety Test] Input: {user_input}")
    
    result = github_search_query_generator.invoke(user_input)
    print(f"👉 Result: {result}")
    
    q_str = result["q"]
    
    # 1. 없는 문법 사용 금지
    forbidden_syntaxes = ["issues:", "commits:", "prs:"]
    for syntax in forbidden_syntaxes:
        assert syntax not in q_str, f"허용되지 않은 문법 '{syntax}'가 q에 포함되었습니다."

    # 2. 빈 필터(Dangling keys) 방지
    # topic: 뒤에 공백이나 다른 필터가 바로 오는지 확인
    # (Parser가 처리해주지만 Generator 단계에서도 안 만드는 게 좋음)
    if "topic:" in q_str:
        import re
        # topic: 뒤에 바로 다른 필터키워드(:가 있는)가 오는 패턴 검사
        assert not re.search(r'topic:\s*(?:\w+:|$)', q_str), "topic: 뒤에 값이 없습니다."

# =============================================================================
# 5. 종합 시나리오 (Integration Scenarios)
# =============================================================================
SCENARIOS = [
    ("React state management", "키워드 보존"),
    ("최근 1개월 내 업데이트된 파이썬 툴", "기간 및 언어"),
    ("스타 1000개 이상인 Go 프로젝트", "명시적 필터"),
    ("PR이 활발한(많은) 장고 프로젝트", "Other 필드 변환"),
    ("그냥 아무거나 추천해줘", "Null Handling"),
]

@pytest.mark.parametrize("user_input, desc", SCENARIOS)
def test_comprehensive_integration(user_input, desc):
    """
    전체적인 흐름을 눈으로 확인하기 위한 통합 테스트
    """
    print(f"\n[Scenario: {desc}] Input: {user_input}")
    try:
        result = github_search_query_generator.invoke(user_input)
        print(f"👉 Generated: {result}")
        
        # 최소한의 구조 검증
        assert isinstance(result, dict)
        assert "q" in result
        
    except Exception as e:
        pytest.fail(f"Tool execution failed: {e}")

if __name__ == "__main__":
    pytest.main(["-s", "test/test_search_query_generator.py"])