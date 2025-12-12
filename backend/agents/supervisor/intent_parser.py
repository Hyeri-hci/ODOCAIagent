"""
Supervisor Intent Parser V2
최상위 의도 파싱 - 어느 agent로 라우팅할지, 명확화가 필요한지 결정
세션 기반 대화 지원
"""

from typing import Dict, Any, Optional, List, Literal
from pydantic import BaseModel, Field
import logging

from backend.common.intent_utils import (
    IntentParserBase,
    extract_experience_level,
    summarize_session_context
)

logger = logging.getLogger(__name__)


class SupervisorIntentV2(BaseModel):
    """Supervisor 수준 의도 (세션 기반)"""
    
    task_type: Literal[
        "diagnosis",      # 진단 관련
        "onboarding",     # 온보딩 관련
        "security",       # 보안 관련
        "recommend",      # 추천 관련
        "contributor",    # 기여자 지원 관련
        "general_chat",   # 일반 대화
        "clarification"   # 명확화 필요
    ]
    
    target_agent: Literal["diagnosis", "onboarding", "security", "recommend", "contributor", "chat", "none"]
    
    # Agentic 기능
    needs_clarification: bool = Field(
        default=False,
        description="명확화 필요 여부"
    )
    clarification_questions: List[str] = Field(
        default_factory=list,
        description="되물을 질문들"
    )
    
    # 세션 컨텍스트 활용
    uses_previous_context: bool = Field(
        default=False,
        description="이전 컨텍스트 활용 여부"
    )
    referenced_data: List[str] = Field(
        default_factory=list,
        description="참조할 데이터 키들 (예: ['diagnosis_result'])"
    )
    
    # 디버깅
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="의도 파악 신뢰도"
    )
    reasoning: str = Field(
        default="",
        description="의도 파악 근거"
    )
    
    # 추가 메타데이터
    detected_repo: Optional[str] = Field(
        default=None,
        description="메시지에서 감지된 저장소 (owner/repo)"
    )
    implicit_context: bool = Field(
        default=False,
        description="암묵적 컨텍스트 사용 여부"
    )
    
    # 멀티 에이전트 협업
    additional_agents: List[str] = Field(
        default_factory=list,
        description="추가로 실행할 에이전트들 (예: ['security', 'onboarding'])"
    )


class SupervisorIntentParserV2(IntentParserBase):
    """Supervisor 의도 파싱기 V2 (세션 지원)"""
    
    def __init__(self):
        super().__init__()
        logger.info("SupervisorIntentParserV2 initialized")
    
    async def parse(
        self,
        user_message: str,
        session_context: Optional[Dict[str, Any]] = None
    ) -> SupervisorIntentV2:
        """
        사용자 메시지를 Supervisor 의도로 파싱
        
        Args:
            user_message: 사용자 메시지
            session_context: 세션 컨텍스트 (있으면)
                {
                    "owner": "facebook",
                    "repo": "react",
                    "conversation_history": [...],
                    "accumulated_context": {...}
                }
        """
        
        # 컨텍스트 요약
        context_summary = summarize_session_context(session_context) if session_context else "없음"
        
        prompt = f"""당신은 GitHub 저장소 분석 시스템의 의도 파악 전문가입니다.

=== 사용자 메시지 ===
{user_message}

=== 세션 컨텍스트 ===
{context_summary}

=== 지시사항 ===
사용자의 의도를 파악하여 다음 JSON 형식으로 반환하세요:

{{
    "task_type": "diagnosis" | "onboarding" | "security" | "recommend" | "contributor" | "general_chat" | "clarification",
    "target_agent": "diagnosis" | "onboarding" | "security" | "recommend" | "contributor" | "chat" | "none",
    "additional_agents": ["diagnosis", "security", "onboarding", "contributor", "recommend"],
    "needs_clarification": true | false,
    "clarification_questions": ["질문1", "질문2"],
    "uses_previous_context": true | false,
    "referenced_data": ["diagnosis_result", "onboarding_plan"],
    "confidence": 0.0 ~ 1.0,
    "reasoning": "의도 파악 근거",
    "detected_repo": "owner/repo" | null,
    "implicit_context": true | false
}}

=== 판단 기준 ===

1. task_type 결정:
   - "분석", "분석해줘", "전체 분석", "진단", "건강도", "점수", "상태 확인", "건강 상태" → diagnosis
   - "온보딩", "가이드", "기여 방법", "기여하려면", "시작하려면", "어떻게 시작", "기여 시작", "학습 플랜" → onboarding
   - "보안", "취약점", "CVE", "취약점 분석", "보안 분석" → security
   - "추천", "추천해줘", "비슷한 프로젝트", "유사 프로젝트", "대안", "다른 프로젝트", "비슷한 저장소", "similar" → recommend
   - **"프로젝트 찾", "프로젝트로 알려", "오픈소스 프로젝트", "프로젝트 알려줘", "찾고 있어", "찾아줘" + "프로젝트" → recommend (중요!)**
   - "Good First Issue", "이슈 추천", "좋은 이슈", "기여 체크리스트", "첫 PR" → contributor
   - "커뮤니티", "커뮤니티 활동" → contributor (community_analysis 기능)
   - "비교해줘", "알려줘", "설명해줘", "뭐야", "무엇인지" → general_chat (단, "프로젝트"와 함께 쓰이면 recommend!)
   - 정보가 부족하면 → clarification
   
   **!!!!! 매우 중요: recommend vs general_chat 구분 !!!!!**
   - "오픈소스 프로젝트로 알려줘" → recommend (general_chat 아님!)
   - "프로젝트 찾아줘", "프로젝트 추천해줘" → recommend
   - "오픈소스", "프로젝트"가 포함된 요청 → recommend
   - 단순한 "알려줘", "설명해줘"만 있으면 → general_chat
   
   **중요: "코드 구조", "폴더 구조", "구조 보기", "트리 구조" 요청 처리**
   - 세션 컨텍스트에 diagnosis_result가 있으면 → general_chat (이전 결과 참조)
     - uses_previous_context = true
     - referenced_data = ["diagnosis_result", "structure_visualization"]
   - 세션에 diagnosis_result가 없으면 → contributor (새로 가져옴)
   
   **중요: diagnosis vs contributor 구분**
   - "분석해줘", "전체 분석", "진단해줘", "건강도", "상태 확인" → diagnosis (저장소 전체 진단)
   - "첫 기여", "이슈 추천", "체크리스트" → contributor (기여자 지원)

2. additional_agents (복합 의도 감지):
   - **기본 규칙: 사용자가 명시적으로 여러 작업을 요청할 때만 추가**
   - 예: "진단하고 보안도 확인해줘" → target_agent="diagnosis", additional_agents=["security"]
   - 예: "분석하고 기여 방법도 알려줘" → target_agent="diagnosis", additional_agents=["onboarding"]
   - **단순 분석/진단 요청은 additional_agents=[] (빈 배열)**
   - 예: "분석해줘", "진단해줘" → target_agent="diagnosis", additional_agents=[]
   - 보안 분석은 시스템이 자동으로 추가하므로 여기서 추가하지 않음

3. needs_clarification (중요!):
   **저장소 명확화 기준:**
   - 메시지에 저장소가 명시되어 있거나 → false
   - 세션 컨텍스트에 owner/repo가 있으면 (예: "Repository: facebook/react") → false
   - 대명사("이", "저", "그", "해당")가 있고 세션에 저장소 정보가 있으면 → false (암묵적 참조)
   - 메시지에도 없고 세션에도 없으면 → true (어떤 저장소인지 물어봐야 함)
   
   **온보딩/기여 요청 시 사용자 수준 확인:**
   - task_type이 "onboarding" 또는 "contributor"이고
   - 사용자 경험 수준이 명시되지 않았고 (메시지에 "입문자", "초보자", "beginner" 등 없음)
   - 세션에 user_profile.experience_level도 없으면
   → needs_clarification = true
   → clarification_questions에 추가: "프로그래밍 경험 수준을 알려주세요: 1) 입문자 2) 중급자 3) 숙련자"
   
   **예시:**
   - "진단해줘" + 세션에 facebook/react 있음 → needs_clarification = false
   - "이 저장소에 기여하려면?" + 세션에 microsoft/vscode 있음 → needs_clarification = false
   - "온보딩 플랜 만들어줘" + 저장소 없음 → needs_clarification = true (저장소 물어봄)
   - "facebook/react 온보딩 플랜" → needs_clarification = false (저장소 있음, 경험수준은 선택사항으로 기본값 사용)

3. uses_previous_context:
   - "그거", "더 자세히", "다시", "아까" 등 → true
   - 세션에 이미 데이터가 있고 참조 가능 → true
   - ⚠️ 대명사 감지 시 referenced_data에 해당 데이터 명시

4. implicit_context:
   - owner/repo가 명시되지 않았지만 세션에서 추론 가능 → true

5. confidence:
   - 명확한 요청 (저장소 명시, 구체적 동작) → 0.9+
   - 대명사 참조가 명확한 경우 → 0.8+
   - 일반적 요청 → 0.7~0.8
   - 모호한 요청 → 0.5 이하

6. detected_repo 결정 (중요!):
   - 메시지에 "owner/repo" 형식 명시 → 해당 저장소
   - 메시지에 프로젝트명만 있음 (예: "react", "vscode") → 세션의 Last mentioned repo 확인
   - "📌 Last mentioned repo: owner/repo"가 있으면 → 해당 저장소 사용
   - 메시지에 저장소 없음 + Last mentioned repo 없음 → 세션의 Repository 사용
   - 예: "진단해줘" + Last mentioned repo: microsoft/vscode → detected_repo="microsoft/vscode"

7. **대화 연속성 (매우 중요!)**:
   - 세션 컨텍스트의 "Last intent"가 있으면 대화의 연속성을 고려하세요
   - **이전에 clarification을 요청했고 사용자가 그에 대해 대답하고 있다면:**
     - 사용자의 응답이 이전 질문의 답변으로 보이면 → 원래 task_type 유지
     - 예: 이전 intent가 recommend이고 clarification 질문 후 "오픈소스로 찾고 싶어"라고 답변
       → task_type = "recommend" (general_chat 아님!)
   - **프로젝트 찾기/추천 관련 키워드가 있으면 recommend:**
     - "프로젝트 찾고 있어", "오픈소스 프로젝트", "프로젝트 찾아줘", "찾고 싶어" → recommend
     - 특정 기술/분야 언급 + "프로젝트" → recommend
   - **일반적인 대화가 아닌 작업 요청은 general_chat이 아님:**
     - "~해줘", "~찾아줘", "~추천해줘" 같은 요청은 해당 에이전트로 라우팅

=== 대화 연속성 예시 ===

입력: "그런 건 따로 없고, 오픈소스 프로젝트로 찾고 싶어"
컨텍스트: Last intent = recommend (clarification 요청 후)
→ {{"task_type": "recommend", "target_agent": "recommend", "needs_clarification": false}}
(NOT general_chat!)

입력: "자율주행 딥러닝 프로젝트 찾아줘"
컨텍스트: 새 세션
→ {{"task_type": "recommend", "target_agent": "recommend"}}

=== 대명사 처리 예시 ===

입력: "그거 초보자 관점에서 다시 설명해줘"
컨텍스트: diagnosis_result 있음
→ {{"task_type": "diagnosis", "target_agent": "diagnosis", "uses_previous_context": true, "referenced_data": ["diagnosis_result"]}}

입력: "더 자세히 알려줘"
컨텍스트: 이전에 onboarding_plan 생성
→ {{"task_type": "onboarding", "target_agent": "onboarding", "uses_previous_context": true}}
"""

        try:
            intent_data = await self._call_llm(prompt)
            intent = SupervisorIntentV2(**intent_data)
            
            # 온보딩/기여 요청 시 사용자 경험 수준 체크
            if intent.task_type == "onboarding" and not intent.needs_clarification:
                experience_level = extract_experience_level(user_message)
                
                if not experience_level:
                    # 사용자 수준이 명시되지 않았으면 clarification 필요
                    logger.info("Onboarding request without experience level - requesting clarification")
                    intent.needs_clarification = True
                    intent.clarification_questions = [
                        "온보딩 플랜을 생성하기 전에 프로그래밍 경험 수준을 알려주세요:",
                        "1. 입문자 - 프로그래밍을 막 시작했거나 이 기술 스택이 처음이에요",
                        "2. 중급자 - 기본 개념은 알고 있고, 실제 프로젝트 경험을 쌓고 싶어요",
                        "3. 숙련자 - 경험이 많고, 핵심 기여나 아키텍처 이해를 원해요"
                    ]
            
            logger.info(
                f"Parsed intent: task_type={intent.task_type}, "
                f"target_agent={intent.target_agent}, "
                f"confidence={intent.confidence}, "
                f"needs_clarification={intent.needs_clarification}"
            )
            
            return intent
            
        except Exception as e:
            logger.error(f"Failed to parse intent: {e}")
            # Fallback: 기본 의도 반환
            return SupervisorIntentV2(
                task_type="clarification",
                target_agent="none",
                needs_clarification=True,
                clarification_questions=["무엇을 도와드릴까요?"],
                confidence=0.0,
                reasoning=f"파싱 실패: {str(e)}"
            )
