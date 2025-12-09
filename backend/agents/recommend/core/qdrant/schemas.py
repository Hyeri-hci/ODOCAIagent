# core/qdrant/schemas.py

from config.setting import settings 

class RepoSchema:
    """Repository Description 컬렉션 정의"""
    
    FIELD_PROJECT_ID = "project_id"
    FIELD_EMBEDDING = "embedding"
    FIELD_NAME = "name"
    FIELD_OWNER = "owner"
    FIELD_REPO_URL = "repo_url"
    FIELD_DESC = "description"
    FIELD_MAIN_LANG = "main_language"
    FIELD_LICENSE = "license"
    FIELD_STARS = "stars"
    FIELD_FORKS = "forks"
    FIELD_TOPICS = "topics"
    FIELD_LANGUAGES = "languages"

    pass 


class ReadmeSchema:
    """Readme Chunks 컬렉션 정의"""
    
    FIELD_UID = "uid"
    FIELD_PROJECT_ID = "project_id"
    FIELD_CHUNK_IDX = "chunk_idx"
    FIELD_CONTENT = "chunk_content"
    FIELD_EMBEDDING = "embedding" 

    pass