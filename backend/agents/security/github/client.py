"""
GitHub API 클라이언트
"""
import os
import base64
import requests
import time
from typing import List, Dict, Optional
from dotenv import load_dotenv


class GitHubClient:
    """GitHub API와 통신하는 클라이언트"""

    def __init__(self, token: Optional[str] = None, base_url: Optional[str] = None):
        """
        GitHub 클라이언트 초기화

        Args:
            token: GitHub Personal Access Token (없으면 환경변수에서 가져옴)
            base_url: GitHub API 기본 URL (없으면 환경변수에서 가져옴)
        """
        load_dotenv()
        self.base_url = base_url or os.getenv('GITHUB_BASE_URL', 'https://api.github.com')
        self.base_url = f"{self.base_url}/repos"
        self.token = token or os.getenv('GITHUB_TOKEN')
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
            "User-Agent": "DependencyAnalyzer/1.0",
        }

    def get_repository_tree(self, owner: str, repo: str) -> List[Dict]:
        """
        레포지토리의 전체 파일 트리 가져오기

        Args:
            owner: 레포지토리 소유자
            repo: 레포지토리 이름

        Returns:
            List[Dict]: 파일 정보 목록
        """
        url = f"{self.base_url}/{owner}/{repo}/git/trees/HEAD?recursive=1"

        try:
            response = requests.get(url=url, headers=self.headers)
            response.raise_for_status()

            data = response.json()
            files = []

            if 'tree' in data:
                for item in data['tree']:
                    if item.get('type') == 'blob':
                        files.append({
                            'path': item.get('path'),
                            'sha': item.get('sha'),
                            'size': item.get('size', 0),
                            'url': item.get('url')
                        })

            return files

        except Exception as e:
            print(f"Error getting repository tree: {e}")
            return []

    def get_file_content(self, owner: str, repo: str, path: str) -> Optional[str]:
        """
        GitHub에서 파일 내용 가져오기

        Args:
            owner: 레포지토리 소유자
            repo: 레포지토리 이름
            path: 파일 경로

        Returns:
            Optional[str]: 파일 내용 (실패 시 None)
        """
        url = f"{self.base_url}/{owner}/{repo}/contents/{path}"

        try:
            response = requests.get(url=url, headers=self.headers)
            response.raise_for_status()

            data = response.json()
            if 'content' in data:
                content = base64.b64decode(data['content']).decode('utf-8')
                return content

        except Exception as e:
            print(f"Error getting file content for {path}: {e}")

        return None

    def get_file_content_with_retry(self, owner: str, repo: str, path: str, max_retries: int = 3) -> Optional[str]:
        """
        재시도 로직을 포함한 파일 내용 가져오기

        Args:
            owner: 레포지토리 소유자
            repo: 레포지토리 이름
            path: 파일 경로
            max_retries: 최대 재시도 횟수

        Returns:
            Optional[str]: 파일 내용 (실패 시 None)
        """
        for attempt in range(max_retries):
            try:
                content = self.get_file_content(owner, repo, path)
                if content:
                    return content

            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    print(f"Retry {attempt + 1} for {path} after {wait_time}s")
                    time.sleep(wait_time)
                else:
                    print(f"Failed to fetch {path} after {max_retries} attempts")

        return None
