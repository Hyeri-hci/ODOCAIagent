"""
Good First Issue 스마트 매칭 모듈

사용자 기술 스택 기반 이슈 추천 및 난이도 예측
"""

from typing import Dict, Any, List, Optional, Set
import re
import logging

logger = logging.getLogger(__name__)


# 기술 스택 키워드 매핑
TECH_STACK_KEYWORDS = {
    "python": ["python", "py", "django", "flask", "fastapi", "pytest", "pip"],
    "javascript": ["javascript", "js", "node", "npm", "react", "vue", "angular", "typescript", "ts"],
    "java": ["java", "spring", "maven", "gradle", "kotlin"],
    "go": ["go", "golang"],
    "rust": ["rust", "cargo"],
    "ruby": ["ruby", "rails", "gem"],
    "php": ["php", "laravel", "composer"],
    "csharp": ["c#", "csharp", ".net", "dotnet", "nuget"],
    "cpp": ["c++", "cpp", "cmake"],
    "swift": ["swift", "ios", "xcode"],
    "kotlin": ["kotlin", "android"],
    "documentation": ["docs", "documentation", "readme", "typo", "translation", "i18n", "l10n"],
    "testing": ["test", "testing", "jest", "pytest", "junit", "spec"],
    "devops": ["ci", "cd", "docker", "kubernetes", "k8s", "github actions", "workflow"],
    "frontend": ["css", "html", "ui", "ux", "design", "style", "layout"],
    "backend": ["api", "server", "database", "sql", "backend"],
}

# 난이도 키워드
DIFFICULTY_KEYWORDS = {
    "easy": ["typo", "docs", "readme", "simple", "easy", "minor", "small", "trivial", "beginner"],
    "medium": ["feature", "enhancement", "improvement", "add", "implement", "refactor"],
    "hard": ["bug", "critical", "complex", "architecture", "performance", "security", "breaking"]
}

# 예상 시간 (분)
ESTIMATED_TIME = {
    "easy": {"min": 15, "max": 60, "text": "15분 ~ 1시간"},
    "medium": {"min": 60, "max": 240, "text": "1시간 ~ 4시간"},
    "hard": {"min": 240, "max": 480, "text": "4시간 이상"}
}


def extract_tech_stack_from_text(text: str) -> Set[str]:
    """텍스트에서 기술 스택 추출"""
    if not text:
        return set()
    
    text_lower = text.lower()
    detected = set()
    
    for stack, keywords in TECH_STACK_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text_lower:
                detected.add(stack)
                break
    
    return detected


def estimate_difficulty(
    title: str,
    body: str,
    labels: List[str]
) -> Dict[str, Any]:
    """
    이슈 난이도 예측
    
    Args:
        title: 이슈 제목
        body: 이슈 본문
        labels: 이슈 라벨 목록
    
    Returns:
        난이도 정보
    """
    combined_text = f"{title} {body} {' '.join(labels)}".lower()
    
    # 라벨 기반 우선 판단
    for label in labels:
        label_lower = label.lower()
        if any(kw in label_lower for kw in ["good first issue", "beginner", "easy", "starter"]):
            return {
                "level": "easy",
                "confidence": 0.9,
                "estimated_time": ESTIMATED_TIME["easy"],
                "reason": "Good First Issue 라벨"
            }
        if any(kw in label_lower for kw in ["help wanted", "enhancement"]):
            return {
                "level": "medium",
                "confidence": 0.7,
                "estimated_time": ESTIMATED_TIME["medium"],
                "reason": "Enhancement/Help Wanted 라벨"
            }
        if any(kw in label_lower for kw in ["critical", "complex", "breaking"]):
            return {
                "level": "hard",
                "confidence": 0.8,
                "estimated_time": ESTIMATED_TIME["hard"],
                "reason": "Critical/Complex 라벨"
            }
    
    # 키워드 기반 판단
    easy_score = sum(1 for kw in DIFFICULTY_KEYWORDS["easy"] if kw in combined_text)
    medium_score = sum(1 for kw in DIFFICULTY_KEYWORDS["medium"] if kw in combined_text)
    hard_score = sum(1 for kw in DIFFICULTY_KEYWORDS["hard"] if kw in combined_text)
    
    if easy_score > medium_score and easy_score > hard_score:
        return {
            "level": "easy",
            "confidence": min(0.6 + easy_score * 0.1, 0.9),
            "estimated_time": ESTIMATED_TIME["easy"],
            "reason": "키워드 분석 결과"
        }
    elif hard_score > medium_score:
        return {
            "level": "hard",
            "confidence": min(0.5 + hard_score * 0.1, 0.8),
            "estimated_time": ESTIMATED_TIME["hard"],
            "reason": "키워드 분석 결과"
        }
    else:
        return {
            "level": "medium",
            "confidence": 0.5,
            "estimated_time": ESTIMATED_TIME["medium"],
            "reason": "기본 추정"
        }


def match_issues_to_user(
    issues: List[Dict[str, Any]],
    user_skills: Optional[List[str]] = None,
    experience_level: str = "beginner"
) -> List[Dict[str, Any]]:
    """
    사용자 기술 스택에 맞는 이슈 매칭
    
    Args:
        issues: 이슈 목록
        user_skills: 사용자 기술 스택 (예: ["python", "javascript"])
        experience_level: 사용자 경험 수준 (beginner/intermediate/advanced)
    
    Returns:
        매칭 점수와 함께 정렬된 이슈 목록
    """
    user_skill_set = set(s.lower() for s in (user_skills or []))
    
    matched_issues = []
    
    for issue in issues:
        title = issue.get("title", "")
        body = issue.get("body", "")
        labels = [l.get("name", "") if isinstance(l, dict) else l for l in issue.get("labels", [])]
        number = issue.get("number", 0)
        url = issue.get("html_url", issue.get("url", ""))
        assignee = issue.get("assignee")
        
        # 이미 할당된 이슈는 낮은 점수
        is_assigned = assignee is not None
        
        # 기술 스택 추출
        combined_text = f"{title} {body} {' '.join(labels)}"
        issue_tech_stack = extract_tech_stack_from_text(combined_text)
        
        # 난이도 예측
        difficulty = estimate_difficulty(title, body, labels)
        
        # 매칭 점수 계산
        match_score = 0
        match_reasons = []
        
        # 기술 스택 매칭 (최대 40점)
        if user_skill_set:
            skill_match = user_skill_set.intersection(issue_tech_stack)
            if skill_match:
                match_score += len(skill_match) * 15
                match_reasons.append(f"기술 스택 일치: {', '.join(skill_match)}")
        
        # 난이도 매칭 (최대 30점)
        difficulty_level = difficulty["level"]
        if experience_level == "beginner" and difficulty_level == "easy":
            match_score += 30
            match_reasons.append("초보자에게 적합한 난이도")
        elif experience_level == "intermediate" and difficulty_level in ["easy", "medium"]:
            match_score += 25
            match_reasons.append("중급자에게 적합한 난이도")
        elif experience_level == "advanced":
            match_score += 20  # 상급자는 모든 난이도 가능
        
        # Good First Issue 라벨 보너스 (20점)
        label_lower = [l.lower() for l in labels]
        if any("good first issue" in l or "beginner" in l for l in label_lower):
            match_score += 20
            match_reasons.append("Good First Issue")
        
        # 할당되지 않은 이슈 보너스 (10점)
        if not is_assigned:
            match_score += 10
            match_reasons.append("아직 할당되지 않음")
        else:
            match_reasons.append("이미 다른 사람이 작업 중")
        
        matched_issues.append({
            "number": number,
            "title": title,
            "url": url,
            "labels": labels,
            "is_assigned": is_assigned,
            "tech_stack": list(issue_tech_stack),
            "difficulty": difficulty,
            "match_score": match_score,
            "match_reasons": match_reasons
        })
    
    # 매칭 점수로 정렬
    matched_issues.sort(key=lambda x: x["match_score"], reverse=True)
    
    return matched_issues


def format_matched_issues_as_markdown(
    matched_issues: List[Dict[str, Any]],
    user_skills: Optional[List[str]] = None
) -> str:
    """매칭된 이슈 목록을 Markdown으로 변환"""
    md = "# 추천 이슈\n\n"
    
    if user_skills:
        md += f"**사용자 기술 스택:** {', '.join(user_skills)}\n\n"
    
    if not matched_issues:
        md += "추천할 이슈가 없습니다.\n"
        return md
    
    md += "| 순위 | 이슈 | 난이도 | 예상 시간 | 매칭 점수 |\n"
    md += "|------|------|--------|----------|----------|\n"
    
    for i, issue in enumerate(matched_issues[:10], 1):
        difficulty = issue.get("difficulty", {})
        level_icon = {"easy": "쉬움", "medium": "보통", "hard": "어려움"}.get(difficulty.get("level", ""), "")
        time_text = difficulty.get("estimated_time", {}).get("text", "알 수 없음")
        
        title = issue["title"][:50] + "..." if len(issue["title"]) > 50 else issue["title"]
        assigned_mark = " (작업중)" if issue.get("is_assigned") else ""
        
        md += f"| {i} | [#{issue['number']}]({issue['url']}) {title}{assigned_mark} | {level_icon} | {time_text} | {issue['match_score']} |\n"
    
    md += "\n"
    
    # 상위 3개 이슈 상세 정보
    md += "## 상위 추천 이슈 상세\n\n"
    for i, issue in enumerate(matched_issues[:3], 1):
        md += f"### {i}. #{issue['number']} {issue['title']}\n\n"
        md += f"- **링크:** {issue['url']}\n"
        md += f"- **라벨:** {', '.join(issue['labels']) if issue['labels'] else '없음'}\n"
        md += f"- **기술 스택:** {', '.join(issue['tech_stack']) if issue['tech_stack'] else '일반'}\n"
        md += f"- **매칭 이유:** {', '.join(issue['match_reasons'])}\n\n"
    
    return md
