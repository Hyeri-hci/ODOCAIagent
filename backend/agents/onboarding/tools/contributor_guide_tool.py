"""
Tool A: Contributor Guide Generator
Fork → Clone → Branch → Commit → Test/Build → PR 단계별 기여 가이드를 마크다운으로 생성합니다.
"""

import logging
from typing import Dict, Any, List, Optional

from backend.agents.onboarding.models import OnboardingContext, UserGoal

logger = logging.getLogger(__name__)


def generate_contributor_guide(
    context: OnboardingContext,
    user_goal: UserGoal = "first_pr"
) -> Dict[str, Any]:
    """
    기여 가이드 마크다운 생성 (Tool A)
    
    Args:
        context: OnboardingContext (docs, workflow, code map)
        user_goal: 사용자 목표 (first_pr, docs, bugfix, feature)
    
    Returns:
        {
            "markdown": str,
            "metadata": {"sections": int, "steps": int},
            "source_files": List[str]
        }
    """
    logger.info(f"[Tool A] Generating contributor guide for {context['owner']}/{context['repo']}")
    
    owner = context["owner"]
    repo = context["repo"]
    docs = context["docs_index"]
    workflow = context["workflow_hints"]
    code_map = context["code_map"]
    
    source_files: List[str] = []
    sections: List[str] = []
    total_steps = 0
    
    # 헤더
    sections.append(f"# {owner}/{repo} 기여 가이드\n")
    sections.append(f"> 이 가이드는 **{_goal_description(user_goal)}**을 목표로 합니다.\n\n")
    
    # 1. 사전 준비
    section, steps = _build_prerequisites_section(context)
    sections.append(section)
    total_steps += steps
    
    # 2. Fork & Clone
    section, steps = _build_fork_clone_section(owner, repo, workflow)
    sections.append(section)
    total_steps += steps
    
    # 3. Branch 생성
    section, steps = _build_branch_section(workflow)
    sections.append(section)
    total_steps += steps
    
    # 4. 코드 수정 & 커밋
    section, steps = _build_commit_section(workflow, user_goal)
    sections.append(section)
    total_steps += steps
    
    # 5. 테스트 & 빌드
    section, steps = _build_test_build_section(workflow, code_map)
    sections.append(section)
    total_steps += steps
    
    # 6. PR 생성
    section, steps = _build_pr_section(owner, repo, docs)
    sections.append(section)
    total_steps += steps
    
    # 7. 프로젝트 규칙
    section, files = _build_project_rules_section(docs, workflow)
    sections.append(section)
    source_files.extend(files)
    
    # 8. 초보자 체크리스트
    section = _build_checklist_section(workflow, docs)
    sections.append(section)
    
    # 근거 문서 추가
    if docs.get("file_paths"):
        for doc_type, path in docs["file_paths"].items():
            if path:
                source_files.append(path)
    
    markdown = "\n".join(sections)
    
    return {
        "markdown": markdown,
        "metadata": {
            "sections": 8,
            "steps": total_steps,
            "user_goal": user_goal
        },
        "source_files": list(set(source_files))
    }


def _goal_description(goal: UserGoal) -> str:
    descriptions = {
        "first_pr": "첫 PR 작성",
        "docs": "문서 기여",
        "bugfix": "버그 수정",
        "feature": "기능 추가"
    }
    return descriptions.get(goal, "첫 PR 작성")


def _build_prerequisites_section(context: OnboardingContext) -> tuple:
    code_map = context["code_map"]
    pm = code_map.get("package_manager")
    lang = code_map.get("language", "unknown")
    
    section = "## 1. 사전 준비\n\n"
    steps = 0
    
    # Git
    section += "- [ ] **Git 설치**: [git-scm.com](https://git-scm.com/) 에서 설치\n"
    steps += 1
    
    # GitHub 계정
    section += "- [ ] **GitHub 계정**: [github.com](https://github.com) 에서 가입\n"
    steps += 1
    
    # 언어별 환경
    lang_setup = {
        "JavaScript": "Node.js 설치 (https://nodejs.org)",
        "TypeScript": "Node.js 설치 (https://nodejs.org)",
        "Python": "Python 3.9+ 설치 (https://python.org)",
        "Go": "Go 설치 (https://go.dev)",
        "Rust": "Rust 설치 (https://rustup.rs)",
        "Java": "JDK 설치 (https://adoptium.net)",
    }
    if lang in lang_setup:
        section += f"- [ ] **개발 환경**: {lang_setup[lang]}\n"
        steps += 1
    
    # 패키지 매니저
    if pm:
        section += f"- [ ] **패키지 매니저**: `{pm}` 사용\n"
        steps += 1
    
    section += "\n"
    return section, steps


def _build_fork_clone_section(owner: str, repo: str, workflow: dict) -> tuple:
    section = "## 2. Fork & Clone\n\n"
    steps = 0
    
    # Fork
    section += f"### 2.1 Fork\n"
    section += f"1. GitHub에서 [{owner}/{repo}](https://github.com/{owner}/{repo}) 페이지 방문\n"
    section += f"2. 우측 상단 **Fork** 버튼 클릭\n"
    section += f"3. 자신의 계정으로 Fork 완료 확인\n\n"
    steps += 3
    
    # Clone
    section += f"### 2.2 Clone\n"
    section += f"```bash\n"
    section += f"# 자신의 Fork를 로컬에 Clone\n"
    section += f"git clone https://github.com/YOUR_USERNAME/{repo}.git\n"
    section += f"cd {repo}\n\n"
    section += f"# 원본 저장소를 upstream으로 추가\n"
    section += f"git remote add upstream https://github.com/{owner}/{repo}.git\n"
    section += f"```\n\n"
    steps += 2
    
    return section, steps


def _build_branch_section(workflow: dict) -> tuple:
    section = "## 3. Branch 생성\n\n"
    steps = 0
    
    branch_convention = workflow.get("branch_convention") or "feature/your-feature-name"
    
    section += f"```bash\n"
    section += f"# 최신 코드로 동기화\n"
    section += f"git fetch upstream\n"
    section += f"git checkout main\n"
    section += f"git merge upstream/main\n\n"
    section += f"# 작업 브랜치 생성\n"
    section += f"git checkout -b {branch_convention}\n"
    section += f"```\n\n"
    steps += 3
    
    if workflow.get("branch_convention"):
        section += f"> 브랜치 네이밍 컨벤션: `{workflow['branch_convention']}`\n\n"
    else:
        section += f"> 브랜치 네이밍 컨벤션: *확인되지 않음* (일반적으로 `feature/xxx` 형식 사용)\n\n"
    
    return section, steps


def _build_commit_section(workflow: dict, user_goal: UserGoal) -> tuple:
    section = "## 4. 코드 수정 & 커밋\n\n"
    steps = 0
    
    # 목표별 가이드
    goal_guides = {
        "first_pr": "간단한 문서 수정이나 오타 수정부터 시작하세요.",
        "docs": "README.md나 문서 파일을 개선하세요.",
        "bugfix": "이슈에 설명된 버그를 재현하고 수정하세요.",
        "feature": "기능 명세를 확인하고 구현하세요."
    }
    section += f"> **팁**: {goal_guides.get(user_goal, goal_guides['first_pr'])}\n\n"
    
    section += f"```bash\n"
    section += f"# 변경 사항 확인\n"
    section += f"git status\n"
    section += f"git diff\n\n"
    section += f"# 스테이징 및 커밋\n"
    section += f"git add .\n"
    section += f"git commit -m \"feat: add your feature description\"\n"
    section += f"```\n\n"
    steps += 2
    
    # 커밋 컨벤션
    if workflow.get("commit_convention"):
        section += f"### 커밋 메시지 규칙\n"
        section += f"이 프로젝트는 **{workflow['commit_convention']}**을 따릅니다.\n\n"
        section += f"```\n"
        section += f"<type>(<scope>): <description>\n\n"
        section += f"예시:\n"
        section += f"  feat(auth): add login feature\n"
        section += f"  fix(api): resolve null pointer exception\n"
        section += f"  docs(readme): update installation guide\n"
        section += f"```\n\n"
    else:
        section += f"> 커밋 메시지 규칙: *확인되지 않음* (CONTRIBUTING.md를 확인하세요)\n\n"
    
    return section, steps


def _build_test_build_section(workflow: dict, code_map: dict) -> tuple:
    section = "## 5. 테스트 & 빌드\n\n"
    steps = 0
    
    test_cmd = workflow.get("test_command")
    build_cmd = workflow.get("build_command")
    
    if test_cmd:
        section += f"### 테스트 실행\n"
        section += f"```bash\n{test_cmd}\n```\n\n"
        steps += 1
    else:
        section += f"### 테스트 실행\n"
        section += f"> 테스트 명령어: *확인되지 않음* (CONTRIBUTING.md 또는 README.md 참조)\n\n"
    
    if build_cmd:
        section += f"### 빌드 실행\n"
        section += f"```bash\n{build_cmd}\n```\n\n"
        steps += 1
    
    if workflow.get("ci_present"):
        section += f"> CI가 설정되어 있습니다. PR 생성 후 자동으로 테스트가 실행됩니다.\n\n"
    
    return section, steps


def _build_pr_section(owner: str, repo: str, docs: dict) -> tuple:
    section = "## 6. Pull Request 생성\n\n"
    steps = 0
    
    section += f"```bash\n"
    section += f"# 변경 사항 Push\n"
    section += f"git push origin HEAD\n"
    section += f"```\n\n"
    steps += 1
    
    section += f"1. GitHub에서 자신의 Fork 페이지 방문\n"
    section += f"2. **Compare & pull request** 버튼 클릭\n"
    section += f"3. PR 제목과 설명 작성\n"
    section += f"4. **Create pull request** 클릭\n\n"
    steps += 4
    
    # PR 템플릿 존재 여부
    if docs.get("templates"):
        section += f"### PR 템플릿\n"
        section += f"이 프로젝트에는 PR 템플릿이 있습니다. 템플릿의 항목을 모두 채워주세요.\n\n"
    
    section += f"### PR 설명 팁\n"
    section += f"- 변경 사항을 명확하게 설명\n"
    section += f"- 관련 이슈 번호 연결 (예: `Fixes #123`)\n"
    section += f"- 스크린샷/GIF 첨부 (UI 변경 시)\n\n"
    
    return section, steps


def _build_project_rules_section(docs: dict, workflow: dict) -> tuple:
    section = "## 7. 프로젝트 규칙\n\n"
    source_files: List[str] = []
    
    # CONTRIBUTING.md 기반 정보
    if docs.get("contributing"):
        section += f"### 기여 가이드\n"
        section += f"자세한 내용은 [CONTRIBUTING.md]({docs['file_paths'].get('contributing', 'CONTRIBUTING.md')})를 참조하세요.\n\n"
        source_files.append(docs['file_paths'].get('contributing', 'CONTRIBUTING.md'))
    else:
        section += f"### 기여 가이드\n"
        section += f"> CONTRIBUTING.md 파일이 *확인되지 않음*. 프로젝트 메인테이너에게 문의하세요.\n\n"
    
    # 코드 리뷰 프로세스
    if workflow.get("review_process"):
        section += f"### 코드 리뷰\n"
        section += f"{workflow['review_process']}\n\n"
    else:
        section += f"### 코드 리뷰\n"
        section += f"> 리뷰 프로세스: *확인되지 않음*. 일반적으로 1-2명의 리뷰어 승인이 필요합니다.\n\n"
    
    # CODE_OF_CONDUCT
    if docs.get("code_of_conduct"):
        section += f"### 행동 강령\n"
        section += f"이 프로젝트는 행동 강령(Code of Conduct)을 따릅니다. "
        section += f"[CODE_OF_CONDUCT.md]({docs['file_paths'].get('code_of_conduct', 'CODE_OF_CONDUCT.md')})를 읽어주세요.\n\n"
        source_files.append(docs['file_paths'].get('code_of_conduct', 'CODE_OF_CONDUCT.md'))
    
    return section, source_files


def _build_checklist_section(workflow: dict, docs: dict) -> str:
    section = "## 8. 초보자 실수 체크리스트\n\n"
    
    checklist = [
        ("upstream 동기화 확인", "작업 전 `git fetch upstream && git merge upstream/main`"),
        ("브랜치에서 작업", "`main` 브랜치에서 직접 작업하지 않기"),
        ("작은 단위로 커밋", "하나의 커밋에 너무 많은 변경 넣지 않기"),
        ("테스트 실행", "PR 전 로컬에서 테스트 실행"),
        ("린트/포맷 확인", "코드 스타일 가이드 준수"),
        ("PR 설명 작성", "왜 이 변경이 필요한지 설명"),
        ("관련 이슈 연결", "Fixes #이슈번호 형식으로 연결"),
        ("리뷰어 응답", "리뷰 코멘트에 친절하게 응답")
    ]
    
    for title, desc in checklist:
        section += f"- [ ] **{title}**: {desc}\n"
    
    section += "\n"
    return section
