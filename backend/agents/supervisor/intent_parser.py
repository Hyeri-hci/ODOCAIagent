"""
Supervisor Intent Parser V2
최상위 의도 파싱 - 어느 agent로 라우팅할지, 명확화가 필요한지 결정
세션 기반 대화 지원

=== 설계 원칙 ===
1. 키워드 전처리로 80% 케이스 빠르게 분류 (LLM 호출 없이)
2. 모호한 케이스만 LLM 호출
3. Few-shot 예제는 YAML에서 로드
"""

from typing import Dict, Any, Optional, List, Literal
from pydantic import BaseModel, Field
import logging
import re
import yaml
from pathlib import Path

from backend.common.intent_utils import (
    IntentParserBase,
    extract_experience_level,
    summarize_session_context
)

logger = logging.getLogger(__name__)

# YAML에서 키워드 규칙 로드
def _load_keyword_rules() -> Dict[str, Any]:
    """intent_examples.yaml에서 키워드 규칙 로드"""
    yaml_path = Path(__file__).parent.parent.parent / "prompts" / "intent_examples.yaml"
    try:
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return data.get("keyword_rules", {})
    except Exception as e:
        logger.warning(f"Failed to load keyword rules: {e}")
        return {}

KEYWORD_RULES = _load_keyword_rules()


class SupervisorIntentV2(BaseModel):
    """Supervisor 수준 의도 (세션 기반)"""
    
    task_type: Literal[
        "diagnosis",      # 진단 관련
        "onboarding",     # 온보딩 관련
        "security",       # 보안 관련
        "recommend",      # 추천 관련
        "contributor",    # 기여자 지원 관련
        "comparison",     # 비교 분석 관련
        "general_chat",   # 일반 대화
        "clarification"   # 명확화 필요
    ]
    
    target_agent: Literal["diagnosis", "onboarding", "security", "recommend", "contributor", "comparison", "chat", "none"]
    
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

    comparison_targets: Optional[List[str]] = Field(
        default=None,
        description="비교할 저장소 목록 (예: ['owner1/repo1', 'owner2/repo2'])"
    )
    
    # 멀티 에이전트 협업
    additional_agents: List[str] = Field(
        default_factory=list,
        description="추가로 실행할 에이전트들 (예: ['security', 'onboarding'])"
    )


class SupervisorIntentParserV2(IntentParserBase):
    """Supervisor 의도 파싱기 V2 (세션 지원)"""
    
    # URL 패턴 (Trailing slash, dot git, @ref 지원)
    GITHUB_URL_PATTERN = re.compile(
        r'(?:https?://)?(?:www\.)?github\.com/([a-zA-Z0-9_-]+)/([a-zA-Z0-9_.-]+)(?:.git)?(?:/)?(?:tree/([a-zA-Z0-9_.-]+))?'
    )
    # Owner/Repo 패턴 (@ref 지원)
    REPO_PATTERN = re.compile(r'^([a-zA-Z0-9_-]+)/([a-zA-Z0-9_.-]+)(?:@([a-zA-Z0-9_.-]+))?$')

    def __init__(self):
        super().__init__()
        self.keyword_rules = KEYWORD_RULES
        logger.info("SupervisorIntentParserV2 initialized")

    def _extract_repo(self, message: str) -> Optional[str]:
        """메시지에서 저장소 추출 (ref 포함)"""
        # GitHub URL에서 추출
        url_match = self.GITHUB_URL_PATTERN.search(message)
        if url_match:
            repo = f"{url_match.group(1)}/{url_match.group(2)}"
            # .git 제거
            if repo.endswith(".git"):
                repo = repo[:-4]
            return repo

        # owner/repo 형식 추출
        words = message.split()
        for word in words:
            repo_match = self.REPO_PATTERN.match(word.strip())
            if repo_match:
                return f"{repo_match.group(1)}/{repo_match.group(2)}"

        return None

    def _is_url_only(self, message: str) -> bool:
        """URL 혹은 저장소 식별자만 입력되었는지 확인"""
        message = message.strip()

        # 1. GitHub URL 완전 일치 (Trailing slash 등 허용된 정규식 사용)
        if self.GITHUB_URL_PATTERN.fullmatch(message):
            return True

        # 2. Owner/Repo 완전 일치
        if self.REPO_PATTERN.fullmatch(message):
            return True

        # 3. URL + 간단한 키워드 (분석, 진단, 어때 등)인 경우도 URL 의도로 간주
        # 정규식 부분을 제거하고 남은 텍스트가 "분석", "진단" 등인지 확인
        url_removed = self.GITHUB_URL_PATTERN.sub("", message).strip()
        if not url_removed: # URL 제거 후 빈 문자열이면 OK
             return True

        # owner/repo 제거 시도
        repo_removed = self.REPO_PATTERN.sub("", message).strip()
        if not repo_removed:
            return True

        # 허용된 접미사 키워드
        allowed_suffixes = ["", "어때", "어때?", "분석", "분석해줘", "진단", "진단해줘", "확인", "확인해줘"]
        if url_removed in allowed_suffixes or repo_removed in allowed_suffixes:
            return True

        return False
    
    def _keyword_preprocess(self, message: str) -> Optional[str]:
        """키워드 기반 빠른 분류 (LLM 호출 없이)
        
        Returns:
            target_agent 이름 또는 None (LLM 필요)
        """
        message_lower = message.lower()
        
        # 모든 키워드 매칭 수집
        matched = []
        for agent, rule in self.keyword_rules.items():
            keywords = rule.get("keywords", [])
            priority = rule.get("priority", 99)
            for kw in keywords:
                if kw.lower() in message_lower:
                    # (priority, -keyword_length, agent, keyword) 
                    # 우선순위 같으면 더 긴 키워드 우선
                    matched.append((priority, -len(kw), agent, kw))
        
        if not matched:
            return None
        
        # 우선순위가 가장 높은 (숫자가 작은) + 더 긴 키워드 우선
        matched.sort(key=lambda x: (x[0], x[1]))
        agent = matched[0][2]
        matched_kw = matched[0][3]
        logger.info(f"Keyword matched: '{matched_kw}' -> {agent}")
        
        # agent 이름 정규화
        agent_mapping = {
            "diagnosis": "diagnosis",
            "onboarding_structure": "onboarding",
            "onboarding_issues": "onboarding",
            "onboarding": "onboarding",
            "security": "security",
            "recommend": "recommend",
            "comparison": "comparison",
        }
        
        return agent_mapping.get(agent)
    
    async def parse(
        self,
        user_message: str,
        session_context: Optional[Dict[str, Any]] = None,
        pre_detected_repo: Optional[str] = None  # intent_parser_node에서 이미 감지한 저장소
    ) -> SupervisorIntentV2:
        """
        사용자 메시지를 Supervisor 의도로 파싱
        
        처리 순서:
        1. URL만 입력 → diagnosis (LLM 호출 안 함)
        2. 키워드 전처리 → 명확한 경우 LLM 스킵
        3. 모호한 경우만 LLM 호출
        """
        
        # 저장소 추출 (메시지에서 직접 추출, 없으면 pre_detected_repo 사용)
        detected_repo = self._extract_repo(user_message) or pre_detected_repo
        
        # 컨텍스트 요약
        context_summary = summarize_session_context(session_context) if session_context else "없음"
        
        # === 1. URL만 입력 → 기본 진단 (LLM 스킵) ===
        if self._is_url_only(user_message) and detected_repo:
            logger.info(f"URL-only input detected: {detected_repo} → diagnosis (skipping LLM)")
            return SupervisorIntentV2(
                task_type="diagnosis",
                target_agent="diagnosis",
                detected_repo=detected_repo,
                confidence=0.95,
                reasoning="URL만 입력 → 기본 진단"
            )
        
        # === 2. 키워드 전처리 ===
        keyword_agent = self._keyword_preprocess(user_message)
        
        # === 2-1. recommend는 repo 없이도 동작 가능 ===
        # 키워드가 명확하면 LLM 스킵 (recommend, comparison은 repo 필요 없음)
        repo_not_required = keyword_agent in ("recommend", "comparison")
        has_repo = detected_repo or self._has_repo_in_context(session_context)
        
        if keyword_agent and (has_repo or repo_not_required):
            repo = detected_repo or self._get_repo_from_context(session_context)
            logger.info(f"Keyword match: {keyword_agent} for repo {repo} (skipping LLM)")
            
            # 온보딩 요청 시 경험 수준 체크
            needs_clarification = False
            clarification_questions = []
            if keyword_agent == "onboarding":
                experience_level = extract_experience_level(user_message)
                if not experience_level:
                    needs_clarification = True
                    clarification_questions = [
                        "프로그래밍 경험 수준을 알려주세요:",
                        "1. 입문자 2. 중급자 3. 숙련자"
                    ]
            
            # === 종합 분석(Comprehensive) 처리 ===
            # 키워드 전처리에서 'diagnosis'나 'onboarding' 등이 잡혔더라도, '종합', '전체' 키워드가 있으면 확장
            comprehensive_keywords = ["종합", "전체", "comprehensive", "full", "all"]
            is_comprehensive = any(k in user_message.lower() for k in comprehensive_keywords)
            
            additional_agents = []
            if is_comprehensive and keyword_agent == "diagnosis":
                 additional_agents = ["security", "onboarding", "contributor"]
                 logger.info("Comprehensive analysis keywords detected -> Adding additional agents")

            return SupervisorIntentV2(
                task_type=keyword_agent,
                target_agent=keyword_agent,
                detected_repo=repo,
                needs_clarification=needs_clarification,
                clarification_questions=clarification_questions,
                confidence=0.9,
                reasoning=f"키워드 매칭: {keyword_agent}" + (" (종합 분석)" if is_comprehensive else ""),
                additional_agents=additional_agents
            )
        
        # === 3. 모호한 경우 LLM 호출 ===
        prompt = self._build_prompt(user_message, context_summary)
        
        try:
            intent_data = await self._call_llm(prompt)
            
            # [Robustness] 한글 값 매핑 (LLM이 가끔 번역해서 응답함)
            # [Robustness] 한글 값 매핑 (Fuzzy Matching)
            target = intent_data.get("target_agent", "")
            if isinstance(target, str):
                if any(x in target for x in ["진단", "분석", "diagnosis"]): target = "diagnosis"
                elif any(x in target for x in ["온보딩", "가이드", "onboarding", "입문", "beginner"]): target = "onboarding"
                elif any(x in target for x in ["보안", "취약점", "security"]): target = "security"
                elif any(x in target for x in ["기여", "초심자", "contributor"]): target = "contributor"  # 기여자/초심자 대응
                elif any(x in target for x in ["추천", "recommend"]): target = "recommend"
                elif any(x in target for x in ["비교", "compare"]): target = "comparison"
                elif any(x in target for x in ["대화", "chat", "일반"]): target = "chat"
                
                if target != intent_data.get("target_agent"):
                    logger.info(f"Fuzzy mapped agent name '{intent_data.get('target_agent')}' to '{target}'")
                    intent_data["target_agent"] = target

            task_type = intent_data.get("task_type", "")
            if isinstance(task_type, str):
                 if any(x in task_type for x in ["진단", "분석", "diagnosis"]): task_type = "diagnosis"
                 elif any(x in task_type for x in ["온보딩", "가이드", "onboarding", "입문", "beginner"]): task_type = "onboarding"
                 elif any(x in task_type for x in ["보안", "취약점", "security"]): task_type = "security"
                 elif any(x in task_type for x in ["기여", "초심자", "contributor"]): task_type = "contributor"
                 elif any(x in task_type for x in ["추천", "recommend"]): task_type = "recommend"
                 elif any(x in task_type for x in ["비교", "compare"]): task_type = "comparison"
                 elif any(x in task_type for x in ["대화", "chat", "일반"]): task_type = "general_chat"

                 if task_type != intent_data.get("task_type"):
                     intent_data["task_type"] = task_type

            intent = SupervisorIntentV2(**intent_data)
            
            # 저장소 정보 보완
            if not intent.detected_repo and detected_repo:
                intent.detected_repo = detected_repo
            
            # 온보딩 요청 시 사용자 경험 수준 체크
            if intent.task_type == "onboarding" and not intent.needs_clarification:
                experience_level = extract_experience_level(user_message)
                if not experience_level:
                    logger.info("Onboarding request without experience level")
                    intent.needs_clarification = True
                    intent.clarification_questions = [
                        "프로그래밍 경험 수준을 알려주세요:",
                        "1. 입문자 2. 중급자 3. 숙련자"
                    ]
            
            logger.info(
                f"LLM parsed intent: task_type={intent.task_type}, "
                f"target_agent={intent.target_agent}, "
                f"confidence={intent.confidence}"
            )
            
            return intent
            
        except Exception as e:
            logger.error(f"Failed to parse intent: {e}")
            
            # LLM 실패해도 키워드 agent가 있으면 해당 agent로 라우팅
            # recommend, comparison은 저장소 없이도 동작 가능
            repo_not_required_agents = ("recommend", "comparison")
            if keyword_agent and (detected_repo or keyword_agent in repo_not_required_agents):
                logger.info(f"LLM failed, using keyword fallback: {keyword_agent} for {detected_repo or 'no repo (keyword search)'}")
                return SupervisorIntentV2(
                    task_type=keyword_agent,
                    target_agent=keyword_agent,
                    detected_repo=detected_repo,
                    needs_clarification=False,
                    confidence=0.7,
                    reasoning=f"LLM 파싱 실패, 키워드 fallback: {keyword_agent}"
                )
            
            return SupervisorIntentV2(
                task_type="clarification",
                target_agent="none",
                needs_clarification=True,
                clarification_questions=["무엇을 도와드릴까요?"],
                confidence=0.0,
                reasoning=f"파싱 실패: {str(e)}"
            )
    
    def _has_repo_in_context(self, session_context: Optional[Dict]) -> bool:
        """세션 컨텍스트에 저장소가 있는지 확인"""
        if not session_context:
            return False
        return bool(session_context.get("owner") and session_context.get("repo"))
    
    def _get_repo_from_context(self, session_context: Optional[Dict]) -> Optional[str]:
        """세션 컨텍스트에서 저장소 추출"""
        if not session_context:
            return None
        owner = session_context.get("owner")
        repo = session_context.get("repo")
        if owner and repo:
            return f"{owner}/{repo}"
        return None
    
    def _build_prompt(self, user_message: str, context_summary: str) -> str:
        """간소화된 LLM 프롬프트 생성 (~40줄)"""
        return f"""GitHub 저장소 분석 시스템 의도 분류기.

[입력] {user_message}
[컨텍스트] {context_summary}

## 분류 기준
- diagnosis: 분석/진단/건강도/점수/상태 (URL만 있어도 diagnosis)
- onboarding: 기여시작/가이드/코드구조/이슈추천/학습플랜
- security: 보안/취약점/CVE
- recommend: 유사프로젝트/추천/대안/"프로젝트 찾아줘"
- comparison: 프로젝트 vs 프로젝트 비교
- contributor: 기여자분석/커뮤니티활동
- general_chat: 일반대화/인사/개념질문
- clarification: 정보부족 (저장소 없음)

## 핵심 규칙
1. URL/owner/repo만 입력 → diagnosis
2. "비슷한 프로젝트", "대안", "찾아줘" → recommend (NOT general_chat!)
3. "코드 구조", "폴더 구조" → onboarding
4. "좋은 이슈", "first issue" → onboarding
5. 저장소 없고 분석 요청 → clarification + "어떤 저장소?" 질문
6. 대명사("이거", "그거") + 이전 결과 → uses_previous_context=true

## JSON 응답 형식
{{
  "task_type": "...",
  "target_agent": "...",
  "detected_repo": "owner/repo" | null,
  "needs_clarification": false,
  "clarification_questions": [],
  "uses_previous_context": false,
  "referenced_data": [],
  "additional_agents": [],
  "comparison_targets": null,
  "confidence": 0.9,
  "reasoning": "판단 근거 한줄"
}}"""
