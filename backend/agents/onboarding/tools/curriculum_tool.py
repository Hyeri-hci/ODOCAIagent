"""
Tool B: Onboarding Curriculum Generator
N주 온보딩 커리큘럼을 마크다운으로 생성합니다.
"""

import logging
from typing import Dict, Any, List, Optional

from backend.agents.onboarding.models import OnboardingContext, ExperienceLevel
from backend.llm.kanana_wrapper import KananaWrapper

logger = logging.getLogger(__name__)


def generate_onboarding_curriculum(
    context: OnboardingContext,
    user_level: ExperienceLevel = "beginner",
    weeks: int = 4,
    time_budget: Optional[int] = None,
    variation_options: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    N주 온보딩 커리큘럼 생성 (Tool B)
    
    Args:
        context: OnboardingContext (docs, workflow, code map)
        user_level: 사용자 경험 수준 (beginner/intermediate/advanced)
        weeks: 커리큘럼 주차 수 (1-12)
        time_budget: 주당 투자 시간 (시간 단위, 선택)
        variation_options: 다양성 옵션 (재생성 시 다른 내용 생성을 위함)
    
    Returns:
        {
            "markdown": str,
            "metadata": {"weeks": int, "level": str},
            "source_files": List[str]
        }
    """
    logger.info(f"[Tool B] Generating {weeks}-week curriculum for {context['owner']}/{context['repo']}")
    
    if variation_options:
        logger.info(f"[Tool B] Variation options: {variation_options}")
    
    owner = context["owner"]
    repo = context["repo"]
    docs = context["docs_index"]
    code_map = context["code_map"]
    
    # 주차 수 제한
    weeks = max(1, min(weeks, 12))
    
    # 커리큘럼 생성 (다양성 옵션 전달)
    curriculum_weeks = _generate_weekly_plan(
        context=context,
        user_level=user_level,
        weeks=weeks,
        time_budget=time_budget,
        variation_options=variation_options
    )
    
    # 마크다운 조립
    sections: List[str] = []
    
    # 헤더
    sections.append(f"# {owner}/{repo} {weeks}주 온보딩 플랜\n")
    sections.append(f"> **경험 수준**: {_level_label(user_level)} | **기간**: {weeks}주")
    if time_budget:
        sections.append(f" | **주당 시간**: {time_budget}시간")
    sections.append("\n\n")
    
    # 개요
    sections.append(_build_overview_section(context, user_level))
    
    # 주차별 상세
    for week_data in curriculum_weeks:
        sections.append(_format_week_section(week_data, user_level))
    
    # 마무리
    sections.append(_build_completion_section(owner, repo))
    
    markdown = "".join(sections)
    
    # 근거 문서
    source_files: List[str] = []
    if docs.get("file_paths"):
        source_files.extend([p for p in docs["file_paths"].values() if p])
    
    return {
        "markdown": markdown,
        "curriculum_weeks": curriculum_weeks,  # plan 데이터 포함
        "metadata": {
            "weeks": weeks,
            "level": user_level,
            "time_budget": time_budget
        },
        "source_files": source_files
    }


def _level_label(level: ExperienceLevel) -> str:
    labels = {
        "beginner": "입문자",
        "intermediate": "중급자",
        "advanced": "숙련자"
    }
    return labels.get(level, "입문자")


def _generate_weekly_plan(
    context: OnboardingContext,
    user_level: ExperienceLevel,
    weeks: int,
    time_budget: Optional[int],
    variation_options: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """LLM을 사용하여 주차별 플랜 생성 (다양성 옵션 지원)"""
    
    # 기본 템플릿 기반 생성 (LLM 실패 시 fallback)
    curriculum = []
    
    code_map = context["code_map"]
    lang = code_map.get("language", "unknown")
    pm = code_map.get("package_manager")
    main_dirs = code_map.get("main_directories", [])
    
    # 다양성 옵션 추출
    focus_area = None
    preferred_style = None
    if variation_options:
        focus_area = variation_options.get("focus_area")
        preferred_style = variation_options.get("preferred_style")
        logger.info(f"[Curriculum] Using variation: focus={focus_area}, style={preferred_style}")
    
    # 난이도별 커리큘럼 템플릿 (다양성 옵션에 따라 변형)
    if user_level == "beginner":
        curriculum = _beginner_curriculum(context, weeks, focus_area, preferred_style)
    elif user_level == "intermediate":
        curriculum = _intermediate_curriculum(context, weeks, focus_area, preferred_style)
    else:
        curriculum = _advanced_curriculum(context, weeks, focus_area, preferred_style)
    
    return curriculum


# ===== 다양성을 위한 대안 템플릿 =====
ALTERNATIVE_WEEK1_TITLES = {
    "hands-on": "실습 중심 환경 구축",
    "theoretical": "프로젝트 철학과 아키텍처 이해",
    "project-based": "미니 프로젝트로 시작하기",
    "mentoring": "커뮤니티 참여와 환경 설정"
}

ALTERNATIVE_FOCUS_TASKS = {
    "code-review": ["기존 PR 리뷰 분석", "코드 리뷰 가이드라인 학습", "리뷰 코멘트 연습"],
    "documentation": ["문서 구조 파악", "README 개선점 찾기", "API 문서 분석"],
    "testing": ["테스트 커버리지 분석", "테스트 패턴 학습", "테스트 케이스 작성"],
    "feature-development": ["로드맵 분석", "기능 요청 이슈 탐색", "작은 기능 구현"],
    "bug-fixing": ["버그 이슈 분석", "재현 방법 학습", "디버깅 도구 활용"]
}


def _beginner_curriculum(
    context: OnboardingContext, 
    weeks: int,
    focus_area: Optional[str] = None,
    preferred_style: Optional[str] = None
) -> List[Dict[str, Any]]:
    """입문자용 커리큘럼 (다양성 옵션 지원)"""
    owner = context["owner"]
    repo = context["repo"]
    code_map = context["code_map"]
    workflow = context["workflow_hints"]
    
    # 다양성에 따른 1주차 타이틀 변경
    week1_title = ALTERNATIVE_WEEK1_TITLES.get(preferred_style, "환경 설정 및 프로젝트 탐색")
    
    # 포커스 영역에 따른 추가 태스크
    focus_tasks = ALTERNATIVE_FOCUS_TASKS.get(focus_area, [])
    
    base_curriculum = [
        {
            "week": 1,
            "title": week1_title,
            "goals": [
                "개발 환경 설정 완료",
                "프로젝트 구조 이해"
            ],
            "learning": [
                "Git/GitHub 기본 사용법",
                "프로젝트 README 정독",
                "폴더 구조 파악"
            ],
            "tasks": [
                f"저장소 Fork 및 Clone",
                f"의존성 설치 (`{code_map.get('package_manager', 'npm/pip')} install`)",
                "프로젝트 실행 테스트",
                "주요 디렉토리 탐색"
            ] + (focus_tasks[:1] if focus_tasks else []),
            "checklist": [
                "로컬에서 프로젝트 실행 성공",
                "README.md 읽기 완료",
                "주요 파일 5개 이상 확인"
            ]
        },
        {
            "week": 2,
            "title": "문서 기여로 첫 PR" if not focus_area else f"{focus_area.replace('-', ' ').title()} 중심 첫 기여",
            "goals": [
                "GitHub PR 워크플로우 이해",
                "첫 PR 작성"
            ],
            "learning": [
                "CONTRIBUTING.md 숙지",
                "PR 작성 방법",
                "코드 리뷰 프로세스"
            ],
            "tasks": [
                "good first issue 탐색",
                "문서 오타/개선점 찾기" if not focus_area else focus_tasks[1] if len(focus_tasks) > 1 else "개선점 찾기",
                "브랜치 생성 및 수정",
                "PR 작성 및 제출"
            ],
            "checklist": [
                "브랜치 생성 성공",
                "커밋 메시지 작성",
                "PR 제출 완료"
            ]
        },
        {
            "week": 3,
            "title": "코드 구조 심화 학습",
            "goals": [
                "핵심 모듈 이해",
                "테스트 실행 방법 습득"
            ],
            "learning": [
                f"주요 디렉토리: {', '.join(code_map.get('main_directories', ['src/', 'lib/'])[:3])}",
                "테스트 코드 구조",
                "디버깅 기초"
            ],
            "tasks": [
                "핵심 모듈 3개 코드 읽기",
                f"테스트 실행 (`{workflow.get('test_command', 'npm test')}`)",
                "간단한 테스트 케이스 작성 시도"
            ] + (focus_tasks[2:3] if len(focus_tasks) > 2 else []),
            "checklist": [
                "테스트 전체 통과",
                "모듈 의존 관계 파악",
                "함수 흐름 이해"
            ]
        },
        {
            "week": 4,
            "title": "간단한 버그 수정" if focus_area != "feature-development" else "작은 기능 구현",
            "goals": [
                "이슈 기반 기여 경험",
                "코드 리뷰 피드백 반영"
            ],
            "learning": [
                "이슈 트래커 사용법",
                "버그 재현 및 디버깅" if focus_area != "feature-development" else "기능 설계 및 구현",
                "리뷰 피드백 대응"
            ],
            "tasks": [
                "간단한 버그 이슈 선택" if focus_area != "feature-development" else "작은 기능 이슈 선택",
                "버그 재현 및 원인 분석" if focus_area != "feature-development" else "기능 설계 및 구현",
                "수정 코드 작성",
                "테스트 추가 후 PR 제출"
            ],
            "checklist": [
                "버그 재현 성공" if focus_area != "feature-development" else "기능 동작 확인",
                "수정 후 테스트 통과",
                "PR 머지 or 피드백 반영"
            ]
        }
    ]
    
    # 요청된 주차 수에 맞게 조정
    if weeks <= len(base_curriculum):
        return base_curriculum[:weeks]
    else:
        # 추가 주차 생성
        result = base_curriculum.copy()
        for i in range(len(base_curriculum) + 1, weeks + 1):
            result.append({
                "week": i,
                "title": f"{i}주차: 지속적 기여",
                "goals": ["이전 주차 심화", "새로운 이슈 도전"],
                "learning": ["코드베이스 심화 이해", "복잡한 이슈 분석"],
                "tasks": ["이슈 선택 및 분석", "구현 및 테스트", "PR 제출"],
                "checklist": ["이슈 완료", "테스트 통과", "PR 리뷰 완료"]
            })
        return result


def _intermediate_curriculum(
    context: OnboardingContext, 
    weeks: int,
    focus_area: Optional[str] = None,
    preferred_style: Optional[str] = None
) -> List[Dict[str, Any]]:
    """중급자용 커리큘럼 (다양성 옵션 지원)"""
    owner = context["owner"]
    repo = context["repo"]
    code_map = context["code_map"]
    workflow = context["workflow_hints"]
    
    # 포커스 영역에 따른 2주차 타이틀 변경
    week2_titles = {
        "code-review": "코드 리뷰 심화",
        "documentation": "기술 문서 작성",
        "testing": "테스트 인프라 개선",
        "feature-development": "핵심 기능 개발",
        "bug-fixing": "복잡한 버그 추적"
    }
    
    base_curriculum = [
        {
            "week": 1,
            "title": "아키텍처 분석",
            "goals": ["전체 아키텍처 이해", "핵심 모듈 파악"],
            "learning": ["설계 패턴 분석", "의존성 그래프 파악", "데이터 흐름 이해"],
            "tasks": [
                "아키텍처 문서 분석",
                "핵심 모듈 코드 리뷰",
                "의존성 다이어그램 작성"
            ],
            "checklist": ["아키텍처 개요 정리", "핵심 모듈 3개 이상 분석", "질문 목록 작성"]
        },
        {
            "week": 2,
            "title": week2_titles.get(focus_area, "기능 개선 기여"),
            "goals": ["enhancement 이슈 해결", "코드 품질 개선"],
            "learning": ["기능 요구사항 분석", "기존 코드 확장", "테스트 커버리지"],
            "tasks": [
                "enhancement 라벨 이슈 선택",
                "설계 문서 작성",
                "구현 및 테스트",
                "PR 제출"
            ],
            "checklist": ["설계 리뷰 완료", "테스트 커버리지 유지", "PR 승인"]
        },
        {
            "week": 3,
            "title": "성능 최적화" if focus_area != "testing" else "테스트 커버리지 확대",
            "goals": ["성능 병목 분석", "최적화 기법 적용"] if focus_area != "testing" else ["테스트 커버리지 향상", "엣지 케이스 처리"],
            "learning": ["프로파일링 도구", "알고리즘 최적화", "메모리 관리"] if focus_area != "testing" else ["테스트 전략", "목킹/스터빙", "통합 테스트"],
            "tasks": [
                "성능 벤치마크 실행" if focus_area != "testing" else "커버리지 리포트 분석",
                "병목 지점 분석" if focus_area != "testing" else "미커버 영역 파악",
                "최적화 코드 작성" if focus_area != "testing" else "테스트 케이스 추가",
                "벤치마크 비교" if focus_area != "testing" else "커버리지 비교"
            ],
            "checklist": ["벤치마크 결과 문서화", "성능 개선 수치화", "리그레션 없음 확인"] if focus_area != "testing" else ["커버리지 5% 향상", "테스트 문서화", "CI 통과"]
        },
        {
            "week": 4,
            "title": "코드 리뷰어로 참여",
            "goals": ["다른 PR 리뷰", "커뮤니티 기여"],
            "learning": ["효과적인 코드 리뷰", "건설적 피드백", "프로젝트 가이드라인"],
            "tasks": [
                "최근 PR 3개 이상 리뷰",
                "건설적인 피드백 작성",
                "이슈 트리아지 참여"
            ],
            "checklist": ["리뷰 3개 이상 완료", "피드백 반영 확인", "메인테이너 인정"]
        }
    ]
    
    # 요청된 주차 수에 맞게 조정
    if weeks <= len(base_curriculum):
        return base_curriculum[:weeks]
    else:
        result = base_curriculum.copy()
        for i in range(len(base_curriculum) + 1, weeks + 1):
            result.append({
                "week": i,
                "title": f"{i}주차: 심화 기여",
                "goals": ["복잡한 기능 구현", "아키텍처 개선"],
                "learning": ["심화 패턴", "확장성 고려"],
                "tasks": ["복잡한 이슈 선택", "설계 및 구현", "PR 제출"],
                "checklist": ["기능 완료", "테스트 통과", "문서화 완료"]
            })
        return result


def _advanced_curriculum(
    context: OnboardingContext, 
    weeks: int,
    focus_area: Optional[str] = None,
    preferred_style: Optional[str] = None
) -> List[Dict[str, Any]]:
    """숙련자용 커리큘럼 (핵심 기여자 트랙, 다양성 옵션 지원)"""
    
    base_curriculum = [
        {
            "week": 1,
            "title": "핵심 아키텍처 분석",
            "goals": ["전체 시스템 이해", "확장 포인트 파악"],
            "learning": ["설계 원칙", "확장성 패턴", "성능 특성"],
            "tasks": [
                "핵심 모듈 전체 코드 리뷰",
                "아키텍처 개선 제안서 작성",
                "메인테이너와 논의"
            ],
            "checklist": ["아키텍처 문서 기여", "개선안 피드백", "로드맵 파악"]
        },
        {
            "week": 2,
            "title": "핵심 기능 구현",
            "goals": ["major feature 구현", "설계 리드"],
            "learning": ["RFC 프로세스", "대규모 변경 관리", "하위 호환성"],
            "tasks": [
                "RFC/설계 문서 작성",
                "POC 구현",
                "커뮤니티 피드백 수렴",
                "구현 및 테스트"
            ],
            "checklist": ["RFC 승인", "구현 완료", "문서화 완료"]
        },
        {
            "week": 3,
            "title": "보안 및 안정성",
            "goals": ["보안 취약점 분석", "안정성 개선"],
            "learning": ["보안 코드 리뷰", "취약점 패턴", "안전한 코딩"],
            "tasks": [
                "보안 감사 수행",
                "취약점 수정",
                "보안 가이드 작성"
            ],
            "checklist": ["취약점 0개", "보안 문서 기여", "CI 보안 체크 추가"]
        },
        {
            "week": 4,
            "title": "커뮤니티 리더십",
            "goals": ["새 기여자 멘토링", "프로젝트 방향 참여"],
            "learning": ["오픈소스 거버넌스", "멘토링 기술", "커뮤니티 빌딩"],
            "tasks": [
                "신규 기여자 3명 멘토링",
                "릴리즈 프로세스 참여",
                "로드맵 논의 참여"
            ],
            "checklist": ["멘티 PR 머지 지원", "릴리즈 기여", "메인테이너 인정"]
        }
    ]
    
    if weeks <= len(base_curriculum):
        return base_curriculum[:weeks]
    else:
        result = base_curriculum.copy()
        for i in range(len(base_curriculum) + 1, weeks + 1):
            result.append({
                "week": i,
                "title": f"{i}주차: 핵심 기여자 활동",
                "goals": ["지속적 핵심 기여", "프로젝트 성장 기여"],
                "learning": ["심화 주제", "리더십"],
                "tasks": ["핵심 이슈 해결", "커뮤니티 지원"],
                "checklist": ["기여 완료", "커뮤니티 활동"]
            })
        return result


def _build_overview_section(context: OnboardingContext, level: ExperienceLevel) -> str:
    """개요 섹션 생성"""
    code_map = context["code_map"]
    
    section = "## 개요\n\n"
    section += f"| 항목 | 내용 |\n"
    section += f"|------|------|\n"
    section += f"| 주 언어 | {code_map.get('language', 'N/A')} |\n"
    section += f"| 패키지 매니저 | {code_map.get('package_manager', 'N/A')} |\n"
    
    dirs = code_map.get("main_directories", [])
    if dirs:
        section += f"| 주요 디렉토리 | {', '.join(dirs[:3])} |\n"
    
    section += "\n"
    return section


def _format_week_section(week_data: Dict[str, Any], level: ExperienceLevel) -> str:
    """주차별 섹션 포맷"""
    week_num = week_data["week"]
    title = week_data["title"]
    
    section = f"## {week_num}주차: {title}\n\n"
    
    # 목표
    section += "### 목표\n"
    for goal in week_data.get("goals", []):
        section += f"- {goal}\n"
    section += "\n"
    
    # 학습 내용
    section += "### 학습 내용\n"
    for item in week_data.get("learning", []):
        section += f"- {item}\n"
    section += "\n"
    
    # 실습 과제
    section += "### 실습 과제\n"
    for task in week_data.get("tasks", []):
        section += f"- [ ] {task}\n"
    section += "\n"
    
    # 체크리스트
    section += "### 검증 체크리스트\n"
    for item in week_data.get("checklist", []):
        section += f"- [ ] {item}\n"
    section += "\n---\n\n"
    
    return section


def _build_completion_section(owner: str, repo: str) -> str:
    """마무리 섹션"""
    section = "## 완료 후 다음 단계\n\n"
    section += f"축하합니다! {owner}/{repo} 온보딩 플랜을 완료했습니다.\n\n"
    section += "### 추천 다음 단계\n"
    section += "- [ ] 더 복잡한 이슈에 도전\n"
    section += "- [ ] 새로운 기여자 멘토링\n"
    section += "- [ ] 프로젝트 로드맵 논의 참여\n"
    section += "- [ ] 블로그/발표로 경험 공유\n"
    
    return section
