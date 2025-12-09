import asyncio
import json
from pprint import pprint
from agent.graph import app

def print_separator(title: str):
    print("\n" + "=" * 80)
    print(f" {title} ")
    print("=" * 80)

async def run_agent_interactive():
    """사용자 입력을 받아 Agent를 실행하고 상세 로그를 출력합니다."""
    
    print_separator("🤖 GitHub 프로젝트 추천 에이전트 실행 시작")
    
    # 1. 사용자 입력 받기
    user_query = input("👉 프로젝트 추천을 위한 질문을 입력하세요: ")
    
    inputs = {"user_query": user_query}
    
    print_separator(f"🔍 쿼리 분석 시작: '{user_query}'")
    
    # 2. LangGraph 실행 및 스트리밍 출력
    # astream을 사용하여 각 노드가 실행될 때마다 상태 변화를 확인합니다.
    try:
        async for output in app.astream(inputs):
            for node_name, state_value in output.items():
                
                # 최종 노드 이후의 __end__는 무시
                if node_name == '__end__':
                    continue
                
                # 3. 노드별 작업 및 상태 변화 출력
                print(f"\n➡️ [NODE EXECUTION] {node_name} 실행 완료")
                
                # 라우터 (Router)의 출력
                if 'category' in state_value:
                    category = state_value['category']
                    print(f"  [Router 🚦] 라우팅 결과: '{category}' 경로 선택")
                
                # 쿼리 생성 노드의 출력
                if 'search_queries' in state_value:
                    print(f"  [Search Gen] GitHub API 쿼리 파라미터 생성 완료.")
                if 'rag_queries' in state_value:
                    print(f"  [RAG Gen] 벡터 검색 쿼리/필터 생성 완료.")
                
                # 실행 노드의 상태 및 결과
                if 'last_status' in state_value:
                    status = state_value['last_status']
                    print(f"  [Status] 이전 실행 상태: {status}")
                if 'raw_candidates' in state_value:
                    count = len(state_value['raw_candidates'])
                    print(f"  [Execution] 검색 후보: {count}개 획득.")
                
                # 최종 추천 노드의 출력
                if 'final_result' in state_value:
                    print_separator("🎁 최종 에이전트 추천 답변")
                    final_results = state_value['final_result']
                    
                    if isinstance(final_results, str):
                        # JSON 형태의 답변을 예쁘게 출력 시도
                        try:
                            pprint(json.loads(final_results), indent=2)
                        except json.JSONDecodeError:
                            print(final_results)
                    else:
                        pprint(final_results) # 리스트 또는 딕셔너리 그대로 출력
                    
                    print_separator("✅ 에이전트 워크플로우 종료")
                    return # 최종 결과가 나오면 종료
                    
    except Exception as e:
        print_separator("❌ 에이전트 실행 중 오류 발생")
        print(f"오류 상세: {e}")
        print_separator("⚠️ 워크플로우 비정상 종료")


if __name__ == "__main__":
    # Windows 환경에서 비동기 관련 오류 발생 시 아래 주석 해제 (Select Event Loop 정책 적용)
    # import platform
    # if platform.system() == "Windows":
    #     asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    asyncio.run(run_agent_interactive())