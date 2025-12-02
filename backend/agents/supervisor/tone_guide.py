"""Korean Tone & Prompt Guidelines (Step 9): Fast vs Expert mode consistency."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional


class PromptMode(str, Enum):
    """LLM prompt mode."""
    FAST = "fast"      # 경량 경로: 공손·간결, 불릿 ≤ 3
    EXPERT = "expert"  # 전문가 경로: 건조·정확, 잡담 금지


@dataclass
class ToneConfig:
    """Tone configuration for a mode."""
    temperature: float
    max_tokens: int
    top_p: float
    max_bullets: int           # 최대 불릿 포인트 수
    max_sentences: int         # 최대 문장 수
    next_actions: int          # "다음 행동" 제안 수
    allow_chitchat: bool       # 잡담 허용 여부
    formal_level: str          # "polite" (존댓말) | "neutral"


# Mode별 톤 설정
TONE_CONFIGS: Dict[PromptMode, ToneConfig] = {
    PromptMode.FAST: ToneConfig(
        temperature=0.7,
        max_tokens=300,
        top_p=0.9,
        max_bullets=3,
        max_sentences=5,
        next_actions=2,
        allow_chitchat=True,
        formal_level="polite",
    ),
    PromptMode.EXPERT: ToneConfig(
        temperature=0.25,
        max_tokens=1024,
        top_p=0.9,
        max_bullets=7,
        max_sentences=15,
        next_actions=3,
        allow_chitchat=False,
        formal_level="polite",
    ),
}


# Intent → Mode 매핑
INTENT_MODE_MAP: Dict[str, PromptMode] = {
    # Fast mode: 경량, 빠른 응답
    "smalltalk": PromptMode.FAST,
    "help": PromptMode.FAST,
    "general_qa": PromptMode.FAST,
    "overview": PromptMode.FAST,
    
    # Expert mode: 정밀, 데이터 기반
    "analyze": PromptMode.EXPERT,
    "compare": PromptMode.EXPERT,
    "followup": PromptMode.EXPERT,
    "recommendation": PromptMode.EXPERT,
}


def get_mode_for_intent(intent: str) -> PromptMode:
    """Returns prompt mode for intent."""
    return INTENT_MODE_MAP.get(intent, PromptMode.FAST)


def get_tone_config(mode: PromptMode) -> ToneConfig:
    """Returns tone config for mode."""
    return TONE_CONFIGS.get(mode, TONE_CONFIGS[PromptMode.FAST])


def get_tone_config_for_intent(intent: str) -> ToneConfig:
    """Returns tone config for intent."""
    mode = get_mode_for_intent(intent)
    return get_tone_config(mode)


# 한국어 톤 가이드 프롬프트

TONE_GUIDE_FAST = """## 톤 가이드 (Fast Mode)

### 스타일
- **공손하고 간결하게** 응답합니다
- 존댓말 사용: ~입니다, ~해요
- 불릿 포인트는 최대 3개
- 문장은 5개 이내

### 구조
1. 핵심 답변 (1-2문장)
2. 선택적 설명 (필요시)
3. 다음 행동 2개 제안

### 금지 사항
- 이모지 사용 금지
- 과도한 기술 용어 금지
- 장황한 설명 금지

### 예시
```
네, 도와드릴게요!

저장소를 분석하려면 URL을 알려주세요.

**다음 행동**
- `facebook/react 분석해줘`
- `사용법 알려줘`
```
"""

TONE_GUIDE_EXPERT = """## 톤 가이드 (Expert Mode)

### 스타일
- **건조하고 정확하게** 응답합니다
- 존댓말 사용: ~입니다, ~합니다
- 데이터 기반 설명만 제공
- 잡담 및 인사 금지

### 구조
1. 결과 요약 (표 또는 숫자)
2. 핵심 분석 (데이터 인용)
3. 다음 행동 2-3개 제안

### 금지 사항
- 이모지 사용 금지
- 추측 금지 (데이터 없으면 "정보 없음")
- 불필요한 인사/잡담 금지
- "~인 것 같습니다" 등 애매한 표현 금지

### AnswerContract 준수
- 모든 응답에 sources 명시
- 데이터 출처 명확히 표기

### 예시
```
### 분석 결과

| 지표 | 점수 | 상태 |
|------|------|------|
| 건강 점수 | 78 | 양호 |
| 문서화 품질 | 65 | 보통 |

**분석**: 활동성(85점)이 높으나 문서화(65점)가 상대적으로 부족합니다.

**다음 행동**
- `점수 자세히 설명해줘`
- `비슷한 저장소와 비교해줘`
```
"""


# 시스템 프롬프트 빌더

def build_system_prompt_prefix(mode: PromptMode) -> str:
    """Builds system prompt prefix with tone guide."""
    config = get_tone_config(mode)
    guide = TONE_GUIDE_FAST if mode == PromptMode.FAST else TONE_GUIDE_EXPERT
    
    return f"""# 시스템 설정

{guide}

## 파라미터
- 최대 토큰: {config.max_tokens}
- 불릿 상한: {config.max_bullets}개
- 문장 상한: {config.max_sentences}문장
- 다음 행동: {config.next_actions}개

"""


def get_llm_params_for_mode(mode: PromptMode) -> Dict[str, float]:
    """Returns LLM parameters for mode."""
    config = get_tone_config(mode)
    return {
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
        "top_p": config.top_p,
    }


def get_llm_params_for_intent(intent: str) -> Dict[str, float]:
    """Returns LLM parameters for intent."""
    mode = get_mode_for_intent(intent)
    return get_llm_params_for_mode(mode)


# 길이 검증

def validate_response_length(
    text: str,
    mode: PromptMode,
) -> tuple[bool, Optional[str]]:
    """
    Validates response length against tone config.
    
    Returns (is_valid, warning_message).
    """
    config = get_tone_config(mode)
    
    # 문장 수 체크
    sentences = [s.strip() for s in text.split('.') if s.strip()]
    if len(sentences) > config.max_sentences * 1.5:
        return False, f"문장이 너무 많습니다 ({len(sentences)}문장, 상한 {config.max_sentences})"
    
    # 불릿 수 체크
    bullets = text.count('\n- ') + text.count('\n* ')
    if bullets > config.max_bullets * 2:
        return False, f"불릿이 너무 많습니다 ({bullets}개, 상한 {config.max_bullets})"
    
    # 토큰 추정 (한글: ~2자/토큰)
    estimated_tokens = len(text) / 2
    if estimated_tokens > config.max_tokens * 1.2:
        return False, f"응답이 너무 깁니다 (추정 {int(estimated_tokens)} 토큰)"
    
    return True, None


def truncate_response(
    text: str,
    mode: PromptMode,
    add_truncation_notice: bool = True,
) -> str:
    """Truncates response to fit within token limits."""
    config = get_tone_config(mode)
    max_chars = config.max_tokens * 2  # 한글 추정
    
    if len(text) <= max_chars:
        return text
    
    truncated = text[:max_chars]
    
    # 문장 단위로 자르기
    last_period = max(
        truncated.rfind('.'),
        truncated.rfind('요'),
        truncated.rfind('다'),
    )
    
    if last_period > max_chars * 0.7:
        truncated = truncated[:last_period + 1]
    
    if add_truncation_notice:
        truncated += "\n\n(응답이 길어 일부 생략되었습니다.)"
    
    return truncated


# 톤 체크리스트 (테스트용)

TONE_CHECKLIST = {
    PromptMode.FAST: [
        ("존댓말 사용", lambda t: "입니다" in t or "해요" in t or "습니다" in t),
        ("이모지 없음", lambda t: not any(ord(c) > 127000 for c in t)),
        ("불릿 3개 이하", lambda t: t.count('\n- ') + t.count('\n* ') <= 3),
        ("다음 행동 포함", lambda t: "다음 행동" in t or "다음" in t.lower()),
    ],
    PromptMode.EXPERT: [
        ("존댓말 사용", lambda t: "입니다" in t or "합니다" in t),
        ("이모지 없음", lambda t: not any(ord(c) > 127000 for c in t)),
        ("데이터 인용", lambda t: any(c in t for c in ["점", "%", "개", "건"])),
        ("추측 표현 없음", lambda t: "것 같" not in t and "아마" not in t),
    ],
}


def check_tone_compliance(text: str, mode: PromptMode) -> Dict[str, bool]:
    """Checks if text complies with tone guidelines."""
    checklist = TONE_CHECKLIST.get(mode, [])
    results = {}
    
    for name, check_fn in checklist:
        try:
            results[name] = check_fn(text)
        except Exception:
            results[name] = False
    
    return results


def is_tone_compliant(text: str, mode: PromptMode) -> bool:
    """Returns True if text passes all tone checks."""
    results = check_tone_compliance(text, mode)
    return all(results.values())
