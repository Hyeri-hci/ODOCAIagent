# test/benchmark_readme_summary.py
"""
README 요약 방식 성능 비교 벤치마크

방식 1: 통합 요약만 (현재) - LLM 1회
방식 2: 카테고리별 요약 + 통합 (이전) - LLM 5회
"""
import os
import sys
import time
import traceback
from typing import Dict, List, Tuple, Optional

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.agents.diagnosis.tools.readme_sections import split_readme_into_sections
from backend.agents.diagnosis.tools.llm_summarizer import (
    generate_readme_unified_summary,
    summarize_readme_category_for_embedding,
    ReadmeUnifiedSummary,
)


def method1_unified_only(category_raw_texts: Dict[str, str]) -> Tuple[Optional[ReadmeUnifiedSummary], float]:
    """
    방식 1: raw_text → 통합 요약 (LLM 1회)
    현재 적용된 방식
    """
    start = time.perf_counter()
    try:
        result = generate_readme_unified_summary(category_raw_texts)
        elapsed = time.perf_counter() - start
        return result, elapsed
    except Exception as e:
        elapsed = time.perf_counter() - start
        print(f"\n  [ERROR] 방식 1 실패: {e}")
        return None, elapsed


def method2_per_category_then_unified(category_raw_texts: Dict[str, str]) -> Tuple[Optional[ReadmeUnifiedSummary], Dict[str, str], float]:
    """
    방식 2: raw_text → 카테고리별 요약 (LLM 4회) → 통합 요약 (LLM 1회)
    이전 방식
    """
    start = time.perf_counter()
    
    try:
        # 카테고리별 semantic_summary 생성
        category_summaries: Dict[str, str] = {}
        for cat_name, raw_text in category_raw_texts.items():
            if raw_text and raw_text.strip():
                print(f"    - {cat_name} 요약 중...", end=" ", flush=True)
                cat_start = time.perf_counter()
                try:
                    summary = summarize_readme_category_for_embedding(
                        category=cat_name,
                        text=raw_text[:2000],
                    )
                    category_summaries[cat_name] = summary or ""
                    print(f"{time.perf_counter() - cat_start:.2f}초")
                except Exception as e:
                    print(f"실패: {e}")
                    category_summaries[cat_name] = ""
        
        # 통합 요약 생성 (카테고리별 요약 기반)
        print(f"    - 통합 요약 중...", end=" ", flush=True)
        unified_start = time.perf_counter()
        unified = generate_readme_unified_summary(category_summaries)
        print(f"{time.perf_counter() - unified_start:.2f}초")
        
        elapsed = time.perf_counter() - start
        return unified, category_summaries, elapsed
        
    except Exception as e:
        elapsed = time.perf_counter() - start
        print(f"\n  [ERROR] 방식 2 실패: {e}")
        return None, {}, elapsed


def run_benchmark(readme_text: str, runs: int = 1) -> None:
    """벤치마크 실행"""
    print("=" * 60)
    print("README 요약 방식 성능 비교")
    print("=" * 60)
    
    # 섹션 분리 및 카테고리별 raw_text 추출 (간단 시뮬레이션)
    sections = split_readme_into_sections(readme_text)
    
    # 간단히 첫 4개 섹션을 WHAT, WHY, HOW, CONTRIBUTING으로 매핑
    category_raw_texts: Dict[str, str] = {}
    target_cats = ["WHAT", "WHY", "HOW", "CONTRIBUTING"]
    
    for i, cat in enumerate(target_cats):
        if i < len(sections):
            category_raw_texts[cat] = sections[i].content[:1500]
        else:
            category_raw_texts[cat] = ""
    
    print(f"\n입력 섹션 수: {len(sections)}")
    print(f"카테고리별 텍스트 길이:")
    for cat, text in category_raw_texts.items():
        print(f"  - {cat}: {len(text)} chars")
    
    # 방식 1 벤치마크
    print("\n" + "-" * 60)
    print("방식 1: 통합 요약만 (LLM 1회)")
    print("-" * 60)
    
    times1: List[float] = []
    result1 = None
    for i in range(runs):
        print(f"  Run {i+1}/{runs}...", end=" ", flush=True)
        result1, elapsed1 = method1_unified_only(category_raw_texts)
        times1.append(elapsed1)
        print(f"{elapsed1:.2f}초")
    
    avg1 = sum(times1) / len(times1) if times1 else 0
    if result1:
        print(f"\n  평균 시간: {avg1:.2f}초")
        print(f"  결과 (영어): {result1.summary_en[:150]}...")
        print(f"  결과 (한국어): {result1.summary_ko[:150]}...")
    else:
        print(f"\n  실패 - 평균 시간: {avg1:.2f}초")
    
    # 방식 2 벤치마크
    print("\n" + "-" * 60)
    print("방식 2: 카테고리별 요약 + 통합 (LLM 5회)")
    print("-" * 60)
    
    times2: List[float] = []
    result2 = None
    cat_summaries: Dict[str, str] = {}
    for i in range(runs):
        print(f"  Run {i+1}/{runs}...")
        result2, cat_summaries, elapsed2 = method2_per_category_then_unified(category_raw_texts)
        times2.append(elapsed2)
        print(f"    총 시간: {elapsed2:.2f}초")
    
    avg2 = sum(times2) / len(times2) if times2 else 0
    if result2:
        print(f"\n  평균 시간: {avg2:.2f}초")
        print(f"  카테고리별 요약:")
        for cat, summary in cat_summaries.items():
            if summary:
                print(f"    - {cat}: {summary[:80]}...")
        print(f"  통합 결과 (영어): {result2.summary_en[:150]}...")
        print(f"  통합 결과 (한국어): {result2.summary_ko[:150]}...")
    else:
        print(f"\n  실패 - 평균 시간: {avg2:.2f}초")
    
    # 비교 결과
    if avg1 > 0 and avg2 > 0:
        print("\n" + "=" * 60)
        print("비교 결과")
        print("=" * 60)
        print(f"  방식 1 (통합만):     {avg1:.2f}초 | LLM 1회")
        print(f"  방식 2 (카테고리별): {avg2:.2f}초 | LLM 5회")
        print(f"  속도 차이: {avg2 - avg1:.2f}초 ({avg2/avg1:.1f}x 느림)")
        print(f"  시간 절감: {(1 - avg1/avg2) * 100:.0f}%")


if __name__ == "__main__":
    from backend.agents.diagnosis.tools.readme_loader import fetch_readme_content
    
    # 테스트할 저장소
    test_repos = [
        ("Hyeri-hci", "OSSDoctor"),
        # ("microsoft", "vscode"),
        # ("facebook", "react"),
    ]
    
    for owner, repo in test_repos:
        print(f"\n{'#' * 60}")
        print(f"# 테스트 저장소: {owner}/{repo}")
        print(f"{'#' * 60}")
        
        readme_text = fetch_readme_content(owner, repo)
        if not readme_text:
            print("README를 가져올 수 없습니다.")
            continue
        
        print(f"README 길이: {len(readme_text)} chars")
        run_benchmark(readme_text, runs=1)
