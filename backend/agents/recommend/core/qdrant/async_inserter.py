import json
import os
import asyncio
import argparse
from tqdm.asyncio import tqdm
from typing import List, Dict, Any, Optional

from config.setting import settings
from db.db_check import get_db, TaskType

from adapters.qdrant_client import qdrant_client
from core.qdrant.schemas import RepoSchema, ReadmeSchema 
from qdrant_client.http.models import CollectionStatus

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
    
    # 1. Description/Metadata 데이터
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

    # 2. Readme 청크 데이터
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

# =========================================================
# 🏥 Health Monitor (서버 상태 감시자) - 래퍼 클래스 대응 수정됨
# =========================================================
async def health_monitor(health_event: asyncio.Event, stop_event: asyncio.Event):
    """
    주기적으로 Qdrant 상태를 체크하여 Green일 때만 작업을 허용합니다.
    """
    check_interval = 2.0  # 2초마다 상태 체크
    print("🏥 Health Monitor Started...")

    # [수정 포인트] 래퍼 클래스 내부의 실제 클라이언트 객체 찾기
    real_client = qdrant_client
    if hasattr(qdrant_client, "client"):
        real_client = qdrant_client.client
    elif hasattr(qdrant_client, "conn"):  # 혹시 변수명이 conn일 수도 있음
        real_client = qdrant_client.conn

    while not stop_event.is_set():
        try:
            # 'readme' 컬렉션의 상태를 확인
            # real_client를 사용하여 get_collection 호출
            collection_info = await asyncio.to_thread(real_client.get_collection, "repo_readmes")
            status = collection_info.status

            if status == CollectionStatus.GREEN:
                if not health_event.is_set():
                    print(f"\n🟢 [Health Monitor] Status is GREEN. Resuming workers...")
                    health_event.set() # 워커 진행 허용
            else:
                # Yellow 또는 Red 상태
                if health_event.is_set():
                    print(f"\n🔴 [Health Monitor] Status is {status}. PAUSING all workers!")
                    health_event.clear() # 워커 일시 정지

        except AttributeError:
            print(f"\n⚠️ [Config Error] 'qdrant_client' 내부에서 실제 QdrantClient 객체를 찾을 수 없습니다.")
            print("👉 adapters/qdrant_client.py 파일에서 실제 client 객체의 변수명(예: self.client)을 확인해주세요.")
            # 에러가 나면 일단 무시하고 진행할지, 멈출지 결정 (여기선 멈춤)
            stop_event.set()
            health_event.clear()
            break

        except Exception as e:
            # 연결 실패 시 일시 정지
            if health_event.is_set():
                print(f"\n⚠️ [Health Monitor] Connection Failed ({e}). PAUSING workers...")
                health_event.clear()
        
        await asyncio.sleep(check_interval)

# =========================================================
# 👷 Worker (작업자)
# =========================================================
async def worker(worker_id: int, queue: asyncio.Queue, health_event: asyncio.Event, batch_size: int, pbar: tqdm):
    """
    큐에서 작업을 가져와 처리하는 워커. health_event가 켜져 있을 때만 동작합니다.
    """
    while True:
        # 1. 건강 상태 체크 (Green이 아니면 여기서 대기)
        await health_event.wait()

        # 2. 큐에서 파일 경로 하나 꺼내기 (비어있으면 종료)
        try:
            file_path = await queue.get()
        except asyncio.QueueEmpty:
            break

        try:
            if not os.path.exists(file_path):
                continue

            filename = os.path.basename(file_path)
            try:
                project_id = int(os.path.splitext(filename)[0])
            except ValueError:
                continue

            # DB 처리 여부 확인
            db = get_db(TaskType.QDRANT_INSERT)
            if db.is_processed(project_id):
                continue

            # 3. 데이터 로드
            def load_json_file():
                with open(file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            
            # 로드 전에도 상태 체크
            await health_event.wait()
            raw_data = await asyncio.to_thread(load_json_file)
            data = raw_data[0] if isinstance(raw_data, list) and raw_data else raw_data

            repo_data, readme_chunks_data = transform_to_milvus_data(data)
            
            if not repo_data and not readme_chunks_data:
                continue

            # 4. Qdrant 삽입
            desc_insert_success = True
            readme_insert_success = True
            
            # Repo 데이터 삽입
            await health_event.wait()
            if repo_data:
                try:
                    # insert_data는 래퍼 클래스의 메소드를 그대로 사용 (보통 구현되어 있음)
                    await asyncio.to_thread(qdrant_client.insert_data, 'desc', repo_data)
                except Exception as e:
                    # print(f"❌ [Worker-{worker_id}] DESC Fail: {e}")
                    desc_insert_success = False
            
            # Readme 데이터 삽입 (배치 처리)
            if readme_chunks_data and desc_insert_success:
                total_chunks = len(readme_chunks_data)
                try:
                    for i in range(0, total_chunks, batch_size):
                        # 배치 루프마다 상태 확인
                        await health_event.wait()
                        
                        batch = readme_chunks_data[i : i + batch_size]
                        await asyncio.to_thread(qdrant_client.insert_data, 'readme', batch)
                        
                except Exception as e:
                    print(f"❌ [Worker-{worker_id}] README Batch Fail: {e}") 
                    readme_insert_success = False
            
            elif readme_chunks_data and not desc_insert_success:
                readme_insert_success = False

            # 5. 완료 처리
            if desc_insert_success and readme_insert_success:
                db.mark_as_processed(project_id)
            
        except Exception as e:
            print(f"❌ [Worker-{worker_id}] Unexpected Error: {e}")
        
        finally:
            queue.task_done()
            pbar.update(1)


async def run_qdrant_inserter_smart(target_list=None, max_sessions=10, batch_size=50):
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
    
    total_files = len(files)
    if total_files == 0:
        print("ℹ️ 처리할 파일이 없습니다.")
        return

    print(f"📥 Smart Qdrant Inserter (Health-Check Enabled)")
    print(f"👉 파일 수: {total_files}개")
    print(f"👉 설정: 워커(세션)={max_sessions}, 배치 크기={batch_size}")

    # 1. 큐 생성 및 파일 채우기
    queue = asyncio.Queue()
    for f in files:
        queue.put_nowait(f)

    # 2. 제어용 이벤트 생성
    health_event = asyncio.Event()
    health_event.set() # 초기 상태는 진행 허용
    
    stop_monitor_event = asyncio.Event() 

    # 3. 진행률 바 생성
    pbar = tqdm(total=total_files, desc="Processing")

    # 4. 모니터 태스크 시작
    monitor_task = asyncio.create_task(health_monitor(health_event, stop_monitor_event))

    # 5. 워커 태스크 시작
    workers = []
    for i in range(max_sessions):
        worker_task = asyncio.create_task(
            worker(i, queue, health_event, batch_size, pbar)
        )
        workers.append(worker_task)

    # 6. 모든 큐 작업이 끝날 때까지 대기
    await queue.join()

    # 7. 종료 처리
    for w in workers:
        w.cancel()
    
    stop_monitor_event.set()
    try:
        await monitor_task
    except asyncio.CancelledError:
        pass
    
    pbar.close()
    print("\n✅ 모든 작업이 안전하게 완료되었습니다.")

def main():
    parser = argparse.ArgumentParser(description="Qdrant Smart Data Inserter")
    parser.add_argument("--sessions", type=int, default=10, help="동시 실행 워커 수")
    parser.add_argument("--batch", type=int, default=50, help="데이터 삽입 배치 사이즈")
    args = parser.parse_args()

    # 윈도우 환경 asyncio 정책 설정
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    try:
        asyncio.run(run_qdrant_inserter_smart(
            target_list=None, 
            max_sessions=args.sessions, 
            batch_size=args.batch
        ))
    except KeyboardInterrupt:
        print("\n🛑 사용자에 의해 강제 종료되었습니다.")

if __name__ == "__main__":
    main()