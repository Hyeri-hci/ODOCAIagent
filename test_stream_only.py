"""스트리밍 테스트만 실행"""
import asyncio
import httpx
import json

BASE_URL = "http://localhost:8000"


async def test_streaming():
    """스트리밍 테스트"""
    print("=== 스트리밍 테스트 시작 ===\n")
    
    async with httpx.AsyncClient() as client:
        print("요청 전송 중...")
        async with client.stream(
            "POST",
            f"{BASE_URL}/api/chat/stream",
            json={
                "message": "FastAPI 프로젝트 간단히 분석해줘",
                "owner": "tiangolo",
                "repo": "fastapi"
            },
            timeout=60.0
        ) as response:
            
            print(f"응답 상태 코드: {response.status_code}\n")
            
            if response.status_code == 200:
                event_count = 0
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        event_count += 1
                        data_str = line[6:]
                        print(f"[이벤트 {event_count}] Raw: {data_str}")
                        
                        try:
                            data = json.loads(data_str)
                            event_type = data.get("type")
                            print(f"  타입: {event_type}")
                            print(f"  전체 데이터: {data}")
                            
                            if event_type == "error":
                                print(f"  ❌ 에러 메시지: {data.get('message')}")
                                print(f"  ❌ 에러 메시지 타입: {type(data.get('message'))}")
                        except json.JSONDecodeError as e:
                            print(f"  JSON 파싱 에러: {e}")
                        
                        print()
            else:
                print(f"❌ 요청 실패: {response.status_code}")


if __name__ == "__main__":
    asyncio.run(test_streaming())
