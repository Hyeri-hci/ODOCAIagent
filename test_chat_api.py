"""
Chat API 통합 테스트 스크립트

Usage:
    python test_chat_api.py
"""

import asyncio
import httpx
import json
from typing import Optional


BASE_URL = "http://localhost:8000"


async def test_new_chat():
    """새 채팅 세션 테스트"""
    print("\n=== Test 1: 새 채팅 세션 ===")
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/api/chat/",
            json={
                "message": "django-oscar 프로젝트 분석해줘",
                "owner": "django-oscar",
                "repo": "django-oscar"
            },
            timeout=60.0
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Session ID: {data['session_id']}")
            print(f"✅ Answer: {data['answer'][:100]}...")
            print(f"✅ Suggestions: {data['suggestions']}")
            return data['session_id']
        else:
            print(f"❌ Error: {response.status_code}")
            print(response.text)
            return None


async def test_continue_chat(session_id: str):
    """대화 이어가기 테스트"""
    print(f"\n=== Test 2: 대화 이어가기 (Session: {session_id}) ===")
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/api/chat/",
            json={
                "session_id": session_id,
                "message": "더 자세히 설명해줘"
            },
            timeout=60.0
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Same Session: {data['session_id'] == session_id}")
            print(f"✅ Answer: {data['answer'][:100]}...")
        else:
            print(f"❌ Error: {response.status_code}")


async def test_get_session(session_id: str):
    """세션 정보 조회 테스트"""
    print(f"\n=== Test 3: 세션 정보 조회 ===")
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BASE_URL}/api/chat/session/{session_id}",
            timeout=10.0
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Session ID: {data['session_id']}")
            print(f"✅ Turn Count: {data['turn_count']}")
            print(f"✅ Created At: {data['created_at']}")
        else:
            print(f"❌ Error: {response.status_code}")


async def test_list_sessions():
    """활성 세션 목록 테스트"""
    print("\n=== Test 4: 활성 세션 목록 ===")
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BASE_URL}/api/chat/sessions",
            timeout=10.0
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Total Sessions: {data['total']}")
            for session in data['sessions'][:3]:
                print(f"  - {session['session_id']}: {session['turn_count']} turns")
        else:
            print(f"❌ Error: {response.status_code}")


async def test_streaming_chat():
    """스트리밍 채팅 테스트"""
    print("\n=== Test 5: 스트리밍 채팅 ===")
    
    async with httpx.AsyncClient() as client:
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
            
            if response.status_code == 200:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = json.loads(line[6:])
                        event_type = data.get("type")
                        print(f"📡 Event: {event_type}")
                        
                        if event_type == "answer":
                            print(f"   Answer: {data.get('answer', '')[:50]}...")
                        elif event_type == "error":
                            print(f"   ❌ Error: {data.get('message')}")
            else:
                print(f"❌ Error: {response.status_code}")


async def test_pronoun_resolution(session_id: str):
    """대명사 해결 테스트"""
    print(f"\n=== Test 6: 대명사 해결 (Session: {session_id}) ===")
    
    messages = [
        "그거 초보자 관점에서 다시 설명해줘",
        "온보딩 플랜 만들어줘",
    ]
    
    async with httpx.AsyncClient() as client:
        for msg in messages:
            print(f"\n📤 Message: {msg}")
            
            response = await client.post(
                f"{BASE_URL}/api/chat/",
                json={
                    "session_id": session_id,
                    "message": msg
                },
                timeout=60.0
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Answer: {data['answer'][:80]}...")
            else:
                print(f"❌ Error: {response.status_code}")
            
            await asyncio.sleep(1)


async def test_delete_session(session_id: str):
    """세션 삭제 테스트"""
    print(f"\n=== Test 7: 세션 삭제 ===")
    
    async with httpx.AsyncClient() as client:
        response = await client.delete(
            f"{BASE_URL}/api/chat/session/{session_id}",
            timeout=10.0
        )
        
        if response.status_code == 200:
            print(f"✅ Session deleted: {session_id}")
        else:
            print(f"❌ Error: {response.status_code}")


async def main():
    """전체 테스트 실행"""
    print("=" * 60)
    print("Chat API 통합 테스트")
    print("=" * 60)
    
    try:
        # Test 1: 새 채팅
        session_id = await test_new_chat()
        
        if not session_id:
            print("\n❌ 첫 번째 테스트 실패. 서버가 실행 중인지 확인하세요.")
            return
        
        # Test 2: 대화 이어가기
        await test_continue_chat(session_id)
        
        # Test 3: 세션 정보 조회
        await test_get_session(session_id)
        
        # Test 4: 활성 세션 목록
        await test_list_sessions()
        
        # Test 5: 스트리밍 채팅
        await test_streaming_chat()
        
        # Test 6: 대명사 해결
        await test_pronoun_resolution(session_id)
        
        # Test 7: 세션 삭제
        await test_delete_session(session_id)
        
        print("\n" + "=" * 60)
        print("✅ 모든 테스트 완료!")
        print("=" * 60)
    
    except Exception as e:
        print(f"\n❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
