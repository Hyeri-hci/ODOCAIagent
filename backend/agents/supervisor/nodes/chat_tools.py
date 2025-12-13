"""채팅용 도구 레지스트리."""
from typing import Dict, Any, Callable, Optional
import logging
import asyncio
from functools import partial

logger = logging.getLogger(__name__)


class ChatToolRegistry:
    """채팅 도구 관리"""
    
    def __init__(self):
        self.tools: Dict[str, Callable] = {}
        self.descriptions: Dict[str, str] = {}
    
    def register(self, name: str, func: Callable, description: str):
        self.tools[name] = func
        self.descriptions[name] = description
    
    def get_tool(self, name: str) -> Optional[Callable]:
        return self.tools.get(name)
    
    def get_all_tools(self) -> Dict[str, Callable]:
        return self.tools
    
    def get_tool_list_for_llm(self) -> str:
        lines = []
        for name, desc in self.descriptions.items():
            lines.append(f"- {name}: {desc}")
        return "\n".join(lines)


_registry = ChatToolRegistry()


def get_registry() -> ChatToolRegistry:
    return _registry


async def _run_sync(func, *args, **kwargs):
    """동기 함수를 async로 래핑"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, partial(func, *args, **kwargs))


# === GitHub 도구 ===

async def search_codebase(owner: str, repo: str, query: str, **kwargs) -> Dict[str, Any]:
    """코드베이스에서 키워드 검색"""
    import requests
    from backend.common.config import GITHUB_TOKEN
    
    try:
        headers = {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}
        url = f"https://api.github.com/search/code?q={query}+repo:{owner}/{repo}"
        
        resp = await _run_sync(requests.get, url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("items", [])[:10]
            results = [{"path": i["path"], "name": i["name"]} for i in items]
            return {"success": True, "query": query, "total": len(results), "results": results}
        return {"success": False, "error": f"HTTP {resp.status_code}"}
    except Exception as e:
        logger.warning(f"search_codebase failed: {e}")
        return {"success": False, "error": str(e)}


async def read_file(owner: str, repo: str, path: str, **kwargs) -> Dict[str, Any]:
    """특정 파일 내용 읽기"""
    import requests
    import base64
    from backend.common.config import GITHUB_TOKEN
    
    try:
        headers = {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}
        url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
        
        resp = await _run_sync(requests.get, url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            content = base64.b64decode(data.get("content", "")).decode("utf-8", errors="ignore")
            return {
                "success": True, "path": path,
                "content": content[:5000],
                "truncated": len(content) > 5000
            }
        return {"success": False, "error": f"HTTP {resp.status_code}"}
    except Exception as e:
        logger.warning(f"read_file failed: {e}")
        return {"success": False, "error": str(e)}


async def get_directory_structure(owner: str, repo: str, path: str = "", **kwargs) -> Dict[str, Any]:
    """디렉토리 구조 가져오기"""
    from backend.common.github_client import fetch_repo_tree
    
    try:
        result = await _run_sync(fetch_repo_tree, owner, repo)
        items = result.get("tree", [])[:100] if result else []
        return {"success": True, "path": path or "/", "items": [{"path": i["path"], "type": i["type"]} for i in items]}
    except Exception as e:
        logger.warning(f"get_directory_structure failed: {e}")
        return {"success": False, "error": str(e)}


async def search_issues(owner: str, repo: str, query: str = "", labels: str = "", **kwargs) -> Dict[str, Any]:
    """이슈/PR 검색"""
    from backend.common.github_client import fetch_beginner_issues
    
    try:
        label_list = [l.strip() for l in labels.split(",")] if labels else None
        issues = await _run_sync(fetch_beginner_issues, owner, repo, labels=label_list, max_count=10)
        return {
            "success": True,
            "query": query,
            "total": len(issues),
            "issues": issues[:10]
        }
    except Exception as e:
        logger.warning(f"search_issues failed: {e}")
        return {"success": False, "error": str(e)}


# === Agent 호출 도구 ===

async def call_diagnosis_agent(owner: str, repo: str, **kwargs) -> Dict[str, Any]:
    """Diagnosis Agent 호출하여 건강도 분석"""
    try:
        from backend.agents.diagnosis.graph import run_diagnosis_graph
        
        result = await run_diagnosis_graph(owner, repo)
        return {
            "success": True,
            "health_score": result.get("health_score"),
            "documentation_quality": result.get("documentation_quality"),
            "activity_score": result.get("activity_maintainability"),
            "onboarding_score": result.get("onboarding_score"),
            "summary": result.get("project_summary", "")[:500]
        }
    except Exception as e:
        logger.warning(f"call_diagnosis_agent failed: {e}")
        return {"success": False, "error": str(e)}


async def call_security_agent(owner: str, repo: str, **kwargs) -> Dict[str, Any]:
    """Security Agent 호출하여 보안 분석"""
    try:
        from backend.agents.security.agent.security_agent import SecurityAgent
        from backend.common.config import LLM_BASE_URL, LLM_API_KEY, LLM_MODEL_NAME, LLM_TEMPERATURE
        
        agent = SecurityAgent(
            llm_base_url=LLM_BASE_URL,
            llm_api_key=LLM_API_KEY,
            llm_model=LLM_MODEL_NAME,
            llm_temperature=LLM_TEMPERATURE,
            max_iterations=10
        )
        
        result = await agent.analyze(f"{owner}/{repo} 보안 분석")
        final = result.get("final_result", {}).get("results", {})
        
        return {
            "success": True,
            "security_score": final.get("security_score"),
            "security_grade": final.get("security_grade"),
            "vulnerability_count": final.get("vulnerabilities", {}).get("total", 0),
            "risk_level": final.get("risk_level")
        }
    except Exception as e:
        logger.warning(f"call_security_agent failed: {e}")
        return {"success": False, "error": str(e)}


async def call_onboarding_agent(owner: str, repo: str, experience_level: str = "beginner", **kwargs) -> Dict[str, Any]:
    """Onboarding Agent 호출하여 온보딩 가이드 생성"""
    try:
        from backend.agents.onboarding.graph import run_onboarding_graph
        
        result = await run_onboarding_graph(owner, repo, experience_level=experience_level)
        plan = result.get("plan", [])
        
        return {
            "success": True,
            "plan_weeks": len(plan),
            "first_week_goals": plan[0].get("goals", []) if plan else [],
            "summary": result.get("summary", "")[:500]
        }
    except Exception as e:
        logger.warning(f"call_onboarding_agent failed: {e}")
        return {"success": False, "error": str(e)}


async def get_dependencies(owner: str, repo: str, **kwargs) -> Dict[str, Any]:
    """의존성 파일 목록 및 상세 정보 가져오기 (Security 도구 활용)"""
    try:
        from backend.agents.security.tools.dependency_analyzer import (
            analyze_repository_dependencies,
            find_dependency_files,
            summarize_dependency_analysis
        )
        
        # 먼저 파일 목록만 빠르게 가져오기
        dep_files = await _run_sync(find_dependency_files, owner, repo)
        
        if not dep_files:
            return {
                "success": True,
                "dependency_files": [],
                "total_files": 0,
                "message": "의존성 파일이 발견되지 않았습니다."
            }
        
        # 상세 분석 수행
        analysis = await _run_sync(analyze_repository_dependencies, owner, repo)
        
        if analysis.get("error"):
            return {
                "success": False,
                "error": analysis["error"],
                "dependency_files": dep_files
            }
        
        # 파일별 의존성 정보 포맷팅
        files_info = []
        for file_data in analysis.get("files", []):
            deps = file_data.get("dependencies", [])
            dep_list = []
            for d in deps[:15]:  # 최대 15개
                name = d.get("name", "")
                version = d.get("version", "*")
                is_dev = d.get("is_dev", False)
                dev_tag = " (dev)" if is_dev else ""
                dep_list.append(f"{name}@{version}{dev_tag}")
            
            files_info.append({
                "file": file_data.get("file", ""),
                "dependencies": dep_list,
                "total_count": len(deps)
            })
        
        # 요약 정보
        summary = analysis.get("summary", {})
        
        return {
            "success": True,
            "dependency_files": dep_files,
            "total_files": analysis.get("total_files", 0),
            "total_dependencies": analysis.get("total_dependencies", 0),
            "runtime_deps": summary.get("runtime_dependencies", 0),
            "dev_deps": summary.get("dev_dependencies", 0),
            "by_source": summary.get("by_source", {}),
            "files_detail": files_info
        }
    except Exception as e:
        logger.warning(f"get_dependencies failed: {e}")
        return {"success": False, "error": str(e)}


# === 도구 등록 ===

_registry.register("search_codebase", search_codebase, "코드베이스에서 키워드 검색")
_registry.register("read_file", read_file, "특정 파일 내용 읽기")
_registry.register("get_directory_structure", get_directory_structure, "디렉토리 구조 탐색")
_registry.register("search_issues", search_issues, "이슈/PR 검색")
_registry.register("call_diagnosis_agent", call_diagnosis_agent, "건강도/활동성 분석")
_registry.register("call_security_agent", call_security_agent, "보안 취약점 분석")
_registry.register("call_onboarding_agent", call_onboarding_agent, "온보딩 가이드 생성")
_registry.register("get_dependencies", get_dependencies, "의존성 파일 및 패키지 목록 조회")


def get_chat_tools() -> Dict[str, Callable]:
    return _registry.get_all_tools()


def get_tool_descriptions() -> str:
    return _registry.get_tool_list_for_llm()
