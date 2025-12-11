import logging
from adapters.github_client import github_instance as client
from core.github.parser import GitHubParser
from core.ingest.summarizer import ContentSummarizer 
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class GitHubIngest:
    """
    [Core Logic] GitHub 데이터 수집 및 전처리(요약) Orchestrator
    """

    def __init__(self):
        self.client = client
        self.summarizer = ContentSummarizer()

    async def get_repo(self, repo_url: str):
        """
        URL -> Raw Data -> Summarization -> Schema
        """
        # 1. URL 파싱
        try:
            parts = repo_url.rstrip("/").split("/")
            if len(parts) < 2:
                raise ValueError("URL format error")
            owner, repo = parts[-2], parts[-1]
            logger.info(f"[Ingest] Attempting to process {owner}/{repo}")
        except ValueError:
            logger.error(f"[Ingest] Invalid GitHub URL format: {repo_url}")
            raise ValueError(f"Invalid GitHub URL format: {repo_url}")

        logger.info(f"🟢 [Ingest] Starting data fetching for {owner}/{repo}...")

        # 2. Pygithub 객체 가져오기 (API Call 1)
        repo_obj = self.client.get_repo(f"{owner}/{repo}")
        logger.info(f"   [API Call 1] Repository metadata fetched successfully.")
        
        # 3. README 원본 가져오기 (API Call 2)
        raw_readme = self.client.get_readme(owner, repo)
        readme_len = len(raw_readme) if raw_readme else 0
        logger.info(f"   [API Call 2] README fetched. (Length: {readme_len} chars)")

        # 4. 언어 데이터 가져오기 (API Call 3)
        languages_dict = repo_obj.get_languages()
        logger.info(f"   [API Call 3] Languages fetched. (Main language: {max(languages_dict, key=languages_dict.get) if languages_dict else 'None'})")
        
        # ========================================================
        # [전처리 핵심] Map-Reduce 요약 실행 (LLM Call)
        # ========================================================
        summary = ""
        if raw_readme:
            print(f"   [LLM Task] Summarizing README for {owner}/{repo}...")
            # 💡 [로그 추가] 요약이 시작됨을 명시
            summary = await self.summarizer.summarize(raw_readme)
            print(f"   [LLM Result] Summarization successful. (Summary length: {len(summary)} chars)")
        else:
            summary = "No README content available."
            print("   [LLM Task] Skipping summarization: No README found.")

        
        # 5. 데이터 병합 (Parser에게 넘길 준비)
        repo_data = repo_obj.raw_data
        repo_data['languages'] = languages_dict
        logger.info("   [Data Merge] Merged languages and metadata.")
        
        # 6. 파싱 및 반환 (Pydantic 객체)
        repo_schema = GitHubParser.parse_repo(repo_data, summary)
        
        print(f"✅ [Ingest Done] Successfully parsed {owner}/{repo} into schema.")
        return repo_schema