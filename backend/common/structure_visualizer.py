"""
코드 구조 시각화 모듈

저장소 구조를 트리/다이어그램으로 시각화
"""

from typing import Dict, Any, List, Optional, Set
import re
import logging

logger = logging.getLogger(__name__)


# 파일 유형별 아이콘
FILE_ICONS = {
    # 프로그래밍 언어
    ".py": "PY",
    ".js": "JS",
    ".ts": "TS",
    ".jsx": "JSX",
    ".tsx": "TSX",
    ".java": "JAVA",
    ".go": "GO",
    ".rs": "RS",
    ".rb": "RB",
    ".php": "PHP",
    ".cs": "CS",
    ".cpp": "CPP",
    ".c": "C",
    ".swift": "SWIFT",
    ".kt": "KT",
    # 설정 파일
    ".json": "JSON",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".toml": "TOML",
    ".xml": "XML",
    ".ini": "INI",
    ".env": "ENV",
    # 문서
    ".md": "DOC",
    ".txt": "TXT",
    ".rst": "RST",
    # 웹
    ".html": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    # 데이터
    ".sql": "SQL",
    ".graphql": "GQL",
    # 기타
    ".sh": "SH",
    ".dockerfile": "DOCKER",
    "dockerfile": "DOCKER",
}

# 특수 폴더 설명
FOLDER_DESCRIPTIONS = {
    "src": "소스 코드",
    "lib": "라이브러리",
    "test": "테스트 코드",
    "tests": "테스트 코드",
    "spec": "테스트 스펙",
    "docs": "문서",
    "doc": "문서",
    "api": "API 정의",
    "config": "설정 파일",
    "scripts": "스크립트",
    "bin": "실행 파일",
    "build": "빌드 결과물",
    "dist": "배포 파일",
    "public": "정적 파일",
    "static": "정적 파일",
    "assets": "에셋 (이미지, 폰트 등)",
    "components": "UI 컴포넌트",
    "pages": "페이지",
    "views": "뷰",
    "models": "모델 정의",
    "controllers": "컨트롤러",
    "services": "서비스 레이어",
    "utils": "유틸리티",
    "helpers": "헬퍼 함수",
    "middleware": "미들웨어",
    "routes": "라우팅",
    "handlers": "핸들러",
    ".github": "GitHub 설정",
    ".vscode": "VSCode 설정",
}

# 무시할 폴더
IGNORE_FOLDERS = {
    "node_modules", "__pycache__", ".git", ".idea", ".vscode",
    "venv", ".venv", "env", ".env", "build", "dist", ".next",
    "coverage", ".pytest_cache", ".mypy_cache", "target"
}


def parse_tree_structure(file_tree: List[Dict[str, Any]], max_depth: int = 4) -> Dict[str, Any]:
    """
    파일 트리 구조 파싱
    
    Args:
        file_tree: GitHub API에서 받은 파일 목록
        max_depth: 최대 표시 깊이
    
    Returns:
        구조화된 트리 딕셔너리
    """
    root = {
        "name": "/",
        "type": "directory",
        "children": {},
        "file_count": 0,
        "dir_count": 0
    }
    
    for item in file_tree:
        path = item.get("path", "")
        item_type = item.get("type", "blob")
        
        if not path:
            continue
        
        parts = path.split("/")
        
        # 깊이 제한
        if len(parts) > max_depth:
            continue
        
        # 무시할 폴더 체크
        if any(p in IGNORE_FOLDERS for p in parts):
            continue
        
        current = root
        for i, part in enumerate(parts):
            if part not in current["children"]:
                is_dir = i < len(parts) - 1 or item_type == "tree"
                current["children"][part] = {
                    "name": part,
                    "type": "directory" if is_dir else "file",
                    "children": {},
                    "file_count": 0,
                    "dir_count": 0
                }
                if is_dir:
                    current["dir_count"] += 1
                else:
                    current["file_count"] += 1
            current = current["children"][part]
    
    return root


def generate_ascii_tree(
    tree: Dict[str, Any],
    prefix: str = "",
    is_last: bool = True,
    depth: int = 0,
    max_depth: int = 3
) -> str:
    """ASCII 트리 생성"""
    if depth > max_depth:
        return ""
    
    result = ""
    name = tree.get("name", "/")
    node_type = tree.get("type", "directory")
    
    if depth > 0:
        connector = "└── " if is_last else "├── "
        
        # 파일 아이콘
        icon = ""
        if node_type == "file":
            ext = "." + name.split(".")[-1].lower() if "." in name else ""
            icon = f"[{FILE_ICONS.get(ext, 'FILE')}] "
        else:
            icon = "[DIR] "
        
        result += f"{prefix}{connector}{icon}{name}\n"
    else:
        result += f"[ROOT] {name}\n"
    
    children = tree.get("children", {})
    child_items = sorted(
        children.items(),
        key=lambda x: (x[1]["type"] == "file", x[0])  # 폴더 먼저, 알파벳순
    )
    
    for i, (child_name, child_node) in enumerate(child_items):
        is_last_child = i == len(child_items) - 1
        new_prefix = prefix + ("    " if is_last else "│   ") if depth > 0 else ""
        result += generate_ascii_tree(child_node, new_prefix, is_last_child, depth + 1, max_depth)
    
    return result


def generate_mermaid_diagram(tree: Dict[str, Any], max_items: int = 30) -> str:
    """Mermaid 다이어그램 생성"""
    nodes = []
    edges = []
    node_id = 0
    item_count = 0
    
    def sanitize_label(text: str) -> str:
        """Mermaid 레이블에서 특수 문자 이스케이프"""
        # 따옴표, 괄호 등 이스케이프
        text = text.replace('"', '\\"')
        text = text.replace('[', '(')
        text = text.replace(']', ')')
        text = text.replace('<', '(')
        text = text.replace('>', ')')
        return text
    
    def add_node(node: Dict[str, Any], parent_id: Optional[int] = None) -> int:
        nonlocal node_id, item_count
        
        if item_count >= max_items:
            return -1
        
        current_id = node_id
        node_id += 1
        item_count += 1
        
        name = node.get("name", "root")
        node_type = node.get("type", "directory")
        safe_name = sanitize_label(name)
        
        # 노드 스타일 - 따옴표로 레이블 감싸기
        if node_type == "directory":
            nodes.append(f'    N{current_id}["{safe_name}"]')
        else:
            ext = "." + name.split(".")[-1].lower() if "." in name else ""
            icon = FILE_ICONS.get(ext, "FILE")
            nodes.append(f'    N{current_id}["{icon}: {safe_name}"]')
        
        # 엣지 - parent_id가 유효할 때만 추가
        if parent_id is not None and parent_id >= 0:
            edges.append(f"    N{parent_id} --> N{current_id}")
        
        # 자식 노드 - max_items 도달하지 않았을 때만
        if item_count < max_items:
            for child_node in node.get("children", {}).values():
                if item_count >= max_items:
                    break
                add_node(child_node, current_id)
        
        return current_id
    
    add_node(tree)
    
    # 코드블록 마커 없이 순수 Mermaid 코드만 반환
    diagram = "flowchart TD\n"
    diagram += "\n".join(nodes) + "\n"
    if edges:
        diagram += "\n".join(edges)
    
    return diagram


def analyze_project_structure(tree: Dict[str, Any]) -> Dict[str, Any]:
    """프로젝트 구조 분석"""
    # 통계 수집
    file_counts = {}
    folder_types = []
    
    def analyze_node(node: Dict[str, Any], path: str = ""):
        node_type = node.get("type", "directory")
        name = node.get("name", "")
        
        if node_type == "file":
            ext = "." + name.split(".")[-1].lower() if "." in name else ""
            file_counts[ext] = file_counts.get(ext, 0) + 1
        elif node_type == "directory" and name.lower() in FOLDER_DESCRIPTIONS:
            folder_types.append({
                "name": name,
                "path": path,
                "description": FOLDER_DESCRIPTIONS.get(name.lower(), "")
            })
        
        for child_name, child_node in node.get("children", {}).items():
            analyze_node(child_node, f"{path}/{child_name}" if path else child_name)
    
    analyze_node(tree)
    
    # 상위 파일 확장자
    top_extensions = sorted(file_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    
    # 주요 기술 스택 추론
    tech_stack = []
    if ".py" in file_counts:
        tech_stack.append("Python")
    if ".js" in file_counts or ".ts" in file_counts:
        tech_stack.append("JavaScript/TypeScript")
    if ".java" in file_counts:
        tech_stack.append("Java")
    if ".go" in file_counts:
        tech_stack.append("Go")
    if ".rs" in file_counts:
        tech_stack.append("Rust")
    if ".rb" in file_counts:
        tech_stack.append("Ruby")
    
    return {
        "file_extension_counts": dict(top_extensions),
        "detected_tech_stack": tech_stack,
        "key_folders": folder_types,
        "total_files": sum(file_counts.values()),
        "total_extensions": len(file_counts)
    }


def generate_structure_visualization(
    owner: str,
    repo: str,
    file_tree: List[Dict[str, Any]],
    max_depth: int = 3
) -> Dict[str, Any]:
    """
    저장소 구조 시각화 생성
    
    Args:
        owner: 저장소 소유자
        repo: 저장소 이름
        file_tree: 파일 트리 데이터
        max_depth: 최대 깊이
    
    Returns:
        시각화 결과
    """
    parsed_tree = parse_tree_structure(file_tree, max_depth + 1)
    parsed_tree["name"] = f"{owner}/{repo}"
    
    ascii_tree = generate_ascii_tree(parsed_tree, max_depth=max_depth)
    mermaid_diagram = generate_mermaid_diagram(parsed_tree)
    analysis = analyze_project_structure(parsed_tree)
    
    return {
        "owner": owner,
        "repo": repo,
        "ascii_tree": ascii_tree,
        "mermaid_diagram": mermaid_diagram,
        "analysis": analysis
    }


def format_structure_as_markdown(visualization: Dict[str, Any]) -> str:
    """구조 시각화를 Markdown으로 변환"""
    md = f"# {visualization['owner']}/{visualization['repo']} 코드 구조\n\n"
    
    analysis = visualization.get("analysis", {})
    
    # 프로젝트 개요
    md += "## 프로젝트 개요\n\n"
    tech_stack = analysis.get("detected_tech_stack", [])
    if tech_stack:
        md += f"**주요 기술:** {', '.join(tech_stack)}\n\n"
    md += f"**총 파일 수:** {analysis.get('total_files', 0)}개\n\n"
    
    # 주요 폴더 설명
    key_folders = analysis.get("key_folders", [])
    if key_folders:
        md += "## 주요 폴더\n\n"
        md += "| 폴더 | 설명 |\n|------|------|\n"
        for folder in key_folders[:10]:
            md += f"| `{folder['name']}` | {folder['description']} |\n"
        md += "\n"
    
    # ASCII 트리
    md += "## 폴더 구조\n\n"
    md += "```\n"
    md += visualization.get("ascii_tree", "")
    md += "```\n\n"
    
    # Mermaid 다이어그램 (시각적 표시)
    mermaid_diagram = visualization.get("mermaid_diagram", "")
    if mermaid_diagram:
        md += "## 구조 다이어그램\n\n"
        md += "```mermaid\n"
        md += mermaid_diagram
        md += "\n```\n\n"
    
    # 파일 확장자 통계
    ext_counts = analysis.get("file_extension_counts", {})
    if ext_counts:
        md += "## 파일 유형 분포\n\n"
        md += "| 확장자 | 개수 |\n|--------|------|\n"
        for ext, count in ext_counts.items():
            md += f"| `{ext}` | {count} |\n"
        md += "\n"
    
    return md
