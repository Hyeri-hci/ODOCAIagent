# core/github/parser.py

from typing import Dict, List, Any, Union
from datetime import datetime
from core.github.schema import RepoSchema, ParsedRepo, ParsedIssue, ParsedPullRequest, ParsedCommit

class GitHubParser:
    """
    GitHub API 응답(JSON Dict) 또는 PyGithub 객체(Object)를 받아서
    프로젝트 내부에서 사용하는 Pydantic Schema로 변환하는 클래스.
    """

    @staticmethod
    def _to_datetime(ts: Union[str, datetime, None]) -> Union[datetime, None]:
        """
        내부 유틸리티: 입력값이 문자열(ISO8601)이면 datetime으로 변환,
        이미 datetime 객체라면 그대로 반환.
        """
        if not ts:
            return None
        if isinstance(ts, datetime):
            return ts
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            return None

    @staticmethod
    def parse_repo(repo_data: Dict, readme: str) -> RepoSchema:
        """
        [Ingest용] 상세 정보를 포함한 RepoSchema 변환
        - Input: GitHub API JSON (Dict) + README string
        """
        languages = list(repo_data.get("languages", {}).keys()) if "languages" in repo_data else []
        
        return RepoSchema(
            repo_url=repo_data.get("html_url"),
            name=repo_data.get("name"),
            owner=repo_data.get("owner", {}).get("login"),
            description=repo_data.get("description"),
            topics=repo_data.get("topics", []),
            main_language=repo_data.get("language"),
            languages=languages,
            license=repo_data.get("license", {}).get("name") if repo_data.get("license") else None,
            stars=repo_data.get("stargazers_count", 0),
            forks=repo_data.get("forks_count", 0),
            readme=readme
        )
    
    @staticmethod
    def parse_github_search_results(raw_items: List[Dict]) -> List[ParsedRepo]:
        """
        [Search용] 검색 결과 리스트 변환
        - Input: List[Dict] (Client.search_repos에서 .raw_data로 변환된 값)
        """
        parsed = []

        for item in raw_items:
            full_name = item.get("full_name", "")
            if "/" in full_name:
                owner, name = full_name.split("/", 1)
            else:
                owner, name = ("", full_name)

            parsed.append(
                ParsedRepo(
                    full_name=full_name,
                    owner=owner,
                    name=name,
                    stars=item.get("stargazers_count", 0),
                    forks=item.get("forks_count", 0),
                    # open_issues_count는 이슈+PR 합계임 (GitHub API 특성)
                    open_issues=item.get("open_issues_count", 0),
                    topics=item.get("topics", []),
                    last_update=GitHubParser._to_datetime(item.get("updated_at")),
                    last_push=GitHubParser._to_datetime(item.get("pushed_at")) if "pushed_at" in item else None,
                    description=item.get("description"),
                    html_url=item.get("html_url"),
                )
            )

        return parsed

    @staticmethod
    def parse_issues(raw_issues: List[Any]) -> List[ParsedIssue]:
        """
        [Fetcher용] Issue 객체 리스트 변환
        - Input: List[github.Issue.Issue] (PyGithub 객체)
        """
        parsed = []
        for issue in raw_issues:
            # PyGithub 객체 속성 접근 (Dot notation)
            try:
                p_issue = ParsedIssue(
                    number=issue.number,
                    title=issue.title,
                    state=issue.state,
                    # user가 None인 경우(삭제된 계정 등) 대비
                    user_login=issue.user.login if issue.user else "Unknown",
                    created_at=issue.created_at, # PyGithub는 datetime 객체를 줌
                    updated_at=issue.updated_at,
                    html_url=issue.html_url,
                    labels=[l.name for l in issue.labels]
                )
                parsed.append(p_issue)
            except Exception as e:
                # 파싱 중 에러 발생 시 해당 항목 건너뜀 (전체 중단 방지)
                print(f"⚠️ Error parsing issue {getattr(issue, 'number', '?')}: {e}")
                continue
                
        return parsed

    @staticmethod
    def parse_pull_requests(raw_prs: List[Any]) -> List[ParsedPullRequest]:
        """
        [Fetcher용] PR 객체 리스트 변환
        - Input: List[github.PullRequest.PullRequest]
        """
        parsed = []
        for pr in raw_prs:
            try:
                p_pr = ParsedPullRequest(
                    number=pr.number,
                    title=pr.title,
                    state=pr.state,
                    user_login=pr.user.login if pr.user else "Unknown",
                    created_at=pr.created_at,
                    updated_at=pr.updated_at,
                    merged_at=pr.merged_at, # None일 수 있음
                    html_url=pr.html_url
                )
                parsed.append(p_pr)
            except Exception as e:
                print(f"⚠️ Error parsing PR {getattr(pr, 'number', '?')}: {e}")
                continue
        return parsed

    @staticmethod
    def parse_commits(raw_commits: List[Any]) -> List[ParsedCommit]:
        """
        [Fetcher용] Commit 객체 리스트 변환
        - Input: List[github.Commit.Commit]
        """
        parsed = []
        for commit in raw_commits:
            try:
                # PyGithub 구조: commit -> commit(git data) -> author
                #              -> author(github user)
                
                # 1. Git Author Name (커밋한 사람 이름)
                author_name = commit.commit.author.name
                
                # 2. GitHub Login ID (계정 연동된 경우)
                author_login = commit.author.login if commit.author else None
                
                # 3. Date (Git Author Date 기준이 일반적)
                date = commit.commit.author.date
                
                p_commit = ParsedCommit(
                    sha=commit.sha,
                    author_name=author_name,
                    author_login=author_login,
                    date=date,
                    message=commit.commit.message,
                    html_url=commit.html_url
                )
                parsed.append(p_commit)
            except Exception as e:
                # 커밋 데이터가 꼬인 경우 등 대비
                # print(f"⚠️ Error parsing commit: {e}") 
                continue
                
        return parsed