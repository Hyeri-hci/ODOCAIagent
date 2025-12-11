# test/test_qdrant.py

from adapters.qdrant_client import qdrant_client
from core.qdrant.schemas import RepoSchema, ReadmeSchema # 스키마 import 필수
from config.setting import settings

def check_data():
    print("🔍 Qdrant 데이터 무결성 검사 시작...\n")

    real_client = qdrant_client.client
    desc_col = qdrant_client._get_collection_name('desc')
    readme_col = qdrant_client._get_collection_name('readme')

    # ... (카운트 부분 생략, 기존과 동일) ...

    # ====================================================
    # 2. 데이터 샘플 조회 (Scroll)
    # ====================================================
    
    # ... (Repo 부분 생략, 기존과 동일) ...

    print("-" * 50)
    print(f"\n👀 [샘플 데이터 확인] Collection: {readme_col} (상위 3개)")

    points, _ = real_client.scroll(
        collection_name=readme_col,
        limit=3,
        with_payload=True,
        with_vectors=False
    )

    for p in points:
        print(f"\n[ID: {p.id}]")
        
        # 1. 어떤 키값들이 있는지 먼저 확인 (디버깅용)
        # print(f" - Payload Keys: {list(p.payload.keys())}") 

        # 2. 스키마 상수를 사용하여 안전하게 조회
        project_id = p.payload.get(ReadmeSchema.FIELD_PROJECT_ID)
        chunk_idx = p.payload.get(ReadmeSchema.FIELD_CHUNK_IDX)
        
        # [핵심 수정] 하드코딩 'content' 대신 스키마 사용
        content = p.payload.get(ReadmeSchema.FIELD_CONTENT, '') 

        print(f" - Project ID: {project_id}")
        print(f" - Chunk Index: {chunk_idx}")
        
        # 내용이 있으면 100자만, 없으면 (Empty) 표시
        if content:
            print(f" - Content (Preview): {str(content)[:100]}...") 
        else:
            print(f" - Content (Preview): (Empty Data) - Key mismatch or null data")
            # 만약 계속 비어있다면 실제 페이로드를 전체 출력해서 키를 확인해보세요
            print(f"   ▶ 실제 Payload 전체: {p.payload}")

    print("\n✅ 검사 완료.")

if __name__ == "__main__":
    check_data()