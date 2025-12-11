"""
Diagnosis Intent Parser
Diagnosis Agent 전용 - Fast/Full/Reinterpret 경로 결정
"""
from typing import Dict, Any, Optional, List, Literal
from pydantic import BaseModel, Field
import logging
import json

from backend.common.intent_utils import (
    IntentParserBase,
    detect_force_refresh,
    detect_detail_level
)

logger = logging.getLogger(__name__)


# 관점 정의
ReinterpretPerspective = Literal[
    "beginner",           # 초보자 관점
    "tech_lead",          # 기술 리드 관점
    "security_officer",   # 보안 담당자 관점
    "manager",            # 관리자 관점
    "contributor",        # 기여자 관점
    "maintainer"          # 오픈소스 메인테이너 관점
]


class DiagnosisIntentV2(BaseModel):
    """Diagnosis Agent 전용 의도"""
    
    execution_path: Literal["fast", "full", "reinterpret"]
    
    # Fast Path
    quick_query_target: Optional[Literal["readme", "activity", "dependencies", "structure"]] = None
    
    # Full Path
    analysis_depth: Literal["quick", "standard", "thorough"] = "standard"
    force_refresh: bool = Field(
        default=False,
        description="캐시 무시하고 최신 데이터로 재분석"
    )
    
    # Reinterpret Path
    reinterpret_perspective: Optional[ReinterpretPerspective] = None
    reinterpret_detail_level: Literal["brief", "standard", "detailed"] = "standard"
    
    # 승급 (FAST → FULL)
    should_upgrade_to_full: bool = Field(
        default=False,
        description="Fast 실행 후 Full로 승급 여부"
    )
    
    # 디버깅
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reasoning: str = ""


class DiagnosisIntentParser(IntentParserBase):
    """Diagnosis Agent 전용 의도 파싱기"""
    
    def __init__(self):
        super().__init__()
        logger.info("DiagnosisIntentParser initialized")
    
    async def parse(
        self,
        user_message: str,
        supervisor_intent: Dict[str, Any],
        cached_diagnosis: Optional[Dict[str, Any]] = None
    ) -> DiagnosisIntentV2:
        """
        Diagnosis 실행 경로 결정
        
        Args:
            user_message: 사용자 원본 메시지
            supervisor_intent: Supervisor가 파싱한 의도
            cached_diagnosis: 캐시된 진단 결과 (있으면)
        """
        
        # 캐시 여부
        has_cache = cached_diagnosis is not None
        
        prompt = f"""당신은 GitHub 저장소 진단 시스템의 실행 경로 결정 전문가입니다.

=== 사용자 메시지 ===
{user_message}

=== Supervisor 의도 ===
{json.dumps(supervisor_intent, indent=2, ensure_ascii=False)}

=== 캐시 상태 ===
캐시된 진단 결과: {"있음" if has_cache else "없음"}

=== 지시사항 ===
다음 JSON 형식으로 실행 경로를 결정하세요:

{{
    "execution_path": "fast" | "full" | "reinterpret",
    "quick_query_target": "readme" | "activity" | "dependencies" | "structure" | null,
    "analysis_depth": "quick" | "standard" | "thorough",
    "force_refresh": true | false,
    "reinterpret_perspective": "beginner" | "tech_lead" | "security_officer" | "manager" | "contributor" | "maintainer" | null,
    "reinterpret_detail_level": "brief" | "standard" | "detailed",
    "should_upgrade_to_full": true | false,
    "confidence": 0.0 ~ 1.0,
    "reasoning": "결정 근거"
}}

=== 경로 결정 기준 ===

1. **Fast Path** (빠른 조회):
   - "README만", "최근 커밋만", "의존성만" 등 **특정 정보만** 명시적으로 요청
   - 전체 분석 불필요
   - quick_query_target 설정
   - ⚠️ 주의: "활발한지", "건강한지", "기여할만한지" 등 **평가/판단 질문은 Fast가 아님**

2. **Full Path** (전체 진단):
   - "분석해줘", "진단해줘", "건강도 체크"
   - "기여하고 싶은데", "사용해도 될까", "활발하게 유지보수되나요?" 등 **평가가 필요한 질문**
   - 캐시가 없거나 force_refresh 요청
   - analysis_depth:
     * quick: 빠른 개요 (1-2분)
     * standard: 표준 분석 (3-5분)
     * thorough: 상세 분석 (5-10분)

3. **Reinterpret Path** (재해석):
   - 캐시가 있고, "다른 관점으로", "초보자 관점으로" 등
   - reinterpret_perspective:
     * beginner: 초보자 (기술 용어 쉽게)
     * tech_lead: 기술 리드 (아키텍처 품질)
     * security_officer: 보안 담당자 (보안 위험)
     * manager: 관리자 (비즈니스 영향)
     * contributor: 기여자 (기여 가능 영역)
     * maintainer: 메인테이너 (유지보수 관점)
   - reinterpret_detail_level:
     * brief: 간략 (3-5문장)
     * standard: 표준 (1-2단락)
     * detailed: 상세 (여러 단락)

4. **force_refresh**:
   - "최신 데이터로", "다시 분석", "업데이트된" 등 명시 시 true

5. **should_upgrade_to_full**:
   - Fast 실행 후 "전체도 보고 싶어" 같은 확장 요청 가능성 있으면 true

=== 예시 ===

입력: "facebook/react README 보여줘"
→ {{"execution_path": "fast", "quick_query_target": "readme"}}

입력: "최근 커밋만 확인하고 싶어"
→ {{"execution_path": "fast", "quick_query_target": "activity"}}

입력: "저장소 분석해줘"
→ {{"execution_path": "full", "analysis_depth": "standard"}}

입력: "이 프로젝트에 기여하고 싶은데, 활발하게 유지보수되고 있나요?"
→ {{"execution_path": "full", "analysis_depth": "standard"}}
(이유: "기여하고 싶다"는 평가/판단이 필요한 질문이므로 Full Path)

입력: "이 라이브러리 프로덕션에 써도 될까요?"
→ {{"execution_path": "full", "analysis_depth": "standard"}}
(이유: 프로덕션 사용 가능 여부는 전체 분석이 필요)

입력: "초보자가 이해하기 쉽게 설명해줘" (캐시 있음)
→ {{"execution_path": "reinterpret", "reinterpret_perspective": "beginner"}}

입력: "최신 데이터로 다시 분석"
→ {{"execution_path": "full", "force_refresh": true}}
"""

        try:
            intent_data = await self._call_llm(prompt)
            
            # None 값 필터링 - Pydantic이 기본값을 사용하도록
            filtered_data = {k: v for k, v in intent_data.items() if v is not None}
            intent = DiagnosisIntentV2(**filtered_data)
            
            logger.info(
                f"Diagnosis intent: path={intent.execution_path}, "
                f"depth={intent.analysis_depth}, "
                f"force_refresh={intent.force_refresh}"
            )
            
            return intent
            
        except Exception as e:
            logger.error(f"Failed to parse diagnosis intent: {e}")
            # Fallback: Full Path
            return DiagnosisIntentV2(
                execution_path="full",
                analysis_depth="standard",
                confidence=0.0,
                reasoning=f"파싱 실패, 기본 Full Path: {str(e)}"
            )
    
    def parse_simple(
        self,
        user_message: str,
        has_cache: bool = False
    ) -> DiagnosisIntentV2:
        """
        간단한 규칙 기반 파싱 (LLM 없이)
        빠른 판단이 필요할 때 사용
        """
        
        lower_msg = user_message.lower()
        
        # Fast Path 패턴
        if "readme" in lower_msg and "만" in user_message:
            return DiagnosisIntentV2(
                execution_path="fast",
                quick_query_target="readme",
                confidence=0.8,
                reasoning="README만 요청"
            )
        
        if any(word in lower_msg for word in ["커밋", "활동", "activity"]) and "만" in user_message:
            return DiagnosisIntentV2(
                execution_path="fast",
                quick_query_target="activity",
                confidence=0.8,
                reasoning="활동만 요청"
            )
        
        # Reinterpret 패턴
        if has_cache and any(word in user_message for word in ["초보자", "beginner"]):
            return DiagnosisIntentV2(
                execution_path="reinterpret",
                reinterpret_perspective="beginner",
                confidence=0.7,
                reasoning="초보자 관점 요청"
            )
        
        if has_cache and any(word in user_message for word in ["더 자세히", "상세하게", "구체적"]):
            return DiagnosisIntentV2(
                execution_path="reinterpret",
                reinterpret_detail_level="detailed",
                confidence=0.7,
                reasoning="상세 설명 요청"
            )
        
        # force_refresh 감지
        force_refresh = detect_force_refresh(user_message)
        
        # 기본: Full Path
        return DiagnosisIntentV2(
            execution_path="full",
            analysis_depth="standard",
            force_refresh=force_refresh,
            confidence=0.6,
            reasoning="기본 전체 분석"
        )
