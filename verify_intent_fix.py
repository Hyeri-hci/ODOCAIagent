
import asyncio
import os
import sys

# 프로젝트 루트를 path에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.agents.supervisor.intent_parser import SupervisorIntentParserV2

async def verify_intent():
    parser = SupervisorIntentParserV2()
    
    test_cases = [
        "facebook/react 종합 분석해줘",
        "이 프로젝트 전체적으로 분석해줘",
        "flask/flask comprehensive analysis"
    ]
    
    print("=== Verifying Comprehensive Analysis Intent ===")
    
    for msg in test_cases:
        print(f"\nInput: {msg}")
        # session_context is needed for some logic, but basic keyword check might not strictly need it 
        # unless it checks _has_repo_in_context. 
        # But my code checks keyword_agent in _keyword_preprocess first.
        # However, _keyword_preprocess returns 'diagnosis'.
        # Then `parse` continues.
        
        # We need a dummy context to avoid errors if any
        ctx = {"owner": "facebook", "repo": "react"}
        
        intent = await parser.parse(msg, session_context=ctx)
        
        print(f"Task Type: {intent.task_type}")
        print(f"Target Agent: {intent.target_agent}")
        print(f"Additional Agents: {intent.additional_agents}")
        
        if intent.target_agent == "diagnosis" and "security" in intent.additional_agents:
             print("RESULT: SUCCESS")
        else:
             print("RESULT: FAILURE")

if __name__ == "__main__":
    asyncio.run(verify_intent())
