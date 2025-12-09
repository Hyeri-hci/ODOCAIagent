"""온보딩 플랜 및 대명사 해결 테스트"""
import asyncio
import httpx

BASE_URL = "http://localhost:8000"


async def test_onboarding_and_pronoun():
    """온보딩 플랜 생성 및 대명사 해결 테스트"""
    
    print("=" * 60)
    print("온보딩 플랜 & 대명사 해결 통합 테스트")
    print("=" * 60)
    
    async with httpx.AsyncClient() as client:
        
        # Test 1: 저장소 진단
        print("\n=== Test 1: 저장소 진단 ===")
        response = await client.post(
            f"{BASE_URL}/api/chat/",
            json={
                "message": "fastapi/fastapi 저장소 분석해줘",
                "owner": "fastapi",
                "repo": "fastapi"
            },
            timeout=120.0
        )
        
        if response.status_code == 200:
            data = response.json()
            session_id = data["session_id"]
            print(f"✅ Session ID: {session_id}")
            print(f"✅ Answer preview: {data['answer'][:150]}...")
        else:
            print(f"❌ Error: {response.status_code}")
            return
        
        await asyncio.sleep(2)
        
        # Test 2: 온보딩 플랜 요청 (세션 유지)
        print("\n=== Test 2: 온보딩 플랜 요청 ===")
        response = await client.post(
            f"{BASE_URL}/api/chat/",
            json={
                "session_id": session_id,
                "message": "온보딩 플랜 만들어줘",
                "owner": "fastapi",
                "repo": "fastapi"
            },
            timeout=120.0
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Answer preview: {data['answer'][:300]}...")
            
            # 응답에 온보딩 관련 키워드가 있는지 확인
            answer = data['answer']
            keywords = ["단계", "시간", "난이도", "사전지식"]
            found_keywords = [kw for kw in keywords if kw in answer]
            print(f"✅ Found keywords: {found_keywords}")
        else:
            print(f"❌ Error: {response.status_code}")
        
        await asyncio.sleep(2)
        
        # Test 3: 대명사 참조 ("그거" 사용)
        print("\n=== Test 3: 대명사 참조 테스트 ===")
        response = await client.post(
            f"{BASE_URL}/api/chat/",
            json={
                "session_id": session_id,
                "message": "그거 초보자 관점에서 다시 설명해줘",
                "owner": "fastapi",
                "repo": "fastapi"
            },
            timeout=120.0
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Answer preview: {data['answer'][:200]}...")
            
            # 이전 컨텍스트를 참조했는지 확인
            answer = data['answer']
            context_indicators = ["온보딩", "단계", "fastapi", "플랜"]
            found_indicators = [ind for ind in context_indicators if ind.lower() in answer.lower()]
            print(f"✅ Context indicators found: {found_indicators}")
        else:
            print(f"❌ Error: {response.status_code}")
        
        await asyncio.sleep(2)
        
        # Test 4: 다른 저장소 온보딩 플랜 (새로운 요청)
        print("\n=== Test 4: 다른 저장소 온보딩 플랜 ===")
        response = await client.post(
            f"{BASE_URL}/api/chat/",
            json={
                "message": "django/django 저장소 온보딩 플랜 만들어줘",
                "owner": "django",
                "repo": "django"
            },
            timeout=120.0
        )
        
        if response.status_code == 200:
            data = response.json()
            new_session_id = data["session_id"]
            print(f"✅ New Session ID: {new_session_id}")
            print(f"✅ Answer preview: {data['answer'][:300]}...")
        else:
            print(f"❌ Error: {response.status_code}")
        
        print("\n" + "=" * 60)
        print("✅ 온보딩 & 대명사 테스트 완료!")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_onboarding_and_pronoun())
