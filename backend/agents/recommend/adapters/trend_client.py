import aiohttp
import logging
from typing import List, Dict, Any, Optional
from enum import Enum
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

class TrendingPeriod(Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"

class GitHubTrendClient:
    """
    하이브리드 클라이언트:
    1. OSS Insight API 시도 (빠름)
    2. 실패 시 GitHub Trending 페이지 크롤링 (안정적, Fallback)
    """
    
    # API URL (끝에 슬래시 포함)
    API_URL = "https://api.ossinsight.io/v1/trends/repos/"
    # 크롤링 URL
    CRAWL_URL = "https://github.com/trending"

    async def get_trending_repos(
        self, 
        language: Optional[str] = None, 
        period: TrendingPeriod = TrendingPeriod.WEEKLY,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        메인 메서드: API 우선 시도 -> 실패 시 크롤링
        """
        # 1. API 시도
        try:
            logger.info(f"📡 1차 시도: OSS Insight API 요청 (URL: {self.API_URL})")
            results = await self._fetch_from_api(language, period, limit)
            if results:
                return results[:limit]
        except Exception as e:
            logger.warning(f"⚠️ API 호출 실패 ({e}). 크롤링으로 전환합니다.")

        # 2. 크롤링 시도 (Fallback)
        try:
            results = await self._fetch_from_crawling(language, period)
            logger.info(f"🕷️ 2차 시도: GitHub 페이지 크롤링")

            return results[:limit]
        except Exception as e:
            logger.error(f"❌ 크롤링마저 실패했습니다: {e}")
            return []

    # =================================================================
    # [Logic 1] API 호출 (OSS Insight)
    # =================================================================
    async def _fetch_from_api(self, language: str, period: TrendingPeriod, limit: int) -> List[Dict[str, Any]]:
        period_map = {
            TrendingPeriod.DAILY: "past_24_hours",
            TrendingPeriod.WEEKLY: "past_week",
            TrendingPeriod.MONTHLY: "past_month",
        }
        
        # 쿼리 파라미터 설정
        params = {
            "period": period_map.get(period, "past_week"),
            "limit": limit  # 💡 API 요청에 limit 파라미터 추가
        }
        
        if language and language.lower() != "all":
            # 🛠️ [Fix] API가 소문자(python)를 에러 처리하는 경우가 있어 대문자(Python)로 변환
            params["language"] = language.capitalize()

        headers = {
            "Accept": "application/json"
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(self.API_URL, headers=headers, params=params, timeout=5) as response:
                if response.status != 200:
                    # 에러 메시지를 상세히 로깅하기 위해 본문 읽기
                    error_text = await response.text()
                    raise Exception(f"Status: {response.status}, Msg: {error_text}")
                
                data = await response.json()
                return self._parse_api_response(data)

    def _parse_api_response(self, data: dict) -> List[Dict[str, Any]]:
        # 데이터 구조 유연하게 처리 (data.rows 또는 data.data.rows)
        rows = data.get("data", {}).get("rows", [])
        
        # 구조가 다를 경우 대비 ({ "type": "sql_endpoint", "data": { "rows": ... } })
        if not rows and "data" in data and "rows" in data["data"]:
             rows = data["data"]["rows"]

        if not rows:
            return []
            
        parsed = []
        for idx, item in enumerate(rows):
            full_name = item.get("repo_name", "")
            
            # Owner/Name 쪼개기 (필수)
            owner = "Unknown"
            name = full_name
            
            if full_name and "/" in full_name:
                try:
                    owner, name = full_name.split("/", 1)
                except ValueError:
                    pass

            if not name:
                continue

            # 숫자 필드 안전 변환 (문자열로 올 수 있음)
            try:
                stars = int(item.get("stars", 0))
            except (ValueError, TypeError):
                stars = 0
                
            try:
                # API 데이터의 total_score 등을 stars_since로 대체
                # (API에 정확한 period_stars가 없을 경우 스코어를 사용)
                stars_since = int(float(item.get("total_score", 0))) 
            except (ValueError, TypeError):
                stars_since = 0

            parsed.append({
                "rank": idx + 1,
                "owner": owner,
                "name": name,
                "url": f"https://github.com/{full_name}",
                "description": item.get("description"),
                "language": item.get("primary_language"), # API 필드명 매핑
                "total_stars": stars,
                "stars_since": stars_since
            })
        return parsed

    # =================================================================
    # [Logic 2] 크롤링 (GitHub Web Parsing)
    # =================================================================
    async def _fetch_from_crawling(self, language: str, period: TrendingPeriod) -> List[Dict[str, Any]]:
        url = self.CRAWL_URL
        if language and language.lower() != "all":
            url += f"/{language}"
            
        params = {"since": period.value} # daily, weekly, monthly 그대로 사용

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    raise Exception(f"GitHub Page Error: {response.status}")
                
                html = await response.text()
                return self._parse_html(html)

    def _parse_html(self, html: str) -> List[Dict[str, Any]]:
        soup = BeautifulSoup(html, "html.parser")
        repos = []
        articles = soup.select("article.Box-row")
        
        for article in articles:
            try:
                # Title & URL
                h2 = article.select_one("h2.h3 a")
                if not h2: continue
                full_name = h2.get_text(strip=True).replace(" ", "")
                owner, name = full_name.split("/")
                relative_url = h2["href"]

                # Description
                p = article.select_one("p.col-9")
                description = p.get_text(strip=True) if p else ""
                
                # Language
                lang_span = article.select_one("[itemprop='programmingLanguage']")
                language = lang_span.get_text(strip=True) if lang_span else "Unknown"
                
                # Total Stars
                total_stars_tag = article.select_one(f"a[href='{relative_url}/stargazers']")
                total_stars_str = total_stars_tag.get_text(strip=True).replace(",", "") if total_stars_tag else "0"
                
                # Stars Since (오늘/이번주 획득 스타)
                stars_since_span = article.select_one(".float-sm-right")
                stars_since_str = "0"
                if stars_since_span:
                    text = stars_since_span.get_text(strip=True)
                    # "123 stars today" -> "123"
                    stars_since_str = text.split(" ")[0].replace(",", "")

                repos.append({
                    "rank": len(repos) + 1,
                    "owner": owner,
                    "name": name,
                    "url": f"https://github.com{relative_url}",
                    "description": description,
                    "language": language,
                    "total_stars": int(total_stars_str) if total_stars_str.isdigit() else 0,
                    "stars_since": int(stars_since_str) if stars_since_str.isdigit() else 0
                })
            except Exception:
                continue
        return repos

# 싱글톤 인스턴스
trend_client = GitHubTrendClient()