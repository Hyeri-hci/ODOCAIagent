"""
CLI 실시간 채팅 테스트 스크립트

터미널에서 Supervisor 에이전트와 대화형으로 채팅하며 동작을 테스트할 수 있습니다.

Usage:
    python -m backend.scripts.chat_cli --owner <owner> --repo <repo>

Example:
    python -m backend.scripts.chat_cli --owner Hyeri-hci --repo OSSDoctor
"""

import asyncio
import argparse
import sys
from typing import Optional

# 프로젝트 루트 경로 설정
sys.path.insert(0, "d:\\dev\\ODOCAIagent")

from backend.agents.supervisor.graph import run_supervisor


# 색상 코드 (터미널 출력용)
class Colors:
    RESET = "\033[0m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    DIM = "\033[2m"


def print_header():
    """헤더 출력"""
    print(f"\n{Colors.BOLD}{'='*60}{Colors.RESET}")
    print(f"{Colors.CYAN}  Supervisor Agent CLI 채팅 테스트{Colors.RESET}")
    print(f"{Colors.BOLD}{'='*60}{Colors.RESET}")
    print(f"{Colors.DIM}  명령어: /quit (종료), /clear (세션 초기화), /help (도움말){Colors.RESET}")


def print_help():
    """도움말 출력"""
    print(f"\n{Colors.YELLOW}사용 가능한 명령어:{Colors.RESET}")
    print(f"  /quit, /exit, /q  - 채팅 종료")
    print(f"  /clear, /reset    - 세션 초기화 (새 대화 시작)")
    print(f"  /repo <owner/repo> - 분석 대상 저장소 변경")
    print(f"  /status           - 현재 상태 확인")
    print(f"  /help, /?         - 이 도움말 표시")
    print()


def print_status(owner: str, repo: str, session_id: Optional[str]):
    """현재 상태 출력"""
    print(f"\n{Colors.YELLOW}현재 상태:{Colors.RESET}")
    print(f"  저장소: {owner}/{repo}")
    print(f"  세션 ID: {session_id or '(신규)'}")
    print()


async def chat_loop(owner: str, repo: str):
    """메인 채팅 루프"""
    session_id: Optional[str] = None
    
    print_header()
    print(f"\n{Colors.GREEN}분석 대상 저장소: {owner}/{repo}{Colors.RESET}")
    print(f"{Colors.DIM}메시지를 입력하세요...{Colors.RESET}\n")
    
    while True:
        try:
            # 사용자 입력 받기
            user_input = input(f"{Colors.CYAN}[You] > {Colors.RESET}").strip()
            
            if not user_input:
                continue
            
            # 명령어 처리
            if user_input.startswith("/"):
                cmd = user_input.lower().split()[0]
                
                if cmd in ["/quit", "/exit", "/q"]:
                    print(f"\n{Colors.YELLOW}채팅을 종료합니다.{Colors.RESET}\n")
                    break
                    
                elif cmd in ["/clear", "/reset"]:
                    session_id = None
                    print(f"{Colors.GREEN}세션이 초기화되었습니다.{Colors.RESET}\n")
                    continue
                    
                elif cmd == "/repo":
                    parts = user_input.split()
                    if len(parts) >= 2 and "/" in parts[1]:
                        owner, repo = parts[1].split("/", 1)
                        session_id = None
                        print(f"{Colors.GREEN}저장소가 변경되었습니다: {owner}/{repo}{Colors.RESET}\n")
                    else:
                        print(f"{Colors.RED}사용법: /repo owner/repo{Colors.RESET}\n")
                    continue
                    
                elif cmd == "/status":
                    print_status(owner, repo, session_id)
                    continue
                    
                elif cmd in ["/help", "/?"]:
                    print_help()
                    continue
                    
                else:
                    print(f"{Colors.RED}알 수 없는 명령어: {cmd}{Colors.RESET}")
                    print(f"{Colors.DIM}/help 로 도움말을 확인하세요.{Colors.RESET}\n")
                    continue
            
            # Supervisor 실행
            print(f"{Colors.DIM}(처리 중...){Colors.RESET}")
            
            result = await run_supervisor(
                owner=owner,
                repo=repo,
                user_message=user_input,
                session_id=session_id
            )
            
            # 세션 ID 업데이트
            session_id = result.get("session_id")
            
            # 응답 출력
            final_answer = result.get("final_answer", "(응답 없음)")
            print(f"\n{Colors.GREEN}[Agent]{Colors.RESET}")
            print(f"{final_answer}\n")
            
            # Suggested actions 출력
            suggested_actions = result.get("suggested_actions", [])
            if suggested_actions:
                print(f"{Colors.YELLOW}제안 액션:{Colors.RESET}")
                for action in suggested_actions:
                    print(f"  - {action}")
                print()
            
            # Clarification 필요 여부
            if result.get("awaiting_clarification"):
                print(f"{Colors.YELLOW}(추가 정보가 필요합니다){Colors.RESET}\n")
                
        except KeyboardInterrupt:
            print(f"\n\n{Colors.YELLOW}채팅을 종료합니다.{Colors.RESET}\n")
            break
        except Exception as e:
            print(f"\n{Colors.RED}오류 발생: {e}{Colors.RESET}\n")
            import traceback
            traceback.print_exc()


def main():
    parser = argparse.ArgumentParser(
        description="Supervisor Agent CLI 채팅 테스트"
    )
    parser.add_argument(
        "--owner",
        type=str,
        default="Hyeri-hci",
        help="저장소 소유자 (기본값: Hyeri-hci)"
    )
    parser.add_argument(
        "--repo",
        type=str,
        default="ODOCAIagent",
        help="저장소 이름 (기본값: ODOCAIagent)"
    )
    
    args = parser.parse_args()
    
    try:
        asyncio.run(chat_loop(args.owner, args.repo))
    except KeyboardInterrupt:
        print("\n채팅을 종료합니다.")
        sys.exit(0)


if __name__ == "__main__":
    main()
