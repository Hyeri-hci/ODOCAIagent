# core/github/fetcher.py

from typing import List, Dict, Optional
from adapters.github_client import github_instance as client
from core.github.schema import ParsedIssue, ParsedPullRequest, ParsedCommit, ParsedRepo
from core.github.parser import GitHubParser

class GitHubDetailFetcher:
    """
    [Live Data Verification]
    DB에 저장된 데이터 외에, '현재 시점'의 살아있는 데이터가 필요할 때 사용하는 Fetcher.
    
    GitHubClient(PyGithub)를 통해 객체를 받아오고,
    GitHubParser를 통해 내부 Schema로 변환하여 반환합니다.
    
    주요 용도:
    - 오래된 프로젝트(Last Push > 1년)의 생존 여부 확인
    - 이슈/PR 탭의 실제 활성도 정밀 검증
    """

    def __init__(self):
        self.client = client

    def fetch_recent_issues(self, owner: str, name: str, limit: int = 10) -> List[ParsedIssue]:
        """
        최근 Open Issue 목록을 가져옵니다.
        
        [주의] GitHub API의 get_issues는 PR도 포함해서 내려줍니다.
        따라서 넉넉하게 가져온 뒤(buffer), 순수 Issue만 필터링합니다.
        """
        try:
            # 1. Repo 객체 획득 (API 호출 최소화)
            repo = self.client.get_repo(f"{owner}/{name}")
            
            # 2. API 호출 (Pagination 자동 처리)
            # PR이 섞여 있을 수 있으므로 요청한 limit보다 3배수로 넉넉히 가져와서 검사
            buffer_limit = limit * 3
            raw_issues_iterator = repo.get_issues(state='open', sort='created', direction='desc')
            
            real_issues = []
            for item in raw_issues_iterator:
                # 목표 수량을 채우면 중단
                if len(real_issues) >= limit:
                    break
                
                # buffer_limit만큼 확인했는데도 못 채웠으면 중단 (무한 루프 방지)
                # (PyGithub Iterator는 인덱싱이 안되므로 카운트로 체크하거나 슬라이싱 사용)
                # 여기서는 Iterator 특성상 loop 내에서 체크
                
                # pull_request 속성이 없거나 None이어야 진짜 Issue
                if not item.pull_request:
                    real_issues.append(item)
            
            # 3. Parser에게 변환 위임
            return GitHubParser.parse_issues(real_issues)
            
        except Exception as e:
            print(f"⚠️ [Fetcher] Failed to fetch issues for {owner}/{name}: {e}")
            return []

    def fetch_recent_prs(self, owner: str, name: str, limit: int = 10) -> List[ParsedPullRequest]:
        """
        최근 Open PR 목록을 가져옵니다.
        """
        try:
            repo = self.client.get_repo(f"{owner}/{name}")
            
            # API 호출: PyGithub의 슬라이싱 기능을 사용하여 딱 필요한 만큼만 요청
            raw_prs = repo.get_pulls(state='open', sort='created', direction='desc')[:limit]
            
            return GitHubParser.parse_pull_requests(raw_prs)

        except Exception as e:
            print(f"⚠️ [Fetcher] Failed to fetch PRs for {owner}/{name}: {e}")
            return []

    def fetch_recent_commits(self, owner: str, name: str, limit: int = 10) -> List[ParsedCommit]:
        """
        최근 Commit 목록을 가져옵니다. (기본 브랜치 기준)
        
        [Tip] 커밋 데이터는 무겁기 때문에 limit을 작게(5~10) 유지하는 것이 좋습니다.
        """
        try:
            repo = self.client.get_repo(f"{owner}/{name}")
            
            # API 호출
            raw_commits = repo.get_commits()[:limit]
            
            return GitHubParser.parse_commits(raw_commits)

        except Exception as e:
            print(f"⚠️ [Fetcher] Failed to fetch commits for {owner}/{name}: {e}")
            return []

    def fetch_all_details(self, repo: ParsedRepo, limits: Dict[str, int] = None) -> Dict[str, List]:
        """
        (Optional) 종합 검진용: 이슈, PR, 커밋을 한 번에 가져옵니다.
        Agent가 프로젝트의 전반적인 건강 상태를 판단할 때 유용합니다.
        """
        if limits is None:
            limits = {"issues": 5, "prs": 5, "commits": 5}

        return {
            "issues": self.fetch_recent_issues(repo.owner, repo.name, limits.get("issues", 5)),
            "prs": self.fetch_recent_prs(repo.owner, repo.name, limits.get("prs", 5)),
            "commits": self.fetch_recent_commits(repo.owner, repo.name, limits.get("commits", 5))
        }