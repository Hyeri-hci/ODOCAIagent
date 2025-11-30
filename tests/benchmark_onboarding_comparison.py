"""
온보딩 플랜 모듈 추가 전/후 LLM 답변 비교 벤치마크

비교 항목:
1. onboarding_plan 없이 LLM 요약만
2. onboarding_plan 포함하여 LLM 요약
"""
import json
import time
from typing import Dict, Any

from backend.agents.diagnosis.service import run_diagnosis
from backend.agents.diagnosis.llm_summarizer import summarize_diagnosis_repository


def run_comparison(owner: str, repo: str) -> Dict[str, Any]:
    """온보딩 플랜 유무에 따른 LLM 답변 비교"""
    
    print(f"\n{'='*60}")
    print(f"🔬 비교 대상: {owner}/{repo}")
    print(f"{'='*60}")
    
    # 1. 전체 진단 실행 (onboarding_plan 포함)
    start = time.time()
    result = run_diagnosis({"owner": owner, "repo": repo})
    diagnosis_time = time.time() - start
    
    scores = result["scores"]
    labels = result["labels"]
    onboarding_plan = result["onboarding_plan"]
    
    print(f"\n📊 기본 점수:")
    print(f"  - health_score: {scores['health_score']}")
    print(f"  - onboarding_score: {scores['onboarding_score']}")
    print(f"  - is_healthy: {scores['is_healthy']}")
    print(f"  - health_level: {labels['health_level']}")
    print(f"  - onboarding_level: {labels['onboarding_level']}")
    
    # 2. 기존 LLM 요약 (onboarding_plan 없이)
    result_without_plan = {
        "input": result["input"],
        "scores": result["scores"],
        "labels": result["labels"],
        "details": result["details"],
    }
    
    start = time.time()
    summary_without = summarize_diagnosis_repository(
        diagnosis_result=result_without_plan,
        user_level="beginner",
        language="ko",
    )
    time_without = time.time() - start
    
    # 3. 새로운 LLM 요약 (onboarding_plan 포함)
    result_with_plan = {
        "input": result["input"],
        "scores": result["scores"],
        "labels": result["labels"],
        "onboarding_plan": result["onboarding_plan"],
        "details": result["details"],
    }
    
    start = time.time()
    summary_with = summarize_diagnosis_repository(
        diagnosis_result=result_with_plan,
        user_level="beginner",
        language="ko",
    )
    time_with = time.time() - start
    
    # 4. 결과 출력
    print(f"\n{'─'*60}")
    print(f"📝 [A] onboarding_plan 없이 LLM 요약 ({time_without:.1f}초)")
    print(f"{'─'*60}")
    print(summary_without[:1500])
    if len(summary_without) > 1500:
        print(f"\n... (총 {len(summary_without)}자)")
    
    print(f"\n{'─'*60}")
    print(f"📝 [B] onboarding_plan 포함 LLM 요약 ({time_with:.1f}초)")
    print(f"{'─'*60}")
    print(summary_with[:1500])
    if len(summary_with) > 1500:
        print(f"\n... (총 {len(summary_with)}자)")
    
    print(f"\n{'─'*60}")
    print(f"📋 [C] 규칙 기반 onboarding_plan (v0)")
    print(f"{'─'*60}")
    print(f"  recommended_for_beginner: {onboarding_plan['recommended_for_beginner']}")
    print(f"  difficulty: {onboarding_plan['difficulty']}")
    print(f"  estimated_setup_time: {onboarding_plan['estimated_setup_time']}")
    print(f"\n  first_steps:")
    for i, step in enumerate(onboarding_plan['first_steps'], 1):
        print(f"    {i}. {step}")
    print(f"\n  risks:")
    if onboarding_plan['risks']:
        for risk in onboarding_plan['risks']:
            print(f"    - {risk}")
    else:
        print(f"    (없음)")
    
    # 5. 비교 분석
    print(f"\n{'='*60}")
    print(f"📈 비교 분석")
    print(f"{'='*60}")
    print(f"  진단 시간: {diagnosis_time:.1f}초")
    print(f"  요약(A) 시간: {time_without:.1f}초")
    print(f"  요약(B) 시간: {time_with:.1f}초")
    print(f"  요약(A) 길이: {len(summary_without)}자")
    print(f"  요약(B) 길이: {len(summary_with)}자")
    
    # 키워드 체크
    keywords_to_check = [
        ("온보딩", "onboarding/온보딩 언급"),
        ("first", "first steps 언급"),
        ("단계", "단계별 가이드"),
        ("good-first-issue", "good-first-issue 언급"),
        ("위험", "risks/위험 언급"),
        ("주의", "주의사항 언급"),
    ]
    
    print(f"\n  키워드 포함 여부:")
    for keyword, desc in keywords_to_check:
        in_a = "✓" if keyword.lower() in summary_without.lower() else "✗"
        in_b = "✓" if keyword.lower() in summary_with.lower() else "✗"
        print(f"    {desc}: A={in_a}, B={in_b}")
    
    return {
        "repo": f"{owner}/{repo}",
        "scores": scores,
        "labels": labels,
        "onboarding_plan": onboarding_plan,
        "summary_without_plan": summary_without,
        "summary_with_plan": summary_with,
        "time_without": time_without,
        "time_with": time_with,
    }


if __name__ == "__main__":
    # 테스트 대상 레포지토리
    repos = [
        ("Hyeri-hci", "OSSDoctor"),      # 건강한 프로젝트
        ("facebookarchive", "flux"),      # archived 프로젝트
    ]
    
    results = []
    for owner, repo in repos:
        try:
            result = run_comparison(owner, repo)
            results.append(result)
        except Exception as e:
            print(f"❌ {owner}/{repo} 실패: {e}")
    
    print(f"\n\n{'='*60}")
    print(f"🏁 최종 요약")
    print(f"{'='*60}")
    
    for r in results:
        print(f"\n{r['repo']}:")
        print(f"  health_level: {r['labels']['health_level']}")
        print(f"  recommended_for_beginner: {r['onboarding_plan']['recommended_for_beginner']}")
        print(f"  요약 길이 차이: {len(r['summary_with_plan']) - len(r['summary_without_plan'])}자")
