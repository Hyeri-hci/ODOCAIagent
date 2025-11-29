"""
온보딩 플랜 모듈 효과 평가 벤치마크

정량적 평가:
- 응답 시간 (초)
- 응답 길이 (자)
- 키워드 포함률 (%)
- 구조화 점수 (0-100)

정성적 평가:
- LLM 기반 품질 평가 (명확성, 실행가능성, 초보자 친화도)
"""
import json
import time
from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Optional

from backend.agents.diagnosis.service import run_diagnosis
from backend.agents.diagnosis.llm_summarizer import summarize_diagnosis_repository
from backend.llm.base import ChatMessage, ChatRequest
from backend.llm.factory import fetch_llm_client


@dataclass
class QuantitativeMetrics:
    """정량적 평가 지표"""
    response_time_sec: float
    response_length: int
    keyword_coverage: float  # 0-100%
    structure_score: float   # 0-100
    actionable_steps_count: int
    risk_mentions_count: int


@dataclass
class QualitativeMetrics:
    """정성적 평가 지표 (LLM 평가)"""
    clarity_score: int        # 1-5
    actionability_score: int  # 1-5
    beginner_friendly: int    # 1-5
    completeness: int         # 1-5
    overall_score: float      # 평균
    evaluation_reason: str


@dataclass
class EvaluationResult:
    """통합 평가 결과"""
    repo: str
    condition: str  # "without_plan" | "with_plan"
    quantitative: QuantitativeMetrics
    qualitative: Optional[QualitativeMetrics]
    summary_preview: str


# 평가용 키워드 목록
EVALUATION_KEYWORDS = [
    # 온보딩 관련
    ("온보딩", "onboarding"),
    ("시작", "start"),
    ("설치", "install"),
    ("환경", "environment"),
    # 기여 관련
    ("기여", "contribut"),
    ("PR", "pull request"),
    ("이슈", "issue"),
    ("good-first-issue", "good first issue"),
    # 위험/주의 관련
    ("주의", "warning"),
    ("위험", "risk"),
    ("어려", "difficult"),
    # 실행 가능한 조언
    ("단계", "step"),
    ("먼저", "first"),
    ("다음", "next"),
    ("확인", "check"),
]


def compute_keyword_coverage(text: str) -> float:
    """키워드 포함률 계산 (0-100)"""
    text_lower = text.lower()
    found = 0
    for kr, en in EVALUATION_KEYWORDS:
        if kr in text_lower or en in text_lower:
            found += 1
    return (found / len(EVALUATION_KEYWORDS)) * 100


def compute_structure_score(text: str) -> float:
    """구조화 점수 계산 (0-100)"""
    score = 0
    
    # 번호 매기기 (1., 2., 3., ...)
    import re
    numbered_items = len(re.findall(r'^\d+\.', text, re.MULTILINE))
    score += min(numbered_items * 5, 25)
    
    # 섹션 구분 (제목, 소제목)
    sections = len(re.findall(r'^#+\s|^[가-힣]+\s*[:：]', text, re.MULTILINE))
    score += min(sections * 5, 25)
    
    # 단락 구분
    paragraphs = text.count('\n\n')
    score += min(paragraphs * 3, 25)
    
    # 구체적 파일/경로 언급
    file_mentions = len(re.findall(r'README|CONTRIBUTING|package\.json|requirements\.txt|\.md|\.json', text, re.IGNORECASE))
    score += min(file_mentions * 5, 25)
    
    return min(score, 100)


def count_actionable_steps(text: str) -> int:
    """실행 가능한 단계 수 카운트"""
    import re
    # 번호 매기기된 항목
    numbered = len(re.findall(r'^\d+\.', text, re.MULTILINE))
    # 동사로 끝나는 문장 (한국어: ~한다, ~해라 등)
    action_verbs = len(re.findall(r'[다라요]\.', text))
    return max(numbered, action_verbs // 2)


def count_risk_mentions(text: str) -> int:
    """위험/주의사항 언급 수"""
    risk_keywords = ['주의', '위험', '어려', '느릴', '없어', '부족', '비활성', '유지보수']
    count = 0
    text_lower = text.lower()
    for kw in risk_keywords:
        count += text_lower.count(kw)
    return count


def evaluate_qualitative_with_llm(
    summary_a: str,
    summary_b: str,
    repo_name: str,
) -> Dict[str, QualitativeMetrics]:
    """LLM을 사용한 정성적 평가"""
    
    system_prompt = """당신은 오픈소스 프로젝트 문서 품질 평가 전문가입니다.
두 개의 프로젝트 요약문(A, B)을 비교 평가해주세요.

각 요약문에 대해 다음 기준으로 1-5점 척도로 평가하세요:
1. clarity_score: 설명이 명확하고 이해하기 쉬운가?
2. actionability_score: 초보자가 바로 따라할 수 있는 구체적인 액션이 있는가?
3. beginner_friendly: 초보 개발자에게 친절하고 접근하기 쉬운가?
4. completeness: 필요한 정보가 빠짐없이 포함되어 있는가?

반드시 아래 JSON 형식으로만 응답하세요:
{
  "A": {
    "clarity_score": 1-5,
    "actionability_score": 1-5,
    "beginner_friendly": 1-5,
    "completeness": 1-5,
    "reason": "A에 대한 평가 이유 (1-2문장)"
  },
  "B": {
    "clarity_score": 1-5,
    "actionability_score": 1-5,
    "beginner_friendly": 1-5,
    "completeness": 1-5,
    "reason": "B에 대한 평가 이유 (1-2문장)"
  },
  "winner": "A 또는 B",
  "comparison": "전체 비교 요약 (1-2문장)"
}"""

    user_prompt = f"""프로젝트: {repo_name}

[요약문 A] (onboarding_plan 없이 생성)
{summary_a[:2000]}

[요약문 B] (onboarding_plan 포함하여 생성)
{summary_b[:2000]}

두 요약문을 비교 평가해주세요."""

    messages = [
        ChatMessage(role="system", content=system_prompt),
        ChatMessage(role="user", content=user_prompt),
    ]

    try:
        client = fetch_llm_client()
        request = ChatRequest(messages=messages, max_tokens=800, temperature=0.1)
        response = client.chat(request)
        
        raw = response.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        
        data = json.loads(raw)
        
        results = {}
        for key, label in [("A", "without_plan"), ("B", "with_plan")]:
            scores = data.get(key, {})
            clarity = scores.get("clarity_score", 3)
            action = scores.get("actionability_score", 3)
            beginner = scores.get("beginner_friendly", 3)
            complete = scores.get("completeness", 3)
            overall = (clarity + action + beginner + complete) / 4
            
            results[label] = QualitativeMetrics(
                clarity_score=clarity,
                actionability_score=action,
                beginner_friendly=beginner,
                completeness=complete,
                overall_score=round(overall, 2),
                evaluation_reason=scores.get("reason", ""),
            )
        
        results["comparison"] = data.get("comparison", "")
        results["winner"] = data.get("winner", "")
        
        return results
        
    except Exception as e:
        print(f"  LLM 평가 실패: {e}")
        return {}


def run_full_evaluation(owner: str, repo: str, run_qualitative: bool = True) -> Dict[str, Any]:
    """전체 평가 실행"""
    
    print(f"\n{'='*70}")
    print(f"평가 대상: {owner}/{repo}")
    print(f"{'='*70}")
    
    # 1. 진단 실행
    print("\n[1/4] 진단 실행 중...")
    start = time.time()
    result = run_diagnosis({"owner": owner, "repo": repo})
    diagnosis_time = time.time() - start
    print(f"  완료 ({diagnosis_time:.1f}초)")
    
    scores = result["scores"]
    labels = result["labels"]
    onboarding_plan = result["onboarding_plan"]
    
    # 2. 요약 A: onboarding_plan 없이
    print("\n[2/4] 요약 A 생성 중 (onboarding_plan 없이)...")
    result_without = {
        "input": result["input"],
        "scores": result["scores"],
        "labels": result["labels"],
        "details": result["details"],
    }
    
    start = time.time()
    summary_a = summarize_diagnosis_repository(result_without, "beginner", "ko")
    time_a = time.time() - start
    print(f"  완료 ({time_a:.1f}초, {len(summary_a)}자)")
    
    # 3. 요약 B: onboarding_plan 포함
    print("\n[3/4] 요약 B 생성 중 (onboarding_plan 포함)...")
    result_with = {
        "input": result["input"],
        "scores": result["scores"],
        "labels": result["labels"],
        "onboarding_plan": result["onboarding_plan"],
        "details": result["details"],
    }
    
    start = time.time()
    summary_b = summarize_diagnosis_repository(result_with, "beginner", "ko")
    time_b = time.time() - start
    print(f"  완료 ({time_b:.1f}초, {len(summary_b)}자)")
    
    # 4. 정량적 평가
    print("\n[4/4] 정량적 평가 계산 중...")
    
    quant_a = QuantitativeMetrics(
        response_time_sec=round(time_a, 2),
        response_length=len(summary_a),
        keyword_coverage=round(compute_keyword_coverage(summary_a), 1),
        structure_score=round(compute_structure_score(summary_a), 1),
        actionable_steps_count=count_actionable_steps(summary_a),
        risk_mentions_count=count_risk_mentions(summary_a),
    )
    
    quant_b = QuantitativeMetrics(
        response_time_sec=round(time_b, 2),
        response_length=len(summary_b),
        keyword_coverage=round(compute_keyword_coverage(summary_b), 1),
        structure_score=round(compute_structure_score(summary_b), 1),
        actionable_steps_count=count_actionable_steps(summary_b),
        risk_mentions_count=count_risk_mentions(summary_b),
    )
    
    # 5. 정성적 평가 (LLM)
    qual_results = {}
    if run_qualitative:
        print("\n[추가] 정성적 평가 중 (LLM)...")
        qual_results = evaluate_qualitative_with_llm(
            summary_a, summary_b, f"{owner}/{repo}"
        )
        print("  완료")
    
    # 결과 정리
    eval_a = EvaluationResult(
        repo=f"{owner}/{repo}",
        condition="without_plan",
        quantitative=quant_a,
        qualitative=qual_results.get("without_plan"),
        summary_preview=summary_a[:500],
    )
    
    eval_b = EvaluationResult(
        repo=f"{owner}/{repo}",
        condition="with_plan",
        quantitative=quant_b,
        qualitative=qual_results.get("with_plan"),
        summary_preview=summary_b[:500],
    )
    
    return {
        "repo": f"{owner}/{repo}",
        "scores": scores,
        "labels": labels,
        "onboarding_plan": onboarding_plan,
        "evaluation": {
            "without_plan": asdict(eval_a),
            "with_plan": asdict(eval_b),
        },
        "comparison": qual_results.get("comparison", ""),
        "winner": qual_results.get("winner", ""),
        "summary_a": summary_a,
        "summary_b": summary_b,
    }


def print_comparison_table(results: List[Dict[str, Any]]):
    """비교 결과 테이블 출력"""
    
    print(f"\n\n{'='*80}")
    print("정량적 평가 비교")
    print(f"{'='*80}")
    
    headers = ["Repo", "조건", "시간(초)", "길이", "키워드%", "구조점수", "액션수", "위험언급"]
    print(f"{'|'.join(f'{h:^12}' for h in headers)}")
    print("-" * 100)
    
    for r in results:
        repo = r["repo"].split("/")[1][:10]
        
        for cond in ["without_plan", "with_plan"]:
            e = r["evaluation"][cond]
            q = e["quantitative"]
            cond_label = "A(없음)" if cond == "without_plan" else "B(포함)"
            
            row = [
                repo if cond == "without_plan" else "",
                cond_label,
                f"{q['response_time_sec']:.1f}",
                str(q['response_length']),
                f"{q['keyword_coverage']:.0f}%",
                f"{q['structure_score']:.0f}",
                str(q['actionable_steps_count']),
                str(q['risk_mentions_count']),
            ]
            print(f"{'|'.join(f'{v:^12}' for v in row)}")
        print("-" * 100)
    
    # 정성적 평가 결과
    print(f"\n\n{'='*80}")
    print("정성적 평가 비교 (LLM 평가, 1-5점)")
    print(f"{'='*80}")
    
    headers2 = ["Repo", "조건", "명확성", "실행가능", "초보친화", "완결성", "종합", "승자"]
    print(f"{'|'.join(f'{h:^10}' for h in headers2)}")
    print("-" * 90)
    
    for r in results:
        repo = r["repo"].split("/")[1][:10]
        winner = r.get("winner", "")
        
        for cond in ["without_plan", "with_plan"]:
            e = r["evaluation"][cond]
            q = e.get("qualitative")
            cond_label = "A(없음)" if cond == "without_plan" else "B(포함)"
            
            if q:
                is_winner = "V" if (cond == "without_plan" and winner == "A") or (cond == "with_plan" and winner == "B") else ""
                row = [
                    repo if cond == "without_plan" else "",
                    cond_label,
                    str(q['clarity_score']),
                    str(q['actionability_score']),
                    str(q['beginner_friendly']),
                    str(q['completeness']),
                    f"{q['overall_score']:.2f}",
                    is_winner,
                ]
            else:
                row = [repo if cond == "without_plan" else "", cond_label, "-", "-", "-", "-", "-", ""]
            
            print(f"{'|'.join(f'{v:^10}' for v in row)}")
        print("-" * 90)
    
    # 종합 분석
    print(f"\n\n{'='*80}")
    print("종합 분석")
    print(f"{'='*80}")
    
    for r in results:
        print(f"\n{r['repo']}:")
        print(f"  승자: {r.get('winner', 'N/A')}")
        print(f"  비교: {r.get('comparison', 'N/A')}")
        
        # 정량적 차이 요약
        ea = r["evaluation"]["without_plan"]["quantitative"]
        eb = r["evaluation"]["with_plan"]["quantitative"]
        
        print(f"\n  정량적 차이:")
        print(f"    - 키워드 포함률: A={ea['keyword_coverage']:.0f}% -> B={eb['keyword_coverage']:.0f}% ({eb['keyword_coverage']-ea['keyword_coverage']:+.0f}%)")
        print(f"    - 구조 점수: A={ea['structure_score']:.0f} -> B={eb['structure_score']:.0f} ({eb['structure_score']-ea['structure_score']:+.0f})")
        print(f"    - 액션 수: A={ea['actionable_steps_count']} -> B={eb['actionable_steps_count']} ({eb['actionable_steps_count']-ea['actionable_steps_count']:+d})")


def main():
    """메인 실행"""
    repos = [
        ("Hyeri-hci", "OSSDoctor"),      # 건강한 프로젝트
        ("facebookarchive", "flux"),      # archived 프로젝트
    ]
    
    all_results = []
    
    for owner, repo in repos:
        try:
            result = run_full_evaluation(owner, repo, run_qualitative=True)
            all_results.append(result)
        except Exception as e:
            print(f"ERROR: {owner}/{repo} - {e}")
    
    # 비교 테이블 출력
    print_comparison_table(all_results)
    
    # JSON 저장
    output_file = "test/benchmark_results.json"
    with open(output_file, "w", encoding="utf-8") as f:
        # summary_a, summary_b는 너무 길어서 제외
        save_results = []
        for r in all_results:
            save_r = {k: v for k, v in r.items() if k not in ["summary_a", "summary_b"]}
            save_results.append(save_r)
        json.dump(save_results, f, ensure_ascii=False, indent=2)
    print(f"\n결과 저장: {output_file}")


if __name__ == "__main__":
    main()
