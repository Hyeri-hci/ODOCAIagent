"""
간단한 통합 테스트 - 개별 컴포넌트 검증

실행: python -m backend.tests.test_components
"""

import asyncio
import logging
from typing import Dict, Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)


async def test_intent_parser():
    """의도 파서 테스트"""
    logger.info("\n=== 의도 파서 테스트 ===")
    
    from backend.agents.supervisor.intent_parser import SupervisorIntentParserV2
    
    parser = SupervisorIntentParserV2()
    
    test_cases = [
        ("facebook/react 분석해줘", "diagnosis"),
        ("보안 취약점 확인해줘", "security"),
        ("온보딩 가이드 만들어줘", "onboarding"),
        ("비슷한 프로젝트 추천해줘", "recommend"),
        ("Good First Issue 찾아줘", "contributor"),
        ("점수가 왜 이래?", "chat"),
    ]
    
    passed = 0
    for message, expected in test_cases:
        result = await parser.parse(message)
        actual = result.target_agent if result else "none"
        status = "PASS" if actual == expected else "FAIL"
        logger.info(f"  [{status}] '{message}' -> {actual} (expected: {expected})")
        if actual == expected:
            passed += 1
    
    logger.info(f"  결과: {passed}/{len(test_cases)} 통과")
    return passed == len(test_cases)


async def test_diagnosis_graph():
    """진단 그래프 테스트"""
    logger.info("\n=== 진단 그래프 테스트 ===")
    
    from backend.agents.diagnosis.graph import run_diagnosis
    
    try:
        result = await run_diagnosis(
            owner="facebook",
            repo="react",
            user_message="분석해줘"
        )
        
        has_score = "health_score" in result
        has_level = "health_level" in result
        
        logger.info(f"  health_score: {result.get('health_score')}")
        logger.info(f"  health_level: {result.get('health_level')}")
        logger.info(f"  결과: {'PASS' if has_score and has_level else 'FAIL'}")
        
        return has_score and has_level
    except Exception as e:
        logger.error(f"  에러: {e}")
        return False


async def test_streaming():
    """스트리밍 테스트"""
    logger.info("\n=== 스트리밍 테스트 ===")
    
    from backend.agents.diagnosis.graph import run_diagnosis_stream
    
    try:
        events = []
        async for event in run_diagnosis_stream(
            owner="facebook",
            repo="react"
        ):
            events.append(event)
            logger.info(f"  노드: {event.get('node')} ({event.get('progress')}%) - {event.get('message')}")
        
        has_complete = any(e.get("node") == "complete" for e in events)
        logger.info(f"  이벤트 수: {len(events)}")
        logger.info(f"  결과: {'PASS' if has_complete else 'FAIL'}")
        
        return has_complete
    except Exception as e:
        logger.error(f"  에러: {e}")
        return False


async def test_session():
    """세션 관리 테스트"""
    logger.info("\n=== 세션 관리 테스트 ===")
    
    from backend.common.session import get_session_store
    
    try:
        store = get_session_store()
        
        # 세션 생성
        session = store.create_session(owner="test", repo="test")
        session_id = session.session_id
        logger.info(f"  생성된 세션: {session_id}")
        
        # 세션 조회
        loaded = store.get_session(session_id)
        exists = loaded is not None
        logger.info(f"  세션 조회: {'PASS' if exists else 'FAIL'}")
        
        return exists
    except Exception as e:
        logger.error(f"  에러: {e}")
        return False


async def run_all_tests():
    """모든 테스트 실행"""
    logger.info("\n" + "#"*60)
    logger.info("컴포넌트 통합 테스트")
    logger.info("#"*60)
    
    results = {}
    
    # 테스트 실행
    results["intent_parser"] = await test_intent_parser()
    results["diagnosis_graph"] = await test_diagnosis_graph()
    results["streaming"] = await test_streaming()
    results["session"] = await test_session()
    
    # 결과 요약
    logger.info("\n" + "#"*60)
    logger.info("테스트 결과 요약")
    logger.info("#"*60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for name, result in results.items():
        status = "PASS" if result else "FAIL"
        logger.info(f"  [{status}] {name}")
    
    logger.info(f"\n총 결과: {passed}/{total} 통과")
    
    return passed == total


if __name__ == "__main__":
    asyncio.run(run_all_tests())
