"""
기여 가이드 통합 모듈

- CONTRIBUTING.md 파싱 및 체크리스트 생성
- 신규 기여자를 위한 첫 PR 단계별 가이드
"""

from typing import Dict, Any, List, Optional
import re
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# 기여 체크리스트 (Contribution Checklist)
# =============================================================================

# 일반적인 기여 규칙 패턴
CONTRIBUTION_PATTERNS = {
    "code_style": [
        r"(?:code\s*style|coding\s*style|format|lint|eslint|prettier|black|flake8|pylint)",
        r"코드\s*스타일|포맷|린트"
    ],
    "testing": [
        r"(?:test|testing|unit\s*test|pytest|jest|mocha)",
        r"테스트|단위\s*테스트"
    ],
    "commit_message": [
        r"(?:commit\s*message|conventional\s*commit|commit\s*format)",
        r"커밋\s*메시지|커밋\s*규칙"
    ],
    "pr_template": [
        r"(?:pull\s*request|pr\s*template|pr\s*description)",
        r"풀\s*리퀘스트|PR\s*템플릿"
    ],
    "documentation": [
        r"(?:document|doc|readme|changelog)",
        r"문서|문서화"
    ],
    "issue_reference": [
        r"(?:issue\s*reference|link\s*issue|fixes\s*#|closes\s*#)",
        r"이슈\s*연결|이슈\s*참조"
    ],
    "branch_naming": [
        r"(?:branch\s*name|branch\s*naming|naming\s*convention)",
        r"브랜치\s*이름|브랜치\s*규칙"
    ],
    "sign_off": [
        r"(?:sign\s*off|dco|developer\s*certificate)",
        r"서명|DCO"
    ],
    "license": [
        r"(?:license|licensing|copyright)",
        r"라이선스|저작권"
    ],
    "code_review": [
        r"(?:code\s*review|review\s*process|reviewer)",
        r"코드\s*리뷰|리뷰"
    ]
}

# 기본 체크리스트 항목
DEFAULT_CHECKLIST = [
    {
        "category": "code_style",
        "title": "코드 스타일 준수",
        "description": "프로젝트의 코드 스타일 가이드를 따랐는지 확인하세요.",
        "priority": "high",
        "default": True
    },
    {
        "category": "testing",
        "title": "테스트 작성/실행",
        "description": "새 기능에 대한 테스트를 작성하고, 기존 테스트가 통과하는지 확인하세요.",
        "priority": "high",
        "default": True
    },
    {
        "category": "commit_message",
        "title": "커밋 메시지 규칙",
        "description": "프로젝트의 커밋 메시지 규칙을 따랐는지 확인하세요.",
        "priority": "medium",
        "default": True
    },
    {
        "category": "documentation",
        "title": "문서 업데이트",
        "description": "필요한 경우 README나 관련 문서를 업데이트했는지 확인하세요.",
        "priority": "medium",
        "default": True
    },
    {
        "category": "issue_reference",
        "title": "이슈 연결",
        "description": "PR에 관련 이슈를 연결했는지 확인하세요. (예: Fixes #123)",
        "priority": "medium",
        "default": True
    }
]


def parse_contributing_md(content: str) -> Dict[str, Any]:
    """
    CONTRIBUTING.md 내용 파싱하여 규칙 추출
    
    Args:
        content: CONTRIBUTING.md 파일 내용
    
    Returns:
        파싱된 규칙 정보
    """
    if not content:
        return {"found": False, "rules": [], "raw_sections": []}
    
    content_lower = content.lower()
    detected_rules = []
    
    # 패턴 매칭으로 규칙 감지
    for rule_type, patterns in CONTRIBUTION_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, content_lower, re.IGNORECASE):
                detected_rules.append(rule_type)
                break
    
    # 섹션 추출 (## 또는 ### 헤더)
    sections = []
    header_pattern = r'^#{2,3}\s+(.+)$'
    for match in re.finditer(header_pattern, content, re.MULTILINE):
        sections.append(match.group(1).strip())
    
    # 구체적인 명령어 추출
    commands = []
    code_block_pattern = r'```(?:bash|shell|sh)?\n(.*?)```'
    for match in re.finditer(code_block_pattern, content, re.DOTALL):
        cmd = match.group(1).strip()
        if cmd and len(cmd) < 200:  # 너무 긴 건 제외
            commands.append(cmd)
    
    return {
        "found": True,
        "rules": list(set(detected_rules)),
        "raw_sections": sections,
        "commands": commands[:10]  # 최대 10개
    }


def generate_contribution_checklist(
    owner: str,
    repo: str,
    contributing_content: Optional[str] = None
) -> Dict[str, Any]:
    """
    기여 체크리스트 생성
    
    Args:
        owner: 저장소 소유자
        repo: 저장소 이름
        contributing_content: CONTRIBUTING.md 내용 (없으면 기본 체크리스트)
    
    Returns:
        체크리스트 딕셔너리
    """
    checklist_items = []
    parsed_rules = {"found": False, "rules": [], "raw_sections": [], "commands": []}
    
    # CONTRIBUTING.md 파싱
    if contributing_content:
        parsed_rules = parse_contributing_md(contributing_content)
    
    # 감지된 규칙 기반 체크리스트 생성
    detected_categories = set(parsed_rules.get("rules", []))
    
    for item in DEFAULT_CHECKLIST:
        # 감지된 규칙이거나 기본 항목이면 추가
        if item["category"] in detected_categories or item.get("default"):
            checklist_items.append({
                "id": len(checklist_items) + 1,
                "category": item["category"],
                "title": item["title"],
                "description": item["description"],
                "priority": item["priority"],
                "checked": False,
                "detected": item["category"] in detected_categories
            })
    
    # 추가 규칙이 있으면 체크리스트에 추가
    extra_rules = detected_categories - {item["category"] for item in DEFAULT_CHECKLIST}
    extra_item_map = {
        "branch_naming": {
            "title": "브랜치 이름 규칙",
            "description": "프로젝트의 브랜치 네이밍 규칙을 따랐는지 확인하세요.",
            "priority": "low"
        },
        "sign_off": {
            "title": "커밋 서명 (DCO)",
            "description": "커밋에 서명(sign-off)이 필요한지 확인하세요. (git commit -s)",
            "priority": "medium"
        },
        "license": {
            "title": "라이선스 확인",
            "description": "라이선스 조건을 이해하고 준수했는지 확인하세요.",
            "priority": "low"
        },
        "pr_template": {
            "title": "PR 템플릿 작성",
            "description": "PR 템플릿의 모든 항목을 작성했는지 확인하세요.",
            "priority": "medium"
        },
        "code_review": {
            "title": "코드 리뷰 준비",
            "description": "리뷰어가 이해하기 쉽게 PR을 작성했는지 확인하세요.",
            "priority": "medium"
        }
    }
    
    for rule in extra_rules:
        if rule in extra_item_map:
            info = extra_item_map[rule]
            checklist_items.append({
                "id": len(checklist_items) + 1,
                "category": rule,
                "title": info["title"],
                "description": info["description"],
                "priority": info["priority"],
                "checked": False,
                "detected": True
            })
    
    # 우선순위 정렬
    priority_order = {"high": 0, "medium": 1, "low": 2}
    checklist_items.sort(key=lambda x: (priority_order.get(x["priority"], 99), x["id"]))
    
    return {
        "title": f"{owner}/{repo} 기여 체크리스트",
        "contributing_found": parsed_rules.get("found", False),
        "sections_detected": parsed_rules.get("raw_sections", []),
        "commands": parsed_rules.get("commands", []),
        "items": checklist_items,
        "total_items": len(checklist_items),
        "helpful_links": {
            "contributing": f"https://github.com/{owner}/{repo}/blob/main/CONTRIBUTING.md",
            "issues": f"https://github.com/{owner}/{repo}/issues",
            "pr_template": f"https://github.com/{owner}/{repo}/blob/main/.github/PULL_REQUEST_TEMPLATE.md"
        }
    }


def format_checklist_as_markdown(checklist: Dict[str, Any]) -> str:
    """
    체크리스트를 Markdown 형식으로 변환
    """
    md = f"# {checklist['title']}\n\n"
    
    if checklist.get("contributing_found"):
        md += "> CONTRIBUTING.md를 분석하여 생성된 체크리스트입니다.\n\n"
    else:
        md += "> 일반적인 오픈소스 기여 규칙 기반 체크리스트입니다.\n\n"
    
    # 체크리스트 항목
    md += "## PR 제출 전 체크리스트\n\n"
    
    for item in checklist.get("items", []):
        priority_icon = {"high": "", "medium": "", "low": ""}.get(item["priority"], "")
        md += f"- [ ] {priority_icon} **{item['title']}**\n"
        md += f"  - {item['description']}\n"
    
    # 유용한 명령어
    commands = checklist.get("commands", [])
    if commands:
        md += "\n## 유용한 명령어\n\n"
        md += "```bash\n"
        for cmd in commands[:5]:
            md += f"{cmd}\n"
        md += "```\n"
    
    # 링크
    md += "\n## 관련 링크\n\n"
    for name, url in checklist.get("helpful_links", {}).items():
        md += f"- [{name}]({url})\n"
    
    return md


# =============================================================================
# 첫 기여 가이드 (First Contribution Guide)
# =============================================================================

def generate_first_contribution_guide(
    owner: str,
    repo: str,
    recommended_issue: Optional[Dict[str, Any]] = None,
    user_github_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    첫 기여를 위한 단계별 가이드 생성
    
    Args:
        owner: 저장소 소유자
        repo: 저장소 이름
        recommended_issue: 추천 이슈 (있으면 해당 이슈 기반 가이드)
        user_github_id: 사용자 GitHub ID (있으면 personalized)
    
    Returns:
        단계별 가이드 딕셔너리
    """
    repo_url = f"https://github.com/{owner}/{repo}"
    clone_url = f"https://github.com/{owner}/{repo}.git"
    
    # 이슈 정보
    issue_title = recommended_issue.get("title", "선택한 이슈") if recommended_issue else "Good First Issue"
    issue_number = recommended_issue.get("number", "N") if recommended_issue else "N"
    issue_url = recommended_issue.get("url", f"{repo_url}/issues") if recommended_issue else f"{repo_url}/issues"
    
    steps = [
        {
            "step": 1,
            "title": "저장소 Fork 하기",
            "description": "원본 저장소를 본인 계정으로 복사합니다.",
            "action": "브라우저에서 실행",
            "url": f"{repo_url}/fork",
            "command": None,
            "tip": "Fork 버튼은 저장소 페이지 우측 상단에 있습니다."
        },
        {
            "step": 2,
            "title": "Fork한 저장소 Clone 하기",
            "description": "Fork한 저장소를 로컬에 다운로드합니다.",
            "action": "터미널에서 실행",
            "command": f"git clone https://github.com/{user_github_id or 'YOUR_USERNAME'}/{repo}.git" if user_github_id else f"git clone https://github.com/YOUR_USERNAME/{repo}.git",
            "tip": "YOUR_USERNAME을 본인의 GitHub 아이디로 변경하세요."
        },
        {
            "step": 3,
            "title": "프로젝트 디렉토리로 이동",
            "description": "Clone한 프로젝트 폴더로 이동합니다.",
            "action": "터미널에서 실행",
            "command": f"cd {repo}",
            "tip": None
        },
        {
            "step": 4,
            "title": "Upstream 원격 저장소 추가",
            "description": "원본 저장소를 upstream으로 등록하여 최신 변경사항을 받을 수 있게 합니다.",
            "action": "터미널에서 실행",
            "command": f"git remote add upstream {clone_url}",
            "tip": "이미 추가되어 있으면 'error: remote upstream already exists' 메시지가 나옵니다. 무시해도 됩니다."
        },
        {
            "step": 5,
            "title": "작업 브랜치 생성",
            "description": f"이슈 #{issue_number} 작업을 위한 새 브랜치를 만듭니다.",
            "action": "터미널에서 실행",
            "command": f"git checkout -b fix/issue-{issue_number}",
            "tip": "브랜치 이름은 작업 내용을 설명하는 이름으로 지정하세요. 예: feature/add-login, fix/typo-readme"
        },
        {
            "step": 6,
            "title": "코드 수정하기",
            "description": f"이슈 '{issue_title}'를 해결하기 위한 코드를 수정합니다.",
            "action": "에디터에서 작업",
            "url": issue_url,
            "command": None,
            "tip": "수정 전에 프로젝트의 CONTRIBUTING.md와 코드 스타일 가이드를 확인하세요."
        },
        {
            "step": 7,
            "title": "변경사항 확인",
            "description": "수정한 파일들을 확인합니다.",
            "action": "터미널에서 실행",
            "command": "git status",
            "tip": "수정된 파일이 빨간색으로 표시됩니다."
        },
        {
            "step": 8,
            "title": "변경사항 스테이징",
            "description": "커밋할 파일들을 스테이징합니다.",
            "action": "터미널에서 실행",
            "command": "git add .",
            "tip": "특정 파일만 추가하려면 'git add 파일명'을 사용하세요."
        },
        {
            "step": 9,
            "title": "커밋 생성",
            "description": "변경사항을 커밋합니다.",
            "action": "터미널에서 실행",
            "command": f'git commit -m "fix: resolve issue #{issue_number}"',
            "tip": "커밋 메시지는 프로젝트의 커밋 규칙을 따르세요. 일반적으로 'type: description' 형식을 사용합니다."
        },
        {
            "step": 10,
            "title": "Fork한 저장소에 Push",
            "description": "로컬 변경사항을 GitHub에 업로드합니다.",
            "action": "터미널에서 실행",
            "command": f"git push origin fix/issue-{issue_number}",
            "tip": "처음 push할 때 GitHub 인증이 필요할 수 있습니다."
        },
        {
            "step": 11,
            "title": "Pull Request 생성",
            "description": "원본 저장소에 PR을 생성합니다.",
            "action": "브라우저에서 실행",
            "url": f"{repo_url}/compare/main...{user_github_id or 'YOUR_USERNAME'}:fix/issue-{issue_number}" if user_github_id else f"{repo_url}/compare",
            "command": None,
            "tip": "PR 제목과 설명에 어떤 문제를 해결했는지 명확히 작성하세요. 'Fixes #{issue_number}'를 포함하면 PR 머지 시 이슈가 자동으로 닫힙니다."
        },
        {
            "step": 12,
            "title": "리뷰 대기 및 수정",
            "description": "메인테이너의 리뷰를 기다리고, 피드백이 있으면 수정합니다.",
            "action": "대기",
            "command": None,
            "tip": "리뷰가 오래 걸릴 수 있습니다. 일주일 이상 무응답이면 정중하게 리마인드 코멘트를 남겨보세요."
        }
    ]
    
    return {
        "title": f"{owner}/{repo} 첫 기여 가이드",
        "description": "오픈소스 프로젝트에 첫 번째 기여를 하기 위한 단계별 안내입니다.",
        "target_issue": {
            "number": issue_number,
            "title": issue_title,
            "url": issue_url
        } if recommended_issue else None,
        "steps": steps,
        "total_steps": len(steps),
        "estimated_time": "30분 ~ 2시간",
        "prerequisites": [
            "Git 설치 (https://git-scm.com/)",
            "GitHub 계정 생성",
            "코드 에디터 (VS Code 추천)"
        ],
        "helpful_links": {
            "repo": repo_url,
            "issues": f"{repo_url}/issues",
            "contributing": f"{repo_url}/blob/main/CONTRIBUTING.md",
            "discussions": f"{repo_url}/discussions"
        }
    }


def format_guide_as_markdown(guide: Dict[str, Any]) -> str:
    """
    첫 기여 가이드를 Markdown 형식으로 변환
    """
    md = f"# {guide['title']}\n\n"
    md += f"{guide['description']}\n\n"
    md += f"**예상 소요 시간:** {guide['estimated_time']}\n\n"
    
    # 사전 준비사항
    md += "## 사전 준비사항\n\n"
    for prereq in guide.get("prerequisites", []):
        md += f"- {prereq}\n"
    md += "\n"
    
    # 대상 이슈
    if guide.get("target_issue"):
        issue = guide["target_issue"]
        md += f"## 작업할 이슈\n\n"
        md += f"**[#{issue['number']}] {issue['title']}**\n"
        md += f"- 링크: {issue['url']}\n\n"
    
    # 단계별 가이드
    md += "## 단계별 가이드\n\n"
    for step in guide.get("steps", []):
        md += f"### Step {step['step']}: {step['title']}\n\n"
        md += f"{step['description']}\n\n"
        
        if step.get("command"):
            md += f"```bash\n{step['command']}\n```\n\n"
        elif step.get("url"):
            md += f"[이 링크로 이동]({step['url']})\n\n"
        
        if step.get("tip"):
            md += f"> **TIP:** {step['tip']}\n\n"
    
    # 유용한 링크
    md += "## 유용한 링크\n\n"
    for name, url in guide.get("helpful_links", {}).items():
        md += f"- [{name}]({url})\n"
    
    return md
