"""
실행 노드 (ReAct 패턴)
"""
from typing import Dict, Any
from ..state import SecurityAnalysisState
from ..tools import (
    analyze_dependencies,
    calculate_security_score,
    suggest_improvements
)


def execute_tools_node(state: SecurityAnalysisState) -> Dict[str, Any]:
    """
    실행 노드: 계획에 따라 도구를 실행

    Args:
        state: SecurityAnalysisState

    Returns:
        Dict: State 업데이트
    """
    plan = state.get("plan", [])
    iteration = state.get("iteration", 0)
    owner = state.get("owner")
    repository = state.get("repository")
    github_token = state.get("github_token")
    
    if iteration >= len(plan):
        return {
            "current_step": "execution_complete",
            "messages": ["모든 계획 단계를 완료했습니다."]
        }
    
    current_task = plan[iteration]
    print(f"\n[Step {iteration + 1}/{len(plan)}] {current_task}")
    print(f"{'─' * 60}")
    
    result_update = {}
    
    # 현재 작업에 따라 적절한 도구 실행
    task_lower = current_task.lower()
    
    try:
        # 1. 의존성 분석
        if "의존성" in task_lower and "분석" in task_lower:
            print("[THINK] Thought: 레포지토리의 의존성을 분석해야 합니다.")
            print("[ACTION] Action: analyze_dependencies 실행")
            
            result = analyze_dependencies.invoke({
                "owner": owner,
                "repo": repository,
                "github_token": github_token
            })
            
            if result.get("success"):
                print(f"[OK] Observation: {result.get('total_dependencies')} 개의 의존성 발견")
                result_update = {
                    "dependencies": result,
                    "dependency_count": result.get("total_dependencies", 0),
                    "lock_files_found": result.get("summary", {}).get("lock_files", []),
                    "messages": [f"의존성 분석 완료: {result.get('total_dependencies')}개 발견"]
                }
            else:
                print(f"[ERROR] Error: {result.get('error', 'Unknown error')}")
                result_update = {
                    "errors": [f"의존성 분석 실패: {result.get('error')}"],
                    "messages": ["의존성 분석 중 오류 발생"]
                }
        
        # 2. 보안 점수 계산
        elif "보안" in task_lower and "점수" in task_lower:
            dependencies = state.get("dependencies")
            if not dependencies:
                print("[WARNING]  Warning: 의존성 데이터가 없습니다. 먼저 의존성 분석을 실행하세요.")
                result_update = {
                    "warnings": ["의존성 데이터 없음"],
                    "messages": ["보안 점수 계산을 건너뜁니다."]
                }
            else:
                print("[THINK] Thought: 의존성 데이터를 바탕으로 보안 점수를 계산합니다.")
                print("[ACTION] Action: calculate_security_score 실행")
                
                result = calculate_security_score.invoke({
                    "analysis_result": dependencies,
                    "vulnerability_result": None
                })
                
                if result.get("success"):
                    score = result.get("score", 0)
                    grade = result.get("grade", "N/A")
                    print(f"[OK] Observation: 보안 점수 {score}/100 (등급: {grade})")
                    result_update = {
                        "security_score": result,
                        "security_grade": grade,
                        "messages": [f"보안 점수 계산 완료: {grade} ({score}/100)"]
                    }
                else:
                    print(f"[ERROR] Error: {result.get('error')}")
                    result_update = {
                        "errors": [f"보안 점수 계산 실패: {result.get('error')}"],
                        "messages": ["보안 점수 계산 중 오류 발생"]
                    }
        
        # 3. 개선 사항 제안
        elif "개선" in task_lower or "제안" in task_lower:
            dependencies = state.get("dependencies")
            security_score = state.get("security_score")
            
            if not dependencies:
                print("[WARNING]  Warning: 의존성 데이터가 없습니다.")
                result_update = {
                    "warnings": ["의존성 데이터 없음"],
                    "messages": ["개선 사항 제안을 건너뜁니다."]
                }
            else:
                print("[THINK] Thought: 분석 결과를 바탕으로 개선 사항을 제안합니다.")
                print("[ACTION] Action: suggest_improvements 실행")
                
                result = suggest_improvements.invoke({
                    "analysis_result": dependencies,
                    "vulnerability_result": None,
                    "security_score": security_score
                })
                
                if result.get("success"):
                    suggestions = result.get("suggestions", [])
                    print(f"[OK] Observation: {len(suggestions)}개의 개선 사항 도출")
                    for i, suggestion in enumerate(suggestions[:3], 1):  # 처음 3개만 출력
                        print(f"    {i}. {suggestion}")
                    result_update = {
                        "recommendations": suggestions,
                        "messages": [f"개선 사항 제안 완료: {len(suggestions)}개"]
                    }
                else:
                    print(f"[ERROR] Error: {result.get('error')}")
                    result_update = {
                        "errors": [f"개선 사항 제안 실패: {result.get('error')}"],
                        "messages": ["개선 사항 제안 중 오류 발생"]
                    }
        
        # 4. 레포트 생성 (다음 노드에서 처리)
        elif "레포트" in task_lower:
            print("[THINK] Thought: 레포트 생성은 별도 노드에서 처리합니다.")
            result_update = {
                "current_step": "ready_for_report",
                "messages": ["레포트 생성 준비 완료"]
            }
        
        else:
            print(f"[WARNING]  Unknown task: {current_task}")
            result_update = {
                "warnings": [f"Unknown task: {current_task}"],
                "messages": [f"작업을 건너뜁니다: {current_task}"]
            }
    
    except Exception as e:
        print(f"[ERROR] Exception: {str(e)}")
        result_update = {
            "errors": [f"실행 중 오류: {str(e)}"],
            "messages": [f"오류 발생: {str(e)}"]
        }
    
    print()  # 빈 줄
    
    # iteration 증가
    result_update["iteration"] = iteration + 1
    result_update["current_step"] = "executing"
    
    return result_update
