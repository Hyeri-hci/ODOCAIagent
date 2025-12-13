import asyncio
import os
import sys

# 프로젝트 루트를 path에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.agents.supervisor.graph import run_supervisor
from backend.common.session import get_session_store

async def test_url_intent():
    # Test Cases
    test_inputs = [
        "https://github.com/hyeri-hci/OSSDoctor",           # Clean URL
        "https://github.com/hyeri-hci/OSSDoctor/",          # Trailing slash
        "https://github.com/hyeri-hci/OSSDoctor.git",       # .git extension
        "hyeri-hci/OSSDoctor",                              # Owner/Repo
        "hyeri-hci/OSSDoctor@main",                         # @ref
        "https://github.com/hyeri-hci/OSSDoctor/tree/dev"   # Tree URL
    ]
    
    for user_message in test_inputs:
        print(f"\n--- Testing with message: {user_message} ---")
        
        try:
            # run_supervisor 실행
            result = await run_supervisor(
                owner="unknown",
                repo="unknown",
                user_message=user_message,
                session_id="test_session_id"
            )
            
            print(f"Target Agent: {result.get('target_agent')}")
            print(f"Detected Repo: {result.get('owner')}/{result.get('repo')}")
            print(f"Diagnosis Result: {'Present' if result.get('diagnosis_result') else 'Missing'}")
            print(f"Security Result: {'Present' if result.get('security_result') else 'Missing'}")
            
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_url_intent())
