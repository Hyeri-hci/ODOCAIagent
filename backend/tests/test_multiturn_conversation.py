"""
멀티턴 대화 및 에이전트 기능 통합 테스트

실행: python -m backend.tests.test_multiturn_conversation
"""

import asyncio
import json
import logging
from typing import Dict, Any, List
from datetime import datetime
import sys
import os

# 프로젝트 루트 경로 추가 (스크립트로 실행 시 필요)
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../../"))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)


# ============================================================
# 테스트 시나리오
# ============================================================

SCENARIOS = [
    # 시나리오 1: 기본 진단
    {
        "name": "기본 진단 요청",
        "messages": [
            "facebook/react 저장소 분석해줘"
        ],
        "expected": {
            "target_agent": "diagnosis",
            "has_health_score": True
        }
    },
    
    # 시나리오 2: 멀티턴 대화 - 진단 후 온보딩
    {
        "name": "멀티턴: 진단 → 온보딩",
        "messages": [
            "microsoft/vscode 분석해줘",
            "이 저장소에 기여하려면 어떻게 시작해야 해?"
        ],
        "expected": {
            "message_1_agent": "diagnosis",
            "message_2_agent": "onboarding"
        }
    },
    
    # 시나리오 3: 보안 분석
    {
        "name": "보안 분석 요청",
        "messages": [
            "vercel/next.js 보안 취약점 확인해줘"
        ],
        "expected": {
            "target_agent": "security",
            "has_security_score": True
        }
    },
    
    # 시나리오 4: 추천 에이전트
    {
        "name": "유사 프로젝트 추천",
        "messages": [
            "facebook/react와 비슷한 프로젝트 추천해줘"
        ],
        "expected": {
            "target_agent": "recommend"
        }
    },
    
    # 시나리오 5: 신규 기여자 가이드
    {
        "name": "신규 기여자 가이드",
        "messages": [
            "처음 오픈소스 기여하려는데 좋은 이슈 추천해줘"
        ],
        "expected": {
            "target_agent": "contributor"
        }
    },
    
    # 시나리오 6: 복합 멀티턴
    {
        "name": "멀티턴: 진단 → 질문 → 보안",
        "messages": [
            "langchain-ai/langchain 분석해줘",
            "점수가 왜 이렇게 나왔어?",
            "보안 측면에서는 어때?"
        ],
        "expected": {
            "message_1_agent": "diagnosis",
            "message_2_agent": "chat",
            "message_3_agent": "security"
        }
    },
    
    # 시나리오 7: 저장소 변경 감지
    {
        "name": "대화 중 저장소 변경",
        "messages": [
            "facebook/react 분석해줘",
            "이제 vue.js 분석해줘"
        ],
        "expected": {
            "repo_changed": True
        }
    },
    
    # 시나리오 8: 세션 유지
    {
        "name": "세션 컨텍스트 유지",
        "messages": [
            "pytorch/pytorch 분석해줘",
            "문서화는 잘 되어있어?",
            "액티비티는 어때?"
        ],
        "expected": {
            "session_maintained": True
        }
    }
]


# ============================================================
# 테스트 러너
# ============================================================

class TestRunner:
    def __init__(self):
        self.results: List[Dict[str, Any]] = []
        self.current_session_id = None
        self.current_owner = None
        self.current_repo = None
    
    def _parse_repo_from_message(self, message: str) -> tuple[str, str]:
        """메시지에서 저장소 정보 추출 (owner, repo)"""
        import re
        
        # GitHub URL 패턴
        url_pattern = r'github\.com[:/]([^/\s]+)/([^/\s]+)'
        match = re.search(url_pattern, message)
        if match:
            return match.group(1), match.group(2).rstrip('/')
        
        # owner/repo 패턴
        repo_pattern = r'\b([a-zA-Z0-9_-]+)/([a-zA-Z0-9_.-]+)\b'
        match = re.search(repo_pattern, message)
        if match:
            return match.group(1), match.group(2)
        
        return None, None
        
    async def run_scenario(self, scenario: Dict[str, Any]) -> Dict[str, Any]:
        """단일 시나리오 실행"""
        logger.info(f"\n{'='*60}")
        logger.info(f"시나리오: {scenario['name']}")
        logger.info(f"{'='*60}")
        
        from backend.agents.supervisor.graph import run_supervisor
        
        self.current_session_id = None
        self.current_owner = None
        self.current_repo = None
        responses = []
        
        for i, message in enumerate(scenario["messages"], 1):
            logger.info(f"\n[사용자 {i}] {message}")
            
            try:
                # 메시지에서 저장소 정보 추출
                owner, repo = self._parse_repo_from_message(message)
                
                # 새로운 저장소 정보가 있으면 업데이트, 없으면 이전 값 유지
                if owner and repo:
                    self.current_owner = owner
                    self.current_repo = repo
                    logger.info(f"저장소 감지: {owner}/{repo}")
                
                # 저장소 정보가 없으면 기본값 사용
                if not self.current_owner or not self.current_repo:
                    self.current_owner = "facebook"
                    self.current_repo = "react"
                    logger.info(f"기본 저장소 사용: {self.current_owner}/{self.current_repo}")
                
                # Supervisor 실행
                result = await run_supervisor(
                    owner=self.current_owner,
                    repo=self.current_repo,
                    user_message=message,
                    session_id=self.current_session_id
                )
                
                # 세션 ID 저장
                if result.get("session_id"):
                    self.current_session_id = result["session_id"]
                
                # Target agent 로깅
                target_agent = result.get("target_agent")
                logger.info(f"실행된 Agent: {target_agent}")
                
                # 응답 로깅
                answer = result.get("final_answer", "응답 없음")
                logger.info(f"[AI] {answer[:200]}..." if len(str(answer)) > 200 else f"[AI] {answer}")
                
                # 추가 정보 로깅 (디버깅용)
                if result.get("needs_clarification"):
                    logger.info(f"명확화 필요: {result.get('clarification_questions', [])}")
                
                # 결과 저장
                responses.append({
                    "message": message,
                    "target_agent": target_agent,
                    "session_id": result.get("session_id"),
                    "has_answer": bool(result.get("final_answer")),
                    "answer_preview": str(answer)[:100],
                    "needs_clarification": result.get("needs_clarification", False)
                })
                
            except Exception as e:
                logger.error(f"에러 발생: {e}")
                responses.append({
                    "message": message,
                    "error": str(e)
                })
        
        # 결과 검증
        passed = self._verify_scenario(scenario, responses)
        
        result = {
            "scenario": scenario["name"],
            "passed": passed,
            "responses": responses
        }
        self.results.append(result)
        
        status = "PASS" if passed else "FAIL"
        logger.info(f"\n결과: {status}")
        
        return result
    
    def _verify_scenario(self, scenario: Dict, responses: List[Dict]) -> bool:
        """시나리오 검증"""
        expected = scenario.get("expected", {})
        
        # 기본 검증
        if "target_agent" in expected and responses:
            if responses[0].get("target_agent") != expected["target_agent"]:
                logger.warning(f"Expected agent: {expected['target_agent']}, Got: {responses[0].get('target_agent')}")
                return False
        
        # 멀티턴 검증
        for key, value in expected.items():
            if key.startswith("message_"):
                idx = int(key.split("_")[1]) - 1
                if idx < len(responses):
                    if responses[idx].get("target_agent") != value:
                        logger.warning(f"{key}: Expected {value}, Got: {responses[idx].get('target_agent')}")
                        return False
        
        # 에러 없음 확인
        for resp in responses:
            if "error" in resp:
                return False
        
        return True
    
    async def run_all(self, scenarios: List[Dict] = None):
        """모든 시나리오 실행"""
        scenarios = scenarios or SCENARIOS
        
        logger.info(f"\n{'#'*60}")
        logger.info(f"멀티턴 대화 테스트 시작")
        logger.info(f"총 {len(scenarios)}개 시나리오")
        logger.info(f"{'#'*60}")
        
        for scenario in scenarios:
            await self.run_scenario(scenario)
            await asyncio.sleep(1)  # 요청 간 간격
        
        # 최종 결과
        self._print_summary()
    
    def _print_summary(self):
        """결과 요약 출력"""
        passed = sum(1 for r in self.results if r["passed"])
        total = len(self.results)
        
        logger.info(f"\n{'#'*60}")
        logger.info(f"테스트 결과 요약")
        logger.info(f"{'#'*60}")
        logger.info(f"통과: {passed}/{total}")
        
        for result in self.results:
            status = "PASS" if result["passed"] else "FAIL"
            logger.info(f"  [{status}] {result['scenario']}")
        
        if passed == total:
            logger.info(f"\n모든 테스트 통과!")
        else:
            logger.info(f"\n{total - passed}개 테스트 실패")


async def main():
    """메인 실행"""
    runner = TestRunner()
    await runner.run_all()


if __name__ == "__main__":
    asyncio.run(main())
