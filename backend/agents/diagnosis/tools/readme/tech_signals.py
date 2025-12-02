"""README 기술 신호 추출기: 코드블록, 명령 패턴, 경로 참조 등."""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any

from backend.agents.diagnosis.config import get_tech_patterns


@dataclass
class TechSignals:
    """기술 신호 데이터."""
    # 코드블록 통계 (언어별)
    code_blocks: Dict[str, int] = field(default_factory=dict)
    
    # 명령형 코드블록 (bash/docker/npm 등)
    command_blocks: Dict[str, int] = field(default_factory=dict)
    command_block_count: int = 0
    
    # 파일/경로 참조
    path_refs: List[str] = field(default_factory=list)
    
    # 플랫폼 플래그
    platform_flags: Dict[str, bool] = field(default_factory=dict)
    
    # 집계
    tech_signal_count: int = 0
    token_count: int = 0
    tech_density: float = 0.0  # per 1k tokens
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# 명령형 언어 (가중치 높음)
COMMAND_LANGUAGES = {"bash", "sh", "shell", "zsh", "powershell", "cmd", "batch"}

# 명령 패턴 컴파일 (설정에서 로드)
def _compile_command_patterns() -> List[re.Pattern]:
    """기술 명령 패턴 컴파일."""
    patterns = get_tech_patterns().get("commands", [])
    compiled = []
    for p in patterns:
        try:
            compiled.append(re.compile(p, re.IGNORECASE))
        except re.error:
            continue
    return compiled


def _compile_path_patterns() -> List[re.Pattern]:
    """경로 패턴 컴파일."""
    patterns = get_tech_patterns().get("paths", [])
    compiled = []
    for p in patterns:
        try:
            # 경로는 단어 경계로 매칭
            compiled.append(re.compile(rf"(?:^|[\s\"`'])({re.escape(p)}[^\s\"`']*)", re.MULTILINE))
        except re.error:
            continue
    return compiled


# 코드블록 추출 정규식
CODE_BLOCK_PATTERN = re.compile(r"```(\w*)\n([\s\S]*?)```", re.MULTILINE)

# 인라인 코드 (백틱) 추출
INLINE_CODE_PATTERN = re.compile(r"`([^`\n]+)`")

# 플랫폼 파일 패턴
PLATFORM_FILES = {
    "has_pyproject": r"pyproject\.toml",
    "has_requirements": r"requirements.*\.txt",
    "has_setup_py": r"setup\.py",
    "has_package_json": r"package\.json",
    "has_dockerfile": r"[Dd]ockerfile",
    "has_docker_compose": r"docker-compose\.ya?ml|compose\.ya?ml",
    "has_makefile": r"[Mm]akefile",
    "has_cargo": r"Cargo\.toml",
    "has_go_mod": r"go\.mod",
}


def extract_tech_signals(readme_content: str) -> TechSignals:
    """
    README에서 기술 신호 추출.
    
    Args:
        readme_content: README 마크다운 내용
        
    Returns:
        TechSignals: 추출된 기술 신호
    """
    if not readme_content:
        return TechSignals()
    
    signals = TechSignals()
    
    # 토큰 수 계산 (공백 기준 단순 분리)
    signals.token_count = len(readme_content.split())
    
    # 1. 코드블록 추출
    code_blocks: Dict[str, int] = {}
    command_blocks: Dict[str, int] = {}
    command_patterns = _compile_command_patterns()
    
    for match in CODE_BLOCK_PATTERN.finditer(readme_content):
        lang = match.group(1).lower() or "unknown"
        content = match.group(2)
        
        code_blocks[lang] = code_blocks.get(lang, 0) + 1
        
        # 명령형 언어 체크
        if lang in COMMAND_LANGUAGES:
            command_blocks[lang] = command_blocks.get(lang, 0) + 1
        
        # 명령 패턴 체크 (모든 코드블록에서)
        for pattern in command_patterns:
            if pattern.search(content):
                pattern_name = pattern.pattern.split()[0].replace("\\", "")
                command_blocks[pattern_name] = command_blocks.get(pattern_name, 0) + 1
    
    signals.code_blocks = code_blocks
    signals.command_blocks = command_blocks
    signals.command_block_count = sum(command_blocks.values())
    
    # 2. 경로 참조 추출
    path_refs: List[str] = []
    path_patterns = _compile_path_patterns()
    
    for pattern in path_patterns:
        for match in pattern.finditer(readme_content):
            path = match.group(1) if match.groups() else match.group(0)
            if path and path not in path_refs:
                path_refs.append(path)
    
    # 인라인 코드에서도 경로 추출
    for match in INLINE_CODE_PATTERN.finditer(readme_content):
        code = match.group(1)
        # 파일 경로 패턴 (./으로 시작하거나 확장자 포함)
        if re.match(r"^\.?/|^\w+/|\.\w+$", code):
            if code not in path_refs and len(code) < 100:
                path_refs.append(code)
    
    signals.path_refs = path_refs[:50]  # 최대 50개
    
    # 3. 플랫폼 플래그 감지
    platform_flags: Dict[str, bool] = {}
    for flag_name, pattern in PLATFORM_FILES.items():
        platform_flags[flag_name] = bool(re.search(pattern, readme_content, re.IGNORECASE))
    
    signals.platform_flags = platform_flags
    
    # 4. 기술 신호 집계
    tech_signal_count = (
        sum(code_blocks.values()) +  # 코드블록 수
        signals.command_block_count * 2 +  # 명령형은 가중치 2배
        len(path_refs) +  # 경로 참조 수
        sum(platform_flags.values()) * 3  # 플랫폼 파일은 가중치 3배
    )
    signals.tech_signal_count = tech_signal_count
    
    # 5. 밀도 계산 (per 1k tokens)
    if signals.token_count > 0:
        signals.tech_density = round(tech_signal_count / (signals.token_count / 1000), 2)
    
    return signals
