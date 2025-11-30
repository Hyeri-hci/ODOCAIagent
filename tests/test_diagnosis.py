"""
Diagnosis 모듈 통합 테스트 Runner

모든 Diagnosis 관련 유닛 테스트를 실행합니다.

테스트 파일:
- test_chaoss_metrics.py: CHAOSS 메트릭 (커밋 활동 분석)
- test_diagnosis_labels.py: 진단 라벨 (건강/온보딩 레벨)
- test_onboarding_plan.py: 온보딩 플랜 생성
- test_onboarding_tasks.py: 온보딩 Task 추천
- test_onboarding_recommender_llm.py: LLM 보강 로직

실행 방법:
    python tests/test_diagnosis.py           # 전체 테스트
    python tests/test_diagnosis.py --quick   # 빠른 테스트 (API 호출 제외)
    pytest tests/test_*.py -v                # pytest로 전체 실행
"""

import sys
import subprocess
from pathlib import Path

# 프로젝트 루트
ROOT = Path(__file__).parent.parent
TEST_DIR = Path(__file__).parent


def run_pytest(test_files: list[str], verbose: bool = True, skip_slow: bool = False) -> int:
    """pytest 실행"""
    args = ["pytest"]
    
    if verbose:
        args.append("-v")
    
    if skip_slow:
        args.extend(["-m", "not slow"])
    
    args.extend(test_files)
    
    print(f"실행: {' '.join(args)}")
    print("=" * 70)
    
    result = subprocess.run(args, cwd=ROOT)
    return result.returncode


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Diagnosis 모듈 테스트 Runner")
    parser.add_argument("--quick", action="store_true", help="빠른 테스트만 실행 (API 호출 제외)")
    parser.add_argument("--file", type=str, help="특정 파일만 테스트")
    args = parser.parse_args()
    
    # Diagnosis 관련 테스트 파일들
    diagnosis_tests = [
        str(TEST_DIR / "test_chaoss_metrics.py"),
        str(TEST_DIR / "test_diagnosis_labels.py"),
        str(TEST_DIR / "test_onboarding_plan.py"),
        str(TEST_DIR / "test_onboarding_tasks.py"),
        str(TEST_DIR / "test_onboarding_recommender_llm.py"),
    ]
    
    if args.file:
        # 특정 파일만 테스트
        test_files = [str(TEST_DIR / args.file)]
    else:
        test_files = diagnosis_tests
    
    print("\n" + "=" * 70)
    print("Diagnosis 모듈 테스트 시작")
    print("=" * 70)
    print(f"테스트 파일 수: {len(test_files)}")
    print()
    
    exit_code = run_pytest(test_files, skip_slow=args.quick)
    
    if exit_code == 0:
        print("\n" + "=" * 70)
        print("모든 테스트 통과!")
        print("=" * 70)
    else:
        print("\n" + "=" * 70)
        print("일부 테스트 실패. 위 결과를 확인하세요.")
        print("=" * 70)
    
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
