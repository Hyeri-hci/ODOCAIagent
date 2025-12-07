from backend.core.models import RepoSnapshot, StructureCoreResult

def analyze_structure(snapshot: RepoSnapshot) -> StructureCoreResult:
    """
    저장소 구조를 분석하여 StructureCoreResult를 반환합니다.
    (현재는 파일 존재 여부만 확인하는 간단한 로직)
    """
    # 파일 목록 (트리 탐색이 이상적이지만, 현재 snapshot 구조상 readme_content 등만 있음)
    # 실제로는 snapshot에 file_tree 정보가 있어야 정확함.
    # 여기서는 간단히 가정하거나, 추후 확장을 위해 기본값 반환.
    
    # TODO: RepoSnapshot에 file_list 추가 필요. 현재는 Mock 성격으로 반환.
    
    return StructureCoreResult(
        has_tests=False,
        has_ci=False,
        has_docs_folder=False,
        has_build_config=False,
        test_files=[],
        ci_files=[],
        build_files=[],
        structure_score=0
    )

# Alias for backward compatibility or explicit naming
analyze_structure_from_snapshot = analyze_structure
