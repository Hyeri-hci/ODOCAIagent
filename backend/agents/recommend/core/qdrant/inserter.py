# core/qdrant/inserter.py

import json
import os
import random
from tqdm import tqdm
from typing import List, Dict, Any, Optional

from config.setting import settings
from db.db_check import get_db, TaskType
from utils.lock_util import acquire_lock, release_lock
from adapters.qdrant_client import qdrant_client
from core.qdrant.schemas import RepoSchema, ReadmeSchema 

INSERT_BATCH_SIZE = 1 

# 텍스트 길이 제한 설정
REPO_DESC_MAX_LEN = 2000
README_CONTENT_MAX_LEN = 3000
REPO_NAME_MAX_LEN = 255 

def truncate_string(s: Optional[str], max_len: int) -> str:
    """문자열을 주어진 max_len으로 자릅니다."""
    if s is None:
        return ""
    return str(s)[:max_len]


def transform_to_milvus_data(data: Dict[str, Any]) -> tuple[List[Dict], List[Dict]]:
    """
    JSON 프로젝트 데이터를 Qdrant 삽입용 형식(List[Dict])으로 변환합니다.
    """
    repo_data = []
    readme_chunks_data = []
    
    # -------------------------------------------------------------
    # 1. Description/Metadata 데이터 (RepoSchema) 추출 및 자르기
    # -------------------------------------------------------------
    desc_embedding = data.get("description_embedding")
    
    if desc_embedding and isinstance(desc_embedding, list) and isinstance(desc_embedding[0], float):
        repo_item = {
            RepoSchema.FIELD_PROJECT_ID: data.get("project_id"),
            RepoSchema.FIELD_EMBEDDING: desc_embedding,
            RepoSchema.FIELD_NAME: truncate_string(data.get("name"), REPO_NAME_MAX_LEN),
            RepoSchema.FIELD_OWNER: truncate_string(data.get("owner"), REPO_NAME_MAX_LEN),
            RepoSchema.FIELD_REPO_URL: truncate_string(data.get("repo_url"), 512),
            RepoSchema.FIELD_DESC: truncate_string(data.get("description"), REPO_DESC_MAX_LEN),
            
            RepoSchema.FIELD_MAIN_LANG: data.get("main_language"),
            RepoSchema.FIELD_LICENSE: data.get("license"),
            RepoSchema.FIELD_STARS: data.get("stars", 0),
            RepoSchema.FIELD_FORKS: data.get("forks", 0),
            RepoSchema.FIELD_TOPICS: data.get("topics"), 
            RepoSchema.FIELD_LANGUAGES: data.get("languages"),
        }
        repo_data.append(repo_item)

    # -------------------------------------------------------------
    # 2. Readme 청크 데이터 (ReadmeSchema) 추출 및 자르기
    # -------------------------------------------------------------
    readme_chunks = data.get("readme_chunks", [])
    readme_embeddings = data.get("readme_embedding", [])
    
    if readme_chunks and readme_embeddings and len(readme_chunks) == len(readme_embeddings):
        project_id = data.get("project_id")
        
        for idx, (chunk_content, embedding) in enumerate(zip(readme_chunks, readme_embeddings)):
            chunk_item = {
                ReadmeSchema.FIELD_PROJECT_ID: project_id,
                ReadmeSchema.FIELD_CHUNK_IDX: idx,
                ReadmeSchema.FIELD_CONTENT: truncate_string(chunk_content, README_CONTENT_MAX_LEN), 
                ReadmeSchema.FIELD_EMBEDDING: embedding,
            }
            readme_chunks_data.append(chunk_item)

    return repo_data, readme_chunks_data


def process_qdrant_insertion(file_path: str):
    if not os.path.exists(file_path):
        return

    try:
        filename = os.path.basename(file_path)
        project_id = int(os.path.splitext(filename)[0])
    except ValueError:
        return

    db = get_db(TaskType.QDRANT_INSERT)
    
    if db.is_processed(project_id):
        return

    lock_name = f"proj_{project_id}"
    if not acquire_lock(lock_name, timeout=0.1):
        return

    try:
        # 1. 데이터 로드 및 변환
        with open(file_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
        
        data = raw_data[0] if isinstance(raw_data, list) and raw_data else raw_data

        repo_data, readme_chunks_data = transform_to_milvus_data(data)
        
        if not repo_data and not readme_chunks_data:
            return 

        # -------------------------------------------------------------
        # 3. Qdrant 삽입 실행 (트랜잭션 로직 시작)
        # -------------------------------------------------------------
        desc_insert_success = True
        readme_insert_success = True
        
        # 3-A. Repo DB 삽입 (Description)
        if repo_data:
            try:
                # Qdrant 클라이언트 사용
                qdrant_client.insert_data('desc', repo_data) 
                print(f"✅ [Qdrant] ID {project_id}: Inserted 1 item into DESC collection.")
            except Exception as e:
                print(f"❌ [QDRANT FAIL] ID {project_id}: DESC Insertion failed. Cause: {e}") 
                desc_insert_success = False
        
        # 3-B. Readme DB 삽입 (Chunks) - 하나씩 삽입
        if readme_chunks_data and desc_insert_success:
            total_chunks = len(readme_chunks_data)
            success_count = 0
            
            try:
                # 🎯 [수정 유지] 청크를 하나씩 순회하며 삽입 (단일 엔티티 삽입)
                for chunk in readme_chunks_data:
                    qdrant_client.insert_data('readme', [chunk]) 
                    success_count += 1
                
                print(f"✅ [Qdrant] ID {project_id}: Inserted {total_chunks} chunks into README collection (One-by-One).")
            
            except Exception as e:
                print(f"❌ [QDRANT FAIL] ID {project_id}: README Insertion failed after {success_count} chunks. Cause: {e}") 
                readme_insert_success = False
        
        elif readme_chunks_data and not desc_insert_success:
            readme_insert_success = False


        # 4. 최종 완료 기록 (두 작업 모두 성공했을 때만 DB 기록)
        if desc_insert_success and readme_insert_success:
            db.mark_as_processed(project_id)
        else:
            print(f"⚠️ [FINAL STATUS] ID {project_id}: Incomplete insertion (DESC:{desc_insert_success}, README:{readme_insert_success}). Retrying next time.")
            
    except Exception as e:
        print(f"❌ [PROCESS FAIL] ID {project_id}: 처리 중 예상치 못한 오류 발생: {e}")
    
    finally:
        release_lock(lock_name)


def run_qdrant_inserter(target_list=None):
    PROJECT_DATA_DIR = settings.paths.PROJECT_DIR
    
    if not os.path.exists(PROJECT_DATA_DIR):
        print("❌ 데이터 폴더 없음")
        return

    files = []
    if target_list:
        for f in target_list:
            if not f.endswith(".json"): f += ".json"
            files.append(os.path.join(PROJECT_DATA_DIR, f))
    else:
        files = [
            os.path.join(PROJECT_DATA_DIR, f) 
            for f in os.listdir(PROJECT_DATA_DIR) 
            if f.endswith(".json")
        ]
        random.shuffle(files)

    if not files:
        print("ℹ️ 처리할 파일이 없습니다.")
        return

    print(f"📥 Qdrant 삽입 시작 ({len(files)}개 파일)")
    
    for file_path in tqdm(files, desc="Qdrant Insert"):
        process_qdrant_insertion(file_path)

    print("\n✅ 모든 파일 삽입 요청 완료. Qdrant는 별도의 Flush가 필요 없습니다.")


if __name__ == "__main__":
    run_qdrant_inserter(None)