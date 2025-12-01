"""
벤치마크 공통 유틸리티
"""
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional
import json
import hashlib
from pathlib import Path


@dataclass
class BenchmarkResult:
    """벤치마크 결과 기본 구조"""
    repo_owner: str
    repo_name: str
    category: str = ""
    
    # 점수
    health_score: Optional[float] = None
    onboarding_score: Optional[float] = None
    documentation_score: Optional[float] = None
    activity_score: Optional[float] = None
    
    # 라벨
    health_level: Optional[str] = None
    onboarding_level: Optional[str] = None
    is_healthy: Optional[bool] = None
    
    # Task 통계
    task_count: int = 0
    beginner_count: int = 0
    intermediate_count: int = 0
    advanced_count: int = 0
    
    # Kind 비율
    docs_kind_ratio: float = 0.0
    test_kind_ratio: float = 0.0
    issue_kind_ratio: float = 0.0
    meta_kind_ratio: float = 0.0
    
    # Intent 비율
    contribute_intent_ratio: float = 0.0
    study_intent_ratio: float = 0.0
    evaluate_intent_ratio: float = 0.0
    
    # 실행 정보
    execution_time_sec: float = 0.0
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def compute_category_stats(results: List[BenchmarkResult], category: str) -> Dict[str, float]:
    """카테고리별 통계 계산"""
    filtered = [r for r in results if r.category == category and r.health_score is not None]
    
    if not filtered:
        return {}
    
    return {
        "count": len(filtered),
        "avg_health": sum(r.health_score for r in filtered) / len(filtered),
        "avg_onboarding": sum(r.onboarding_score or 0 for r in filtered) / len(filtered),
        "is_healthy_ratio": sum(1 for r in filtered if r.is_healthy) / len(filtered),
    }


# 별칭 (호환성)
def compute_stats(results: List[BenchmarkResult], category: str) -> Dict[str, float]:
    """compute_category_stats의 별칭"""
    return compute_category_stats(results, category)


def hash_result(result: Dict[str, Any]) -> str:
    """결과 dict의 해시값 계산 (재현성 검증용)"""
    # 정렬된 JSON으로 직렬화하여 해시
    serialized = json.dumps(result, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()


def save_results(results: List[Any], output_path: Path, name: str = "results"):
    """결과 저장"""
    output_path.mkdir(parents=True, exist_ok=True)
    
    data = [r.to_dict() if hasattr(r, 'to_dict') else asdict(r) for r in results]
    
    with open(output_path / f"{name}.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)


def print_pass_fail(passed: bool, detail: str = ""):
    """통과/실패 출력"""
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"\n  {status}" + (f" - {detail}" if detail else ""))



