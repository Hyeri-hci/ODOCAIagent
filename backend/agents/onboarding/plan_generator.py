"""
단일 저장소에 대한 온보딩 플랜 생성기
진단 결과를 기반으로 초보자 친화적인 단계별 가이드 생성
"""
from __future__ import annotations

import logging
import asyncio
from typing import Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class OnboardingPlanGenerator:
    def __init__(self):
        from backend.llm.factory import fetch_llm_client
        self.llm = fetch_llm_client()
    
    async def generate(
        self,
        owner: str,
        repo: str,
        diagnosis_result: dict[str, Any],
        user_level: str = "beginner",
        target_language: str = "ko",
        include_llm_guide: bool = True
    ) -> dict[str, Any]:
        logger.info(f"Generating onboarding plan for {owner}/{repo} (level: {user_level})")
        
        # 진단 결과에서 정보 추출
        scores = diagnosis_result.get("scores", {})
        labels = diagnosis_result.get("labels", {})
        stack_info = diagnosis_result.get("stack_info", {})
        structure = diagnosis_result.get("structure", {})
        
        # 난이도 결정
        onboarding_score = scores.get("onboarding_score", 50)
        difficulty = self._determine_difficulty(onboarding_score, user_level)
        
        # 예상 시간 계산
        estimated_hours = self._estimate_hours(difficulty, user_level)
        
        # 기본 단계 생성
        steps = self._generate_basic_steps(
            owner=owner,
            repo=repo,
            difficulty=difficulty,
            stack_info=stack_info,
            structure=structure,
            user_level=user_level
        )
        
        # LLM 기반 상세 가이드 추가
        if include_llm_guide:
            try:
                enhanced_steps = await self._enhance_with_llm(
                    owner=owner,
                    repo=repo,
                    basic_steps=steps,
                    diagnosis_result=diagnosis_result,
                    user_level=user_level,
                    target_language=target_language
                )
                steps = enhanced_steps
            except Exception as e:
                logger.warning(f"LLM enhancement failed, using basic steps: {e}")
        
        # 플랜 조립
        plan = {
            "plan_id": f"onboarding_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "repo": f"{owner}/{repo}",
            "difficulty": difficulty,
            "user_level": user_level,
            "estimated_hours": estimated_hours,
            "total_steps": len(steps),
            "steps": steps,
            "prerequisites": self._generate_prerequisites(stack_info),
            "recommended_first_issues": self._extract_good_first_issues(diagnosis_result),
            "created_at": datetime.now().isoformat()
        }
        
        logger.info(f"Onboarding plan generated: {len(steps)} steps, ~{estimated_hours}h")
        return plan
    
    def _determine_difficulty(self, onboarding_score: int, user_level: str) -> str:
        """난이도 결정"""
        if user_level == "advanced":
            return "easy" if onboarding_score > 60 else "normal"
        elif user_level == "intermediate":
            if onboarding_score > 70:
                return "easy"
            elif onboarding_score > 40:
                return "normal"
            else:
                return "hard"
        else:  # beginner
            if onboarding_score > 80:
                return "easy"
            elif onboarding_score > 50:
                return "normal"
            else:
                return "hard"
    
    def _estimate_hours(self, difficulty: str, user_level: str) -> int:
        """예상 소요 시간 계산"""
        base_hours = {
            "easy": 5,
            "normal": 10,
            "hard": 20
        }
        
        multiplier = {
            "beginner": 1.5,
            "intermediate": 1.0,
            "advanced": 0.7
        }
        
        hours = base_hours.get(difficulty, 10) * multiplier.get(user_level, 1.0)
        return int(hours)
    
    def _generate_basic_steps(
        self,
        owner: str,
        repo: str,
        difficulty: str,
        stack_info: dict[str, Any],
        structure: dict[str, Any],
        user_level: str
    ) -> list[dict[str, Any]]:
        """기본 온보딩 단계 생성 (규칙 기반)"""
        
        steps = []
        step_num = 1
        
        # Step 1: 저장소 Fork & Clone
        steps.append({
            "step_number": step_num,
            "title": "저장소 복사 및 로컬 환경 설정",
            "description": f"{owner}/{repo} 저장소를 자신의 계정으로 Fork한 후 로컬에 Clone합니다.",
            "tasks": [
                f"GitHub에서 {owner}/{repo} 저장소를 Fork",
                "Fork한 저장소를 로컬에 Clone",
                "원본 저장소를 upstream으로 추가"
            ],
            "commands": [
                f"git clone https://github.com/YOUR_USERNAME/{repo}.git",
                f"cd {repo}",
                f"git remote add upstream https://github.com/{owner}/{repo}.git"
            ],
            "estimated_time": "30분",
            "difficulty": "easy"
        })
        step_num += 1
        
        # Step 2: 개발 환경 설정
        primary_language = stack_info.get("primary_language", "Unknown")
        setup_guide = self._get_setup_guide(primary_language, structure)
        
        steps.append({
            "step_number": step_num,
            "title": "개발 환경 설정",
            "description": f"{primary_language} 개발 환경을 설정하고 의존성을 설치합니다.",
            "tasks": setup_guide.get("tasks", []),
            "commands": setup_guide.get("commands", []),
            "estimated_time": "1-2시간",
            "difficulty": "normal" if user_level == "beginner" else "easy"
        })
        step_num += 1
        
        # Step 3: 코드베이스 탐색
        steps.append({
            "step_number": step_num,
            "title": "코드베이스 구조 파악",
            "description": "프로젝트의 주요 디렉토리와 파일 구조를 이해합니다.",
            "tasks": [
                "README.md 읽기",
                "CONTRIBUTING.md 확인 (있다면)",
                "주요 디렉토리 구조 파악",
                "테스트 코드 위치 확인"
            ],
            "estimated_time": "1-2시간",
            "difficulty": "easy"
        })
        step_num += 1
        
        # Step 4: 첫 번째 이슈 찾기
        steps.append({
            "step_number": step_num,
            "title": "첫 기여 이슈 찾기",
            "description": "초보자에게 적합한 이슈를 찾아 작업을 시작합니다.",
            "tasks": [
                "'good first issue' 라벨이 있는 이슈 검색",
                "이슈 내용 및 요구사항 파악",
                "이슈에 댓글로 작업 의사 표시",
                "필요시 질문하기"
            ],
            "estimated_time": "30분-1시간",
            "difficulty": "easy"
        })
        step_num += 1
        
        # Step 5: 브랜치 생성 및 작업
        steps.append({
            "step_number": step_num,
            "title": "작업 브랜치 생성 및 코드 수정",
            "description": "새 브랜치를 만들고 이슈를 해결하기 위한 코드를 작성합니다.",
            "tasks": [
                "작업용 브랜치 생성 (예: fix-issue-123)",
                "코드 수정",
                "로컬에서 테스트 실행",
                "변경사항 커밋"
            ],
            "commands": [
                "git checkout -b fix-issue-123",
                "# 코드 수정...",
                "git add .",
                "git commit -m 'Fix: 이슈 설명'"
            ],
            "estimated_time": "2-4시간",
            "difficulty": difficulty
        })
        step_num += 1
        
        # Step 6: PR 생성
        steps.append({
            "step_number": step_num,
            "title": "Pull Request 생성",
            "description": "작업한 내용을 원본 저장소에 Pull Request로 제출합니다.",
            "tasks": [
                "변경사항을 Fork한 저장소에 Push",
                "GitHub에서 Pull Request 생성",
                "PR 템플릿에 맞춰 설명 작성",
                "리뷰 대기 및 피드백 반영"
            ],
            "commands": [
                "git push origin fix-issue-123"
            ],
            "estimated_time": "30분-1시간",
            "difficulty": "normal"
        })
        
        return steps
    
    def _get_setup_guide(
        self,
        language: str,
        structure: dict[str, Any]
    ) -> dict[str, Any]:
        """언어별 설정 가이드"""
        
        guides = {
            "Python": {
                "tasks": [
                    "Python 3.8+ 설치 확인",
                    "가상환경 생성 및 활성화",
                    "requirements.txt 또는 pyproject.toml로 의존성 설치",
                    "테스트 실행하여 환경 검증"
                ],
                "commands": [
                    "python --version",
                    "python -m venv venv",
                    "source venv/bin/activate  # Windows: venv\\Scripts\\activate",
                    "pip install -r requirements.txt",
                    "pytest  # 또는 python -m unittest"
                ]
            },
            "JavaScript": {
                "tasks": [
                    "Node.js 및 npm 설치 확인",
                    "package.json으로 의존성 설치",
                    "테스트 실행하여 환경 검증"
                ],
                "commands": [
                    "node --version",
                    "npm --version",
                    "npm install",
                    "npm test"
                ]
            },
            "TypeScript": {
                "tasks": [
                    "Node.js 및 npm 설치 확인",
                    "package.json으로 의존성 설치",
                    "TypeScript 컴파일 확인",
                    "테스트 실행"
                ],
                "commands": [
                    "node --version",
                    "npm install",
                    "npm run build",
                    "npm test"
                ]
            },
            "Java": {
                "tasks": [
                    "JDK 설치 확인",
                    "Maven 또는 Gradle 설치 확인",
                    "의존성 다운로드 및 빌드",
                    "테스트 실행"
                ],
                "commands": [
                    "java -version",
                    "mvn --version  # 또는 gradle --version",
                    "mvn clean install  # 또는 gradle build",
                    "mvn test  # 또는 gradle test"
                ]
            }
        }
        
        return guides.get(language, {
            "tasks": [
                f"{language} 개발 환경 설정",
                "의존성 설치",
                "빌드 및 테스트 실행"
            ],
            "commands": [
                "# 프로젝트의 README.md를 참고하세요"
            ]
        })
    
    def _generate_prerequisites(self, stack_info: dict[str, Any]) -> list[str]:
        """필요한 사전 지식/도구"""
        prereqs = [
            "Git 기본 사용법",
            "GitHub 계정",
            "터미널/커맨드라인 사용법"
        ]
        
        primary_language = stack_info.get("primary_language")
        if primary_language:
            prereqs.append(f"{primary_language} 기본 문법")
        
        frameworks = stack_info.get("frameworks", [])
        if frameworks:
            prereqs.append(f"다음 중 하나 이상: {', '.join(frameworks[:3])}")
        
        return prereqs
    
    def _extract_good_first_issues(self, diagnosis_result: dict[str, Any]) -> list[str]:
        """Good First Issue 추출"""
        # TODO: GitHub API를 통해 실제 이슈 가져오기
        # 현재는 placeholder
        return [
            "GitHub Issues에서 'good first issue' 라벨 검색",
            "최근 1달 이내 생성된 이슈 우선 확인",
            "코멘트가 많지 않은 이슈 선택"
        ]
    
    async def _enhance_with_llm(
        self,
        owner: str,
        repo: str,
        basic_steps: list[dict[str, Any]],
        diagnosis_result: dict[str, Any],
        user_level: str,
        target_language: str
    ) -> list[dict[str, Any]]:
        """LLM을 사용하여 단계별 가이드 보강"""
        
        from backend.llm.base import ChatRequest, ChatMessage
        
        # 진단 결과 요약
        scores = diagnosis_result.get("scores", {})
        summary = f"""
저장소: {owner}/{repo}
건강도: {scores.get('health_score', 0)}/100
문서 품질: {scores.get('docs_score', 0)}/100
온보딩 점수: {scores.get('onboarding_score', 0)}/100
주요 언어: {diagnosis_result.get('stack_info', {}).get('primary_language', 'Unknown')}
"""
        
        prompt = f"""당신은 오픈소스 기여 온보딩 전문가입니다.

다음 저장소에 대한 온보딩 플랜의 각 단계에 초보자 친화적인 팁과 주의사항을 추가해주세요.

=== 저장소 정보 ===
{summary}

=== 사용자 레벨 ===
{user_level}

=== 기본 단계 (총 {len(basic_steps)}개) ===
{self._format_steps_for_llm(basic_steps)}

=== 요구사항 ===
각 단계에 다음을 추가해주세요:
1. "tips": 초보자를 위한 실용적인 팁 (2-3개)
2. "common_pitfalls": 흔히 겪는 실수와 해결 방법 (1-2개)
3. "resources": 참고할 만한 자료 링크나 키워드 (선택사항)

JSON 형식으로 응답하세요. 각 단계는 기존 정보를 유지하면서 위 3개 필드만 추가합니다.
응답 형식: {{"steps": [...]}}
"""
        
        loop = asyncio.get_event_loop()
        
        request = ChatRequest(
            messages=[
                ChatMessage(role="user", content=prompt)
            ],
            temperature=0.7,
            max_tokens=3000
        )
        
        try:
            response = await loop.run_in_executor(
                None,
                self.llm.chat,
                request
            )
            
            # JSON 파싱
            import json
            response_text = response.content.strip()
            
            # 마크다운 코드 블록 제거
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
            
            enhanced_data = json.loads(response_text)
            enhanced_steps = enhanced_data.get("steps", [])
            
            # 기본 단계와 병합
            for i, step in enumerate(basic_steps):
                if i < len(enhanced_steps):
                    enhanced = enhanced_steps[i]
                    step["tips"] = enhanced.get("tips", [])
                    step["common_pitfalls"] = enhanced.get("common_pitfalls", [])
                    step["resources"] = enhanced.get("resources", [])
            
            return basic_steps
        
        except Exception as e:
            logger.error(f"LLM enhancement failed: {e}", exc_info=True)
            return basic_steps
    
    def _format_steps_for_llm(self, steps: list[dict[str, Any]]) -> str:
        """LLM에게 전달할 단계 포맷팅"""
        formatted = []
        for step in steps:
            formatted.append(f"""
Step {step['step_number']}: {step['title']}
- 설명: {step['description']}
- 예상 시간: {step['estimated_time']}
- 난이도: {step['difficulty']}
""")
        return "\n".join(formatted)


# 편의 함수

async def generate_onboarding_plan(
    owner: str,
    repo: str,
    diagnosis_result: dict[str, Any],
    user_level: str = "beginner",
    target_language: str = "ko"
) -> dict[str, Any]:
    """온보딩 플랜 생성 (편의 함수)"""
    generator = OnboardingPlanGenerator()
    return await generator.generate(
        owner=owner,
        repo=repo,
        diagnosis_result=diagnosis_result,
        user_level=user_level,
        target_language=target_language
    )
