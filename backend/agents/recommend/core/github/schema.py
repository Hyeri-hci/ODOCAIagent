# core/github/schema.py

from pydantic import BaseModel
from dataclasses import dataclass
from typing import List, Optional, Literal
from datetime import datetime

class RepoSchema(BaseModel):
    repo_url: str
    name: str
    owner: str
    description: Optional[str] = None
    topics: List[str] = []
    main_language: Optional[str] = None
    languages: List[str] = []
    license: Optional[str] = None
    stars: int = 0
    forks: int = 0
    readme: str = ""

class GitHubSearchInput(BaseModel):
    q: str
    sort: Optional[str] = None
    order: Optional[str] = None

class ParsedRepo(BaseModel):
    full_name: str
    owner: str
    name: str
    stars: int
    forks: int
    open_issues: int
    topics: List[str]
    last_update: datetime
    last_push: Optional[datetime] = None
    description: Optional[str]
    html_url: str

class ParsedCommit(BaseModel):
    sha: str
    author_name: Optional[str]
    author_login: Optional[str]
    date: datetime
    message: str
    html_url: str

class ParsedIssue(BaseModel):
    number: int
    title: str
    state: str
    user_login: str
    created_at: datetime
    updated_at: datetime
    html_url: str
    labels: List[str]

class ParsedPullRequest(BaseModel):
    number: int
    title: str
    state: str
    user_login: str
    created_at: datetime
    updated_at: datetime
    merged_at: Optional[datetime]
    html_url: str

class GitHubTrendInput(BaseModel):
    """
    트렌드 검색을 위한 입력 파라미터
    """
    language: Optional[str] = None      # 예: 'python', 'java' (없으면 전체 언어)
    since: Literal["daily", "weekly", "monthly"] = "daily" # 기간 설정
    spoken_language_code: Optional[str] = None # 예: 'en', 'ko' (특정 언어권 필터링)

class ParsedTrendingRepo(BaseModel):
    """
    트렌딩 리포지토리 파싱 결과
    일반 Repo와 달리 '순위'와 '기간 내 획득 스타 수'가 중요함
    """
    rank: int                           # 트렌드 순위 (1~25)
    owner: str
    name: str
    url: str
    description: Optional[str] = None
    language: Optional[str] = None
    total_stars: int = 0                # 전체 스타 수
    stars_since: int = 0                # 해당 기간(since) 동안 받은 스타 수 (오늘의 스타 등)
    # 필요하다면 나중에 ParsedRepo로 변환하거나 확장 가능