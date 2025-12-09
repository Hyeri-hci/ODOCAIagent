# tools/github/github_ingest_tool.py

import json
from langchain.tools import tool 
from typing import Dict, Any
from core.ingest.github_ingest import GitHubIngest

@tool
async def github_ingest_tool(repo_url: str) -> str: # [수정] async def
    """
    [Ingest Tool]
    특정 GitHub Repository URL을 입력받아 상세 분석을 수행합니다.
    README 내용을 요약하고, 주요 언어/토픽/메타데이터를 수집하여 반환합니다.
    """
    try:
        # Core 로직 인스턴스화
        ingest = GitHubIngest()
        
        # [수정] 비동기 호출 (요약 과정이 오래 걸릴 수 있으므로 await 필수)
        repo_schema = await ingest.get_repo(repo_url)
        
        # Pydantic -> Dict -> JSON String
        data = repo_schema.model_dump()
        return json.dumps(data, ensure_ascii=False)

    except Exception as e:
        # 에러 발생 시 JSON 형태로 에러 메시지 반환
        return json.dumps({
            "error": f"Ingest failed: {str(e)}",
            "repo_url": repo_url
        }, ensure_ascii=False)