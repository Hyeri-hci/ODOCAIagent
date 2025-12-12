"""
단일 시나리오 대화형 테스트

터미널에서 직접 실행하며 대화 테스트

실행: python -m backend.tests.interactive_test
"""

import asyncio
import logging
from datetime import datetime

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)


async def interactive_session():
    """대화형 세션"""
    from backend.agents.supervisor.graph import run_supervisor
    
    print("\n" + "="*60)
    print("ODOCAIagent 대화형 테스트")
    print("="*60)
    print("명령어:")
    print("  /quit - 종료")
    print("  /reset - 세션 초기화")
    print("  /status - 현재 상태")
    print("="*60 + "\n")
    
    session_id = None
    owner = "facebook"
    repo = "react"
    message_count = 0
    
    while True:
        try:
            # 사용자 입력
            user_input = input(f"\n[{message_count+1}] 입력> ").strip()
            
            if not user_input:
                continue
            
            # 명령어 처리
            if user_input == "/quit":
                print("테스트 종료")
                break
            elif user_input == "/reset":
                session_id = None
                message_count = 0
                print("세션 초기화됨")
                continue
            elif user_input == "/status":
                print(f"세션 ID: {session_id}")
                print(f"저장소: {owner}/{repo}")
                print(f"메시지 수: {message_count}")
                continue
            elif user_input.startswith("/repo "):
                # 저장소 변경: /repo owner/repo
                parts = user_input[6:].split("/")
                if len(parts) == 2:
                    owner, repo = parts
                    print(f"저장소 변경: {owner}/{repo}")
                continue
            
            # Supervisor 실행
            print("\n처리 중...")
            start_time = datetime.now()
            
            result = await run_supervisor(
                owner=owner,
                repo=repo,
                user_message=user_input,
                session_id=session_id
            )
            
            elapsed = (datetime.now() - start_time).total_seconds()
            
            # 결과 출력
            print(f"\n[AI 응답] ({elapsed:.1f}s)")
            print("-"*50)
            
            answer = result.get("final_answer", "응답 없음")
            print(answer)
            
            print("-"*50)
            print(f"에이전트: {result.get('target_agent', 'unknown')}")
            print(f"세션 ID: {result.get('session_id', 'N/A')}")
            
            # 상태 업데이트
            if result.get("session_id"):
                session_id = result["session_id"]
            message_count += 1
            
            # 제안 표시
            suggestions = result.get("suggested_actions", [])
            if suggestions:
                print("\n제안:")
                for i, s in enumerate(suggestions[:3], 1):
                    print(f"  {i}. {s}")
            
        except KeyboardInterrupt:
            print("\n\n테스트 중단")
            break
        except Exception as e:
            print(f"\n에러 발생: {e}")
            import traceback
            traceback.print_exc()


def main():
    """메인 실행"""
    asyncio.run(interactive_session())


if __name__ == "__main__":
    main()
