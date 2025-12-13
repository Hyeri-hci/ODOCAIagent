"""
Onboarding Handler Node (Unified)
Supervisor에서 Onboarding Agent를 호출합니다.
Tool A (기여 가이드) / Tool B (커리큘럼) / Tool C (구조 시각화) / Tool D (이슈 추천) / Both 모드를 지원합니다.
"""

import logging
import re
import random
from typing import Dict, Any, Literal, Optional

from backend.agents.supervisor.models import SupervisorState
from backend.agents.onboarding.graph import run_onboarding_graph
from backend.agents.onboarding.context_builder import build_onboarding_context
from backend.agents.onboarding.tools.contributor_guide_tool import generate_contributor_guide
from backend.agents.onboarding.tools.curriculum_tool import generate_onboarding_curriculum
from backend.agents.diagnosis.graph import run_diagnosis
from backend.common.intent_utils import detect_force_refresh
from backend.common.structure_visualizer import generate_structure_visualization
from backend.common.github_client import fetch_repo_tree, fetch_beginner_issues
from backend.common.issue_matcher import match_issues_to_user

logger = logging.getLogger(__name__)

# Intent 키워드
GUIDE_KEYWORDS = ["가이드", "기여", "pr", "포크", "클론", "브랜치", "contributing", "fork", "clone", "branch", "커밋", "commit"]
CURRICULUM_KEYWORDS = ["주", "커리큘럼", "플랜", "로드맵", "학습", "온보딩", "week", "curriculum", "plan", "roadmap", "onboarding"]
STRUCTURE_KEYWORDS = ["코드 구조", "폴더 구조", "구조", "트리", "디렉토리", "structure", "tree", "directory", "folder"]
ISSUE_KEYWORDS = ["이슈", "issue", "good first", "찾아줘", "추천", "초보자", "beginner", "좋은 이슈", "쉬운 이슈"]


def _route_by_intent(user_message: str) -> Literal["guide", "curriculum", "both", "structure", "issues"]:
    """사용자 의도 분석 → Tool 선택"""
    if not user_message:
        return "curriculum"  # 기본값: 커리큘럼
    
    msg = user_message.lower()
    has_guide = any(kw in msg for kw in GUIDE_KEYWORDS)
    has_curriculum = any(kw in msg for kw in CURRICULUM_KEYWORDS)
    has_structure = any(kw in msg for kw in STRUCTURE_KEYWORDS)
    has_issues = any(kw in msg for kw in ISSUE_KEYWORDS)
    
    # 우선순위: issues > structure > curriculum > both > guide
    if has_issues and not has_curriculum:
        return "issues"
    elif has_structure:
        return "structure"
    elif has_curriculum and has_guide:
        return "both"
    elif has_curriculum:
        return "curriculum"
    elif has_guide:
        return "guide"
    else:
        return "curriculum"  # 기본값


def _extract_weeks(user_message: str) -> int:
    """메시지에서 주차 수 추출"""
    if not user_message:
        return 4  # 기본 4주
    
    # "4주", "4 weeks", "4-week" 등 패턴
    patterns = [
        r"(\d+)\s*주",
        r"(\d+)\s*week",
        r"(\d+)-week"
    ]
    for pattern in patterns:
        match = re.search(pattern, user_message.lower())
        if match:
            weeks = int(match.group(1))
            return max(1, min(weeks, 12))  # 1-12주 제한
    
    return 4  # 기본 4주


def _generate_variation_options(previous_plan: Optional[Dict], force_refresh: bool) -> Dict[str, Any]:
    """
    다시 생성 요청 시 다양성을 위한 옵션 생성
    이전 플랜과 다른 내용을 생성하도록 힌트 제공
    """
    if not force_refresh and not previous_plan:
        return {}
    
    # 랜덤 시드로 다양성 확보
    variation_seed = random.randint(1, 1000)
    
    # 학습 스타일 다양화
    learning_styles = ["hands-on", "theoretical", "project-based", "mentoring"]
    focus_areas = ["code-review", "documentation", "testing", "feature-development", "bug-fixing"]
    
    options = {
        "variation_seed": variation_seed,
        "preferred_style": random.choice(learning_styles),
        "focus_area": random.choice(focus_areas),
        "avoid_previous": True
    }
    
    # 이전 플랜의 주요 내용을 피하도록 힌트 추가
    if previous_plan and isinstance(previous_plan, dict):
        prev_summary = previous_plan.get("summary", "")
        prev_plan_data = previous_plan.get("plan", [])
        
        # 이전 플랜의 첫 주차 목표 추출 (피하기 위해)
        if prev_plan_data and len(prev_plan_data) > 0:
            first_week = prev_plan_data[0]
            options["avoid_goals"] = first_week.get("goals", [])[:2] if first_week.get("goals") else []
    
    logger.info(f"[Onboarding] Variation options: style={options.get('preferred_style')}, focus={options.get('focus_area')}")
    return options


async def run_onboarding_agent_node(state: SupervisorState) -> Dict[str, Any]:
    """
    통합 온보딩 Agent 실행
    
    - Tool A: 기여 가이드 (contributor guide)
    - Tool B: N주 커리큘럼 (onboarding curriculum)
    - Both: Tool B + Tool A를 0주차/부록으로 포함
    """
    logger.info("Running Unified Onboarding Agent")
    
    owner = state.get("owner", "")
    repo = state.get("repo", "")
    ref = state.get("ref", "main")
    user_message = state.get("user_message", "")
    accumulated_context = state.get("accumulated_context", {})
    
    # ===== 다시 생성 요청 감지 =====
    force_refresh = detect_force_refresh(user_message)
    previous_plan = accumulated_context.get("onboarding_result", {})
    
    if force_refresh:
        logger.info(f"[Onboarding] Force refresh detected! Will generate different content.")
    
    if previous_plan:
        logger.info(f"[Onboarding] Previous plan exists, will avoid duplicate content.")
    
    # 의도 분석
    tool_mode = _route_by_intent(user_message)
    weeks = _extract_weeks(user_message)
    
    logger.info(f"[Onboarding] Tool mode: {tool_mode}, weeks: {weeks}, force_refresh: {force_refresh}")
    
    # 사용자 레벨
    session_profile = accumulated_context.get("user_profile", {})
    user_level = session_profile.get("experience_level", "beginner")
    
    # ===== 다양성 옵션 생성 =====
    variation_options = _generate_variation_options(previous_plan, force_refresh)
    
    try:
        # 1. 공통 컨텍스트 빌드
        context = await build_onboarding_context(owner, repo, ref)
        
        # 다양성 옵션을 컨텍스트에 추가
        if variation_options:
            context["variation_options"] = variation_options
        
        result: Dict[str, Any] = {}
        
        # 2. Tool 실행
        if tool_mode == "guide":
            # Tool A: 기여 가이드만
            guide_result = generate_contributor_guide(context, user_goal="first_pr")
            result = {
                "type": "contributor_guide",
                "markdown": guide_result["markdown"],
                "metadata": guide_result["metadata"],
                "source_files": guide_result["source_files"],
                "summary": f"{owner}/{repo} 기여 가이드가 생성되었습니다."
            }
            
        elif tool_mode == "curriculum":
            # Tool B: 커리큘럼만 (다양성 옵션 포함)
            curriculum_result = generate_onboarding_curriculum(
                context, 
                user_level=user_level, 
                weeks=weeks,
                variation_options=variation_options
            )
            # curriculum_tool에서 생성된 plan 데이터 직접 추출
            plan_data = curriculum_result.get("curriculum_weeks", [])
            if not plan_data:
                plan_data = _parse_curriculum_to_plan(curriculum_result)
            
            result = {
                "type": "onboarding_plan",
                "markdown": curriculum_result["markdown"],
                "plan": plan_data,
                "metadata": curriculum_result["metadata"],
                "source_files": curriculum_result["source_files"],
                "summary": f"{weeks}주 온보딩 플랜이 생성되었습니다." + (" (새로 생성됨)" if force_refresh else ""),
                "is_regenerated": force_refresh
            }
        
        elif tool_mode == "structure":
            # Tool C: 코드 구조 시각화
            logger.info(f"[Onboarding] Structure visualization mode")
            
            # file_tree 가져오기
            accumulated_context = state.get("accumulated_context", {})
            file_tree = accumulated_context.get("file_tree", [])
            
            # file_tree가 없으면 GitHub에서 직접 조회
            if not file_tree:
                try:
                    tree_result = fetch_repo_tree(owner, repo)
                    if isinstance(tree_result, dict):
                        file_tree = tree_result.get("tree", [])
                    else:
                        file_tree = tree_result if isinstance(tree_result, list) else []
                    logger.info(f"[Onboarding] Fetched file tree from GitHub: {len(file_tree)} items")
                except Exception as e:
                    logger.warning(f"[Onboarding] Failed to fetch file tree: {e}")
                    file_tree = []
            
            if file_tree:
                visualization = generate_structure_visualization(owner, repo, file_tree)
                result = {
                    "type": "structure",
                    "structure_visualization": visualization,
                    "summary": f"{owner}/{repo} 프로젝트의 코드 구조입니다."
                }
                
                # structure_visualization을 별도로 반환
                return {
                    "agent_result": result,
                    "target_agent": "onboarding",
                    "structure_visualization": visualization,
                    "iteration": state.get("iteration", 0) + 1
                }
            else:
                result = {
                    "type": "structure",
                    "structure_visualization": None,
                    "summary": "코드 구조를 가져올 수 없습니다."
                }
        
        elif tool_mode == "issues":
            # Tool D: 이슈 추천 (Good First Issue 매칭)
            logger.info(f"[Onboarding] Issue recommendation mode")
            
            try:
                # GitHub에서 초보자 친화적 이슈 가져오기
                issues = fetch_beginner_issues(owner, repo, max_count=10)
                logger.info(f"[Onboarding] Fetched {len(issues)} beginner issues")
                
                if issues:
                    # 이슈 매칭 및 점수화
                    matched_issues = match_issues_to_user(issues, experience_level=user_level)
                    logger.info(f"[Onboarding] Matched {len(matched_issues)} issues for {user_level}")
                    
                    # 난이도 레벨 한글 변환
                    level_kr = {"beginner": "입문자", "intermediate": "중급자", "advanced": "숙련자"}.get(user_level, user_level)
                    
                    # 마크다운 형식으로 이슈 목록 생성
                    md_lines = [f"# 🎯 {owner}/{repo} 추천 이슈\n"]
                    md_lines.append(f"> **{level_kr}** 수준에 맞는 이슈를 추천합니다.\n")
                    md_lines.append(f"> 총 {len(issues)}개 이슈 중 {len(matched_issues)}개를 분석했습니다.\n\n")
                    
                    for i, issue in enumerate(matched_issues[:5], 1):
                        title = issue.get("title", "제목 없음")
                        number = issue.get("number", "")
                        url = issue.get("url", f"https://github.com/{owner}/{repo}/issues/{number}")
                        labels = issue.get("labels", [])
                        label_names = [l.get("name", l) if isinstance(l, dict) else str(l) for l in labels[:4]]
                        score = issue.get("match_score", 0)
                        reasons = issue.get("match_reasons", [])
                        difficulty = issue.get("difficulty", {}).get("level", "unknown")
                        est_time = issue.get("difficulty", {}).get("estimated_time", {}).get("text", "")
                        
                        # 난이도 이모지
                        diff_emoji = {"easy": "🟢", "medium": "🟡", "hard": "🔴"}.get(difficulty, "⚪")
                        diff_kr = {"easy": "쉬움", "medium": "보통", "hard": "어려움"}.get(difficulty, "알 수 없음")
                        
                        md_lines.append(f"## {i}. {title}")
                        md_lines.append(f"")
                        md_lines.append(f"| 항목 | 내용 |")
                        md_lines.append(f"|------|------|")
                        md_lines.append(f"| 🔗 링크 | [#{number}]({url}) |")
                        if label_names:
                            label_badges = " ".join([f"`{l}`" for l in label_names])
                            md_lines.append(f"| 🏷️ 라벨 | {label_badges} |")
                        md_lines.append(f"| {diff_emoji} 난이도 | {diff_kr} |")
                        if est_time:
                            md_lines.append(f"| ⏱️ 예상 시간 | {est_time} |")
                        if score:
                            md_lines.append(f"| 📊 매칭 점수 | **{score}점** |")
                        if reasons:
                            md_lines.append(f"| 💡 추천 이유 | {', '.join(reasons)} |")
                        md_lines.append("")
                    
                    md_lines.append("\n---\n")
                    md_lines.append("## 📚 시작하는 방법\n")
                    md_lines.append(f"1. 관심 있는 이슈에 댓글로 작업 의사 표시\n")
                    md_lines.append(f"2. 메인테이너의 승인 후 작업 시작\n")
                    md_lines.append(f"3. Fork → Clone → Branch → Commit → PR\n")
                    md_lines.append(f"\n💡 **팁**: `good first issue` 라벨은 메인테이너가 초보자에게 적합하다고 표시한 것입니다.")
                    
                    result = {
                        "type": "contributor_guide",
                        "markdown": "\n".join(md_lines),
                        "matched_issues": matched_issues[:5],
                        "total_issues": len(issues),
                        "summary": f"{owner}/{repo}에서 {len(matched_issues[:5])}개의 추천 이슈를 찾았습니다."
                    }
                else:
                    result = {
                        "type": "contributor_guide",
                        "markdown": f"# {owner}/{repo}\n\n현재 열려 있는 초보자 친화적 이슈가 없습니다.\n\n프로젝트의 [이슈 페이지](https://github.com/{owner}/{repo}/issues)를 확인해보세요.",
                        "matched_issues": [],
                        "total_issues": 0,
                        "summary": "현재 열려 있는 초보자 친화적 이슈가 없습니다."
                    }
            except Exception as e:
                logger.error(f"[Onboarding] Failed to fetch issues: {e}")
                result = {
                    "type": "contributor_guide",
                    "markdown": f"# {owner}/{repo}\n\n이슈를 가져오는 중 오류가 발생했습니다.\n\n프로젝트의 [이슈 페이지](https://github.com/{owner}/{repo}/issues)를 직접 확인해보세요.",
                    "matched_issues": [],
                    "summary": "이슈를 가져오는 중 오류가 발생했습니다."
                }
            
        else:
            # Both: Tool B + Tool A (부록) - 다양성 옵션 포함
            curriculum_result = generate_onboarding_curriculum(
                context,
                user_level=user_level,
                weeks=weeks,
                variation_options=variation_options
            )
            guide_result = generate_contributor_guide(context, user_goal="first_pr")
            
            # 커리큘럼에 가이드를 부록으로 추가
            combined_markdown = curriculum_result["markdown"]
            combined_markdown += "\n---\n\n# 부록: 첫 PR 기여 가이드\n\n"
            combined_markdown += guide_result["markdown"]
            
            result = {
                "type": "onboarding_plan",
                "markdown": combined_markdown,
                "plan": _parse_curriculum_to_plan(curriculum_result),
                "metadata": {
                    **curriculum_result["metadata"],
                    "includes_guide": True
                },
                "source_files": list(set(
                    curriculum_result["source_files"] + guide_result["source_files"]
                )),
                "summary": f"{weeks}주 온보딩 플랜 + 기여 가이드가 생성되었습니다." + (" (새로 생성됨)" if force_refresh else ""),
                "is_regenerated": force_refresh
            }
        
        logger.info(f"[Onboarding] Result type: {result.get('type')}, regenerated: {force_refresh}")
        
    except Exception as e:
        logger.error(f"Onboarding agent execution failed: {e}", exc_info=True)
        result = {
            "type": "onboarding_plan",
            "error": str(e),
            "message": "온보딩 플랜 생성 중 오류가 발생했습니다."
        }
    
    # 메타인지: 품질 체크
    has_error = "error" in result
    has_markdown = bool(result.get("markdown"))
    plan_weeks = result.get("metadata", {}).get("weeks", 0)
    
    if has_error:
        quality = "failed"
        confidence = 0.0
    elif has_markdown and plan_weeks >= 4:
        quality = "high"
        confidence = 0.9
    elif has_markdown:
        quality = "medium"
        confidence = 0.7
    else:
        quality = "low"
        confidence = 0.4
    
    logger.info(f"[METACOGNITION] Onboarding completed:")
    logger.info(f"  - Tool mode: {tool_mode}")
    logger.info(f"  - Quality: {quality} (confidence: {confidence:.2f})")
    
    return {
        "agent_result": result,
        "target_agent": "onboarding",
        "onboarding_result": result,
        "iteration": state.get("iteration", 0) + 1
    }


def _parse_curriculum_to_plan(curriculum_result: Dict[str, Any]) -> list:
    """커리큘럼 결과를 plan 리스트로 변환 (프론트엔드 호환성)"""
    # 이미 curriculum_tool에서 생성된 plan 데이터가 있으면 그대로 사용
    if "plan" in curriculum_result:
        return curriculum_result["plan"]
    
    # curriculum_weeks 데이터가 있으면 사용 (week, goals, tasks 포함)
    if "curriculum_weeks" in curriculum_result:
        return curriculum_result["curriculum_weeks"]
    
    # 마크다운에서 주차 정보 추출 시도
    markdown = curriculum_result.get("markdown", "")
    if markdown:
        plan = _extract_plan_from_markdown(markdown)
        if plan:
            return plan
    
    # fallback: 빈 plan 구조
    weeks = curriculum_result.get("metadata", {}).get("weeks", 4)
    return [{"week": i + 1, "goals": [], "tasks": []} for i in range(weeks)]


def _extract_plan_from_markdown(markdown: str) -> list:
    """마크다운에서 주차별 plan 추출"""
    import re
    
    plan = []
    # ## Week 1: 또는 ## 1주차: 패턴 찾기
    week_pattern = r'##\s*(?:Week\s*(\d+)|(?:(\d+)주차))\s*[:\-]?\s*([^\n]*)'
    weeks = re.findall(week_pattern, markdown, re.IGNORECASE)
    
    for match in weeks:
        week_num = int(match[0] or match[1])
        title = match[2].strip() if len(match) > 2 else f"{week_num}주차"
        
        plan.append({
            "week": week_num,
            "title": title,
            "goals": [],
            "tasks": []
        })
    
    return plan
