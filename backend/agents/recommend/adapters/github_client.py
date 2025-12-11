# adapters/github/client.py

from github import Github
from github import GithubObject
from github.Auth import Token
from typing import List, Any
from backend.agents.recommend.config.setting import settings
from backend.agents.recommend.core.github.schema import GitHubSearchInput

class GitHubClient:
    """
    PyGithub 라이브러리를 래핑한 GitHub API Client.
    - requests 직접 호출 대신 PyGithub 객체를 반환하여
    - Fetcher에서 .get_issues(), .get_commits() 등을 편하게 쓸 수 있게 함.
    - 페이지네이션 자동 처리 지원
    """

    def __init__(self, token: str = None):
        # 1. 토큰 설정 (없으면 settings에서 가져옴)
        self.token_str = token or settings.github.get_next_token()
        auth = Token(self.token_str)
        
        # 2. PyGithub 인스턴스 생성
        self.g = Github(auth=auth)

    def get_repo(self, repo_full_name: str) -> Any:
        """
        :param repo_full_name: "owner/repo" 형태 (예: "langchain-ai/langchain")
        :return: github.Repository.Repository 객체 (Dict 아님!)
        """
        # PyGithub은 내부적으로 404 에러 등을 핸들링함
        return self.g.get_repo(repo_full_name)

    def get_readme(self, owner: str, repo: str) -> str:
        """README 내용을 디코딩하여 문자열로 반환"""
        repo_obj = self.g.get_repo(f"{owner}/{repo}")
        try:
            file_content = repo_obj.get_readme()
            return file_content.decoded_content.decode("utf-8")
        except Exception:
            return "" # README가 없는 경우 빈 문자열

    def search_repos(self, input_model: GitHubSearchInput) -> List[dict]:
        """
        검색 결과 반환.
        Agent의 Tool에서는 JSON(Dict) 형태를 원하므로, 
        여기서는 PyGithub 객체를 raw data(Dict)로 변환해서 줌.
        """
        query = f"{input_model.q}"
        
        # sort/order 처리
        sort_val = input_model.sort
        if sort_val == "best_match" or not sort_val:
            sort = GithubObject.NotSet # PyGithub의 'Default' 상수
        else:
            sort = sort_val

        # order 처리
        order_val = input_model.order
        if not order_val:
            order = GithubObject.NotSet
        else:
            order = order_val
        
        # PyGithub search (Pagination 자동 처리되는 Iterator 반환)
        # 하지만 API 호출 최소화를 위해 상위 15~20개만 슬라이싱해서 가져옴
        results = self.g.search_repositories(query=query, sort=sort, order=order)
        
        parsed_list = []
        # 상위 15개만 Fetch (여기서 API 호출 발생)
        for repo in results[:15]: 
            parsed_list.append(repo.raw_data) # .raw_data가 실제 JSON Dict임
            
        return parsed_list

# 싱글톤 인스턴스
github_instance = GitHubClient()