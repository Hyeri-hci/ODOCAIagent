# core/qdrant/admin.py

import logging
from qdrant_client import models
from config.setting import settings
from core.qdrant.schemas import RepoSchema, ReadmeSchema 
from adapters.qdrant_client import qdrant_client 

logger = logging.getLogger(__name__)

# Qdrant는 컬렉션 생성 시 벡터 파라미터만 필요합니다.
VECTOR_PARAMS = models.VectorParams(
    size=settings.qdrant.embedding_dim, 
    distance=models.Distance.COSINE # Upstage 임베딩이 코사인 유사도 기반이므로 사용
)

def create_payload_index(collection_name: str, field_name: str, field_type: models.PayloadSchemaType):
    """
    Qdrant의 메타데이터 필터링 속도를 위한 Payload 인덱스 생성
    """
    try:
        qdrant_client.client.create_payload_index(
            collection_name=collection_name, 
            field_name=field_name, 
            field_schema=field_type
        )
        print(f"[Qdrant] Created payload index for field '{field_name}' in '{collection_name}'.")
    except Exception as e:
        logger.error(f"[Qdrant] Failed to create payload index for {field_name}: {e}")

def init_collections():
    """
    Qdrant 컬렉션을 초기화하고 인덱스를 생성합니다.
    """
    print(f"[Qdrant] Checking connection to {settings.qdrant.host}:{settings.qdrant.port}...")
    
    # Qdrant는 연결만 시도해도 클라이언트 객체가 생성됩니다.
    if not qdrant_client.client:
         logger.error("[Qdrant] Client connection failed. Check server status.")
         return

    targets = [
        (settings.qdrant.collection_desc, RepoSchema),
        (settings.qdrant.collection_readme, ReadmeSchema)
    ]

    for col_name, schema_cls in targets:
        try:
            # 1. 컬렉션 생성/재생성 (기존 컬렉션이 있으면 삭제 후 새로 만듭니다)
            qdrant_client.client.recreate_collection(
                collection_name=col_name,
                vectors_config=VECTOR_PARAMS
            )
            print(f"\n[Qdrant] Collection '{col_name}' created/recreated successfully.")
            
            # 2. 메타데이터(Payload) 인덱스 생성
            if schema_cls == RepoSchema:
                # Repo DB: project_id (Primary Key 역할) 및 stars (검색 필터링 용)에 인덱스 생성
                create_payload_index(col_name, RepoSchema.FIELD_PROJECT_ID, models.PayloadSchemaType.INTEGER)
                create_payload_index(col_name, RepoSchema.FIELD_STARS, models.PayloadSchemaType.INTEGER)
                
            elif schema_cls == ReadmeSchema:
                # Readme DB: project_id (Join용)에 인덱스 생성
                create_payload_index(col_name, ReadmeSchema.FIELD_PROJECT_ID, models.PayloadSchemaType.INTEGER)
                
            print(f"[Qdrant] '{col_name}' is ready.")

        except Exception as e:
            logger.error(f"[Qdrant] Failed to initialize collection {col_name}: {e}")

def drop_all_collections():
    """
    [주의] 모든 데이터를 삭제하고 초기화할 때 사용
    """
    if not qdrant_client.client:
        return
        
    target_names = [settings.qdrant.collection_desc, settings.qdrant.collection_readme]
    
    for name in target_names:
        try:
            if qdrant_client.client.get_collection(name):
                 qdrant_client.client.delete_collection(name)
                 print(f"[Qdrant] Dropped collection: {name}")
            else:
                 print(f"[Qdrant] Collection '{name}' does not exist.")
        except Exception:
            # collection not found error prevention
            print(f"[Qdrant] Collection '{name}' does not exist.")


if __name__ == "__main__":
    try:
        # [개발용] 만약 DB를 완전히 밀고 다시 만들고 싶으면 아래 주석 해제
        # drop_all_collections()
        
        init_collections()
        print("\n[Qdrant] All collections initialized successfully.")
    except Exception as e:
        print(f"\n[Error] Failed to initialize Qdrant: {e}")
    
    # Qdrant는 별도의 count_entities 함수가 필요하지 않습니다.
    # qdrant_client.count_entities('desc')를 사용하면 됩니다.