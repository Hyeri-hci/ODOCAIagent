"""
Security Analysis Agent Main Class
"""
from typing import Dict, Any, Optional
from .state import create_initial_state, SecurityAnalysisState
from .graph import create_security_analysis_graph, visualize_graph


class SecurityAnalysisAgent:
    """보안 분석 에이전트"""
    
    def __init__(
        self,
        github_token: Optional[str] = None,
        max_iterations: int = 10,
        verbose: bool = True
    ):
        """
        에이전트 초기화

        Args:
            github_token: GitHub Personal Access Token
            max_iterations: 최대 반복 횟수
            verbose: 상세 출력 여부
        """
        self.github_token = github_token
        self.max_iterations = max_iterations
        self.verbose = verbose
        self.graph = create_security_analysis_graph()
    
    def analyze(
        self,
        owner: str,
        repository: str,
        github_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        레포지토리 보안 분석 실행

        Args:
            owner: 레포지토리 소유자
            repository: 레포지토리 이름
            github_token: GitHub Personal Access Token (옵션, 인스턴스 토큰 우선)

        Returns:
            Dict: 분석 결과
                - owner: str
                - repository: str
                - dependency_count: int
                - security_score: Dict
                - security_grade: str
                - recommendations: List[str]
                - report: str
                - errors: List[str]
        """
        # 토큰 우선순위: 매개변수 > 인스턴스 변수
        token = github_token or self.github_token
        
        # 초기 State 생성
        initial_state = create_initial_state(
            owner=owner,
            repository=repository,
            github_token=token,
            max_iterations=self.max_iterations
        )
        
        if self.verbose:
            print("\n" + "="*60)
            print("Security Analysis Agent")
            print("="*60)
        
        try:
            # 그래프 실행
            final_state = self.graph.invoke(initial_state)
            
            # 결과 추출
            result = {
                "success": True,
                "owner": owner,
                "repository": repository,
                "dependency_count": final_state.get("dependency_count", 0),
                "security_score": final_state.get("security_score"),
                "security_grade": final_state.get("security_grade", ""),
                "recommendations": final_state.get("recommendations", []),
                "report": final_state.get("report"),
                "errors": final_state.get("errors", []),
                "warnings": final_state.get("warnings", []),
                "final_result": final_state.get("final_result")
            }
            
            if self.verbose:
                print("\n" + "="*60)
                print("[OK] Analysis Complete")
                print("="*60 + "\n")
            
            return result
            
        except Exception as e:
            if self.verbose:
                print(f"\n[ERROR] Error during analysis: {str(e)}\n")
            
            return {
                "success": False,
                "error": str(e),
                "owner": owner,
                "repository": repository,
                "dependency_count": 0,
                "security_score": None,
                "security_grade": "F",
                "recommendations": [],
                "report": None,
                "errors": [str(e)]
            }
    
    def visualize(self):
        """그래프 구조 시각화"""
        visualize_graph()


# 편의 함수
def run_security_analysis(
    owner: str,
    repository: str,
    github_token: Optional[str] = None,
    max_iterations: int = 10
) -> Dict[str, Any]:
    """
    보안 분석 실행 (편의 함수)

    Args:
        owner: 레포지토리 소유자
        repository: 레포지토리 이름
        github_token: GitHub Personal Access Token
        max_iterations: 최대 반복 횟수

    Returns:
        Dict: 분석 결과
    """
    agent = SecurityAnalysisAgent(
        github_token=github_token,
        max_iterations=max_iterations
    )
    return agent.analyze(owner, repository)
