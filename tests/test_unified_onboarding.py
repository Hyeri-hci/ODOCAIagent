"""
통합 온보딩 에이전트 테스트 (Tool A + Tool B)

테스트 대상:
- Tool A: generate_contributor_guide (기여 가이드)
- Tool B: generate_onboarding_curriculum (커리큘럼)
- 통합: context_builder + routing

테스트 저장소:
- facebook/react (npm 기반)
- pallets/flask (pip 기반)
"""

import asyncio
import os
import sys
import json
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()


async def test_context_builder():
    """Context Builder 테스트"""
    print("\n" + "="*60)
    print("TEST: Context Builder")
    print("="*60)
    
    from backend.agents.onboarding.context_builder import build_onboarding_context
    
    for repo_id in ["facebook/react", "pallets/flask"]:
        owner, repo = repo_id.split("/")
        print(f"\n[{repo_id}] Building context...")
        
        try:
            ctx = await build_onboarding_context(owner, repo, "main")
            
            print(f"  - Language: {ctx['code_map']['language']}")
            print(f"  - Package Manager: {ctx['code_map']['package_manager']}")
            print(f"  - Main Dirs: {ctx['code_map']['main_directories'][:3]}")
            print(f"  - Contributing: {'FOUND' if ctx['docs_index']['contributing'] else 'NOT FOUND'}")
            print(f"  - CI Present: {'YES' if ctx['workflow_hints']['ci_present'] else 'NO'}")
            print(f"  ✅ Context built successfully")
        except Exception as e:
            print(f"  ❌ Failed: {e}")


async def test_tool_a():
    """Tool A: Contributor Guide 테스트"""
    print("\n" + "="*60)
    print("TEST: Tool A (Contributor Guide)")
    print("="*60)
    
    from backend.agents.onboarding.context_builder import build_onboarding_context
    from backend.agents.onboarding.tools.contributor_guide_tool import generate_contributor_guide
    
    for repo_id in ["facebook/react", "pallets/flask"]:
        owner, repo = repo_id.split("/")
        print(f"\n[{repo_id}] Generating contributor guide...")
        
        try:
            ctx = await build_onboarding_context(owner, repo, "main")
            result = generate_contributor_guide(ctx, user_goal="first_pr")
            
            markdown = result["markdown"]
            metadata = result["metadata"]
            
            # 필수 섹션 검증
            required_sections = [
                "## 1. 사전 준비",
                "## 2. Fork & Clone",
                "## 3. Branch",
                "## 4. 코드 수정",
                "## 5. 테스트",
                "## 6. Pull Request",
                "## 7. 프로젝트 규칙",
                "## 8. 초보자"
            ]
            
            missing = [s for s in required_sections if s not in markdown]
            
            print(f"  - Sections: {metadata['sections']}")
            print(f"  - Steps: {metadata['steps']}")
            print(f"  - Source files: {len(result['source_files'])}")
            print(f"  - Markdown length: {len(markdown)} chars")
            
            if missing:
                print(f"  ⚠️ Missing sections: {missing}")
            else:
                print(f"  ✅ All required sections present")
                
        except Exception as e:
            print(f"  ❌ Failed: {e}")


async def test_tool_b():
    """Tool B: Curriculum 테스트"""
    print("\n" + "="*60)
    print("TEST: Tool B (Curriculum)")
    print("="*60)
    
    from backend.agents.onboarding.context_builder import build_onboarding_context
    from backend.agents.onboarding.tools.curriculum_tool import generate_onboarding_curriculum
    
    for repo_id in ["facebook/react", "pallets/flask"]:
        owner, repo = repo_id.split("/")
        print(f"\n[{repo_id}] Generating 4-week curriculum (beginner)...")
        
        try:
            ctx = await build_onboarding_context(owner, repo, "main")
            result = generate_onboarding_curriculum(
                ctx, 
                user_level="beginner", 
                weeks=4
            )
            
            markdown = result["markdown"]
            metadata = result["metadata"]
            
            # 주차별 섹션 검증
            required_weeks = ["1주차", "2주차", "3주차", "4주차"]
            missing = [w for w in required_weeks if w not in markdown]
            
            # 필수 하위 섹션 검증
            required_subsections = ["### 목표", "### 학습 내용", "### 실습 과제", "### 검증 체크리스트"]
            missing_sub = [s for s in required_subsections if s not in markdown]
            
            print(f"  - Weeks: {metadata['weeks']}")
            print(f"  - Level: {metadata['level']}")
            print(f"  - Markdown length: {len(markdown)} chars")
            
            if missing:
                print(f"  ⚠️ Missing weeks: {missing}")
            else:
                print(f"  ✅ All {metadata['weeks']} weeks present")
                
            if missing_sub:
                print(f"  ⚠️ Missing subsections: {missing_sub}")
            else:
                print(f"  ✅ All required subsections present")
                
        except Exception as e:
            print(f"  ❌ Failed: {e}")


async def test_routing():
    """Intent Routing 테스트"""
    print("\n" + "="*60)
    print("TEST: Intent Routing")
    print("="*60)
    
    from backend.agents.supervisor.nodes.onboarding_handler_node import _route_by_intent, _extract_weeks
    
    test_cases = [
        ("react 기여 가이드 알려줘", "guide", None),
        ("flask 4주 온보딩 플랜 만들어줘", "curriculum", 4),
        ("langchain 커리큘럼이랑 PR 방법도 같이", "both", None),
        ("react 프로젝트 분석해줘", "curriculum", None),  # 기본값
        ("8주 학습 로드맵", "curriculum", 8),
        ("fork하고 clone하는 법", "guide", None),
    ]
    
    for msg, expected_mode, expected_weeks in test_cases:
        mode = _route_by_intent(msg)
        weeks = _extract_weeks(msg) if expected_weeks else None
        
        mode_ok = "✅" if mode == expected_mode else "❌"
        weeks_ok = "✅" if weeks == expected_weeks or expected_weeks is None else "❌"
        
        print(f"  {mode_ok} \"{msg[:40]}...\" → mode={mode} (expected={expected_mode})")
        if expected_weeks:
            print(f"     {weeks_ok} weeks={weeks} (expected={expected_weeks})")


async def test_integration():
    """통합 테스트 (Supervisor → Onboarding Handler)"""
    print("\n" + "="*60)
    print("TEST: Integration (Supervisor → Onboarding)")
    print("="*60)
    
    from backend.agents.supervisor.nodes.onboarding_handler_node import run_onboarding_agent_node
    
    # Mock state
    state = {
        "owner": "facebook",
        "repo": "react",
        "ref": "main",
        "user_message": "react 4주 온보딩 플랜 만들어줘",
        "accumulated_context": {}
    }
    
    print(f"\n[Test] Running unified onboarding handler...")
    print(f"  Message: \"{state['user_message']}\"")
    
    try:
        result = await run_onboarding_agent_node(state)
        
        agent_result = result.get("agent_result", {})
        result_type = agent_result.get("type")
        summary = agent_result.get("summary", "")
        has_markdown = bool(agent_result.get("markdown"))
        
        print(f"  - Result type: {result_type}")
        print(f"  - Summary: {summary}")
        print(f"  - Has markdown: {has_markdown}")
        
        if has_markdown and result_type == "onboarding_plan":
            print(f"  ✅ Integration test PASSED")
        else:
            print(f"  ⚠️ Unexpected result")
            
    except Exception as e:
        print(f"  ❌ Failed: {e}")


async def main():
    print("="*60)
    print("UNIFIED ONBOARDING AGENT TEST SUITE")
    print("="*60)
    
    await test_context_builder()
    await test_tool_a()
    await test_tool_b()
    await test_routing()
    await test_integration()
    
    print("\n" + "="*60)
    print("TEST COMPLETE")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())
