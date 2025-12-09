# core/analysis/scorer.py

import math
from datetime import datetime, timezone
from typing import List, Dict, Any, Union

class RepoScorer:
    """
    [Core Logic: Quantitative Scoring]
    GitHub 프로젝트의 메타데이터를 기반으로 활동성 및 인기도 점수를 산출합니다.
    
    공식:
    Total Score = (StarsScore * 0.5) + (RecencyScore * 0.3) + (ForkScore * 0.2)
    """

    def calculate_score(self, repo: Dict[str, Any]) -> float:
        """단일 리포지토리 점수 계산 (0~100점 스케일링 지향)"""
        score = 0.0
        
        # 1. 스타 점수 (Log Scale 적용)
        # 100개 vs 1000개의 차이는 크지만, 10만개 vs 11만개는 비슷하게 취급
        stars = repo.get("stars", 0) or 0
        # log10(100) = 2, log10(10000) = 4. 
        # 대략 1만 스타면 40점 만점 기준 
        star_score = math.log10(stars + 1) * 10 
        score += star_score * 0.5  # 가중치 50%

        # 2. 최신성 점수 (Recency)
        # 최근 업데이트가 중요함
        last_push = repo.get("last_push") or repo.get("updated_at")
        
        if last_push:
            try:
                # 문자열인 경우 datetime 변환
                if isinstance(last_push, str):
                    # Z를 +00:00으로 치환하여 ISO 포맷 처리
                    last_push = datetime.fromisoformat(last_push.replace("Z", "+00:00"))
                
                # 현재 시간과의 차이 (일 단위)
                now = datetime.now(timezone.utc)
                if last_push.tzinfo is None:
                    last_push = last_push.replace(tzinfo=timezone.utc)
                    
                days_diff = (now - last_push).days
                
                # 30일 이내 업데이트면 만점(30점), 이후 10일마다 1점씩 감점
                # 최소 0점
                recency_score = max(0, 30 - (days_diff // 10))
                score += recency_score * 0.3 # 가중치 30%
                
            except Exception as e:
                print(f"[Scorer] Date parsing error: {e}")
        
        # 3. 포크 점수 (활용도)
        forks = repo.get("forks", 0) or 0
        fork_score = math.log10(forks + 1) * 5
        score += fork_score * 0.2 # 가중치 20%

        return round(score, 2)

    def rank_repositories(self, repos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        리포지토리 리스트를 받아 점수를 매기고 내림차순 정렬하여 반환
        """
        scored_repos = []
        for repo in repos:
            # 원본 데이터 훼손 방지를 위해 복사본 사용 추천
            repo_copy = repo.copy()
            score = self.calculate_score(repo_copy)
            repo_copy["quantitative_score"] = score
            scored_repos.append(repo_copy)
        
        # 점수 높은 순 정렬
        return sorted(scored_repos, key=lambda x: x["quantitative_score"], reverse=True)