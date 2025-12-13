"""
Contributor Handler Node
Supervisor에서 Contributor Agent를 호출하고 결과를 처리하는 노드입니다.
"""

import logging
from typing import Dict, Any

from backend.agents.supervisor.models import SupervisorState
from backend.common.contribution_guide import (
    generate_first_contribution_guide,
    format_guide_as_markdown,
    generate_contribution_checklist,
    format_checklist_as_markdown
)
from backend.common.issue_matcher import (
    match_issues_to_user
)
from backend.common.structure_visualizer import (
    generate_structure_visualization
)
from backend.common.community_analyzer import (
    analyze_community_activity
)
from backend.common.github_client import fetch_repo_tree

logger = logging.getLogger(__name__)

async def run_contributor_agent_node(state: SupervisorState) -> Dict[str, Any]:
    """신규 기여자 지원 에이전트 실행 (첫 기여 가이드, 이슈 매칭, 체크리스트 등)"""
    logger.info("Running Contributor Agent")
    
    try:
        owner = state.get("owner", "")
        repo = state.get("repo", "")
        user_message = state.get("user_message", "").lower()
        
        # 구조만 요청하는 경우 감지
        structure_only = any(kw in user_message for kw in ["구조", "폴더", "structure", "트리", "tree", "디렉토리"])
        structure_only = structure_only and not any(kw in user_message for kw in ["기여", "가이드", "이슈", "pr", "체크리스트"])
        
        result = {
            "type": "structure" if structure_only else "contributor",
            "owner": owner,
            "repo": repo,
            "features": {}
        }
        
        # 코드 구조 시각화 (구조 요청 시 우선 처리)
        if any(kw in user_message for kw in ["구조", "폴더", "structure", "코드 구조", "트리", "tree"]):
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
                    logger.info(f"[Contributor] Fetched file tree from GitHub: {len(file_tree)} items")
                except Exception as e:
                    logger.warning(f"[Contributor] Failed to fetch file tree: {e}")
                    file_tree = []
            
            if file_tree:
                visualization = generate_structure_visualization(owner, repo, file_tree)
                result["features"]["structure_visualization"] = visualization
                logger.info(f"[Contributor] Structure visualization generated")
        
        # 구조만 요청한 경우 기여 가이드 생략
        if structure_only:
            logger.info(f"[Contributor] Structure-only request, skipping contribution guide")
            return {
                "agent_result": result,
                "target_agent": "contributor",
                "structure_visualization": result["features"].get("structure_visualization"),
                "iteration": state.get("iteration", 0) + 1
            }
        
        # 첫 기여 가이드 (기본 제공)
        guide = generate_first_contribution_guide(owner, repo)
        result["features"]["first_contribution_guide"] = guide
        
        # 기여 체크리스트 (기본 제공)
        checklist = generate_contribution_checklist(owner, repo)
        result["features"]["contribution_checklist"] = checklist
        
        if any(kw in user_message for kw in ["이슈", "issue", "good first"]):
            # Good First Issue 매칭 (accumulated_context에서 이슈 정보 가져옴)
            accumulated_context = state.get("accumulated_context", {})
            issues = accumulated_context.get("open_issues", [])
            if issues:
                matched = match_issues_to_user(issues, experience_level="beginner")
                result["features"]["issue_matching"] = matched
        
        if any(kw in user_message for kw in ["커뮤니티", "활동", "community"]):
            # 커뮤니티 활동 분석
            accumulated_context = state.get("accumulated_context", {})
            prs = accumulated_context.get("recent_prs", [])
            issues = accumulated_context.get("recent_issues", [])
            contributors = accumulated_context.get("contributors", [])
            
            community = analyze_community_activity(
                owner, repo, 
                recent_prs=prs, 
                recent_issues=issues, 
                contributors=contributors
            )
            result["features"]["community_analysis"] = community
        
        # 마크다운 요약 생성
        summary_md = f"# {owner}/{repo} 기여 가이드\n\n"
        summary_md += format_guide_as_markdown(guide)
        summary_md += "\n---\n"
        summary_md += format_checklist_as_markdown(checklist)
        result["summary_markdown"] = summary_md
        
        # 메타인지: 품질 체크
        features = result.get("features", {})
        feature_count = len(features)
        has_structure = bool(features.get("structure_visualization"))
        has_guide = bool(features.get("first_contribution_guide"))
        
        if feature_count >= 3 or has_structure:
            quality = "high"
            confidence = 0.9
        elif feature_count >= 1:
            quality = "medium"
            confidence = 0.7
        else:
            quality = "low"
            confidence = 0.4
        
        logger.info(f"[METACOGNITION] Contributor completed:")
        logger.info(f"  - Features: {list(features.keys())}")
        logger.info(f"  - Quality: {quality} (confidence: {confidence:.2f})")
        
        logger.info(f"Contributor agent completed: {list(result['features'].keys())}")
        
        return {
            "agent_result": result,
            "target_agent": "contributor",  # 프론트엔드에서 인식하도록
            "iteration": state.get("iteration", 0) + 1
        }
        
    except ImportError as e:
        logger.warning(f"Contributor agent import failed: {e}")
        return {
            "agent_result": {
                "type": "contributor",
                "message": f"기여자 지원 모듈 로드 실패: {e}",
                "status": "import_error"
            },
            "iteration": state.get("iteration", 0) + 1
        }
    except Exception as e:
        logger.error(f"Contributor agent failed: {e}")
        return {
            "agent_result": {
                "type": "contributor",
                "message": f"기여자 지원 실행 오류: {e}",
                "status": "error"
            },
            "iteration": state.get("iteration", 0) + 1
        }
