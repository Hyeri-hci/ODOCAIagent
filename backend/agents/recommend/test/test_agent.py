import logging
import time
import asyncio
import re  # 정규 표현식 모듈 임포트
from typing import Dict, Any, Optional

# backend.agents.recommend.agent.graph 파일에서 run_recommend 함수를 임포트합니다.
from backend.agents.recommend.agent.graph import run_recommend 

logger = logging.getLogger("TestRealAgent")
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(name)s | %(message)s')


logger = logging.getLogger("TestRealAgent")
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(name)s | %(message)s')

# ------------------------------------------------------------------
# 1. 입력 파싱 유틸리티 함수
# ------------------------------------------------------------------
def parse_single_input(full_input: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """
    하나의 문자열 입력에서 GitHub URL (owner/repo)과 순수 메시지를 파싱합니다.
    """
    owner = None
    repo = None
    message = full_input.strip()

    # 정규식: (https?://github.com/)?(owner)/(repo) 형태 캡처
    github_pattern = re.compile(
        r'(?:https?://github\.com/)?([a-zA-Z0-9_-]+)/([a-zA-Z0-9_-]+)(?:[\s/].*)?'
    )
    
    match = github_pattern.search(full_input)

    if match:
        owner = match.group(1)
        repo = match.group(2)
        
        # URL/owner/repo 부분을 메시지에서 제거하여 순수 메시지만 남깁니다.
        message = github_pattern.sub('', full_input).strip()
        
        # 공백이 여러 개이거나 기호가 남아있을 수 있으므로 추가 정리
        message = ' '.join(message.split()).strip()

    if not message:
        message = None

    return owner, repo, message

# ------------------------------------------------------------------
# 2. 테스트 실행 함수
# ------------------------------------------------------------------

async def interactive_test_main():
    """
    사용자로부터 한 번의 입력을 받아 URL과 메시지를 파싱하여 에이전트를 실행합니다.
    """
    print("\n=======================================================")
    print("        🚀 GitHub 추천 에이전트 인터랙티브 테스트")
    print("=======================================================")
    
    # 1. 사용자로부터 단일 입력 받기
    full_input = input("👉 URL (owner/repo) 및 요청 메시지를 한 줄로 입력하세요: ")
    
    # 2. 입력 파싱
    owner, repo, user_message = parse_single_input(full_input)

    print(owner, repo, user_message)

    user_message_safe = user_message if user_message is not None else "" # ⭐️ 추가된 안전 코드

    print(f"\n[INFO] 분석 시작:")
    print(f"       - 파싱된 URL: {owner}/{repo}")
    print(f"       - 파싱된 요청: '{user_message}'")

    # 3. 에이전트 실행
    start_time_total = time.time()
    try:
        final_state_dict = await run_recommend(
            owner=owner,
            repo=repo,
            user_message=user_message_safe
        )
        
        elapsed_total = round(time.time() - start_time_total, 3)

    except Exception as e:
        print(f"\n❌ 에이전트 실행 중 치명적인 오류 발생: {e}")
        return
    
    final_result = final_state_dict.get("search_results", [])
    print(final_result)

    # 4. 결과 출력
    print("\n======== 📊 최종 결과 보고서 ========")
    
    # 딕셔너리 접근 시 None 체크
    search_results = final_state_dict.get('search_results') if isinstance(final_state_dict, dict) else None
    
    if search_results:
        final_state_obj = final_state_dict 
        
        # --- 메타데이터 ---
        print(f"🔎 [Metadata]")
        print(f"   - Intent: {final_state_obj.get('user_intent', 'N/A')}")
        print(f"   - Query: {final_state_obj.get('search_query', 'N/A')}")
        print(f"🔹 Total Time: {elapsed_total}s")
        
        # --- 추천 결과 (개별 이유 포함) ---
        print(f"\n🏆 [Recommended Projects] Found: {len(search_results)} (Showing Top 3)")
        
        for idx, item in enumerate(search_results, 1): 
            # item은 CandidateRepo (Dict 형태로 가정)
            reason = item.ai_reason or '평가 이유 없음'
            stars = item.stars
            name = item.name
            main_language = item.main_language
            #url = item.url
            
            print(f"   {idx}. {name} (⭐ {stars})")
            #print(f"      - URL: {url}")
            print(f"      - Lang: {main_language}")
            print(f"      - 📝 ⭐️ 추천 이유: {reason}...")
            print("-" * 50)
            
    else:
        # 에러 메시지가 상태에 있을 경우 출력
        error_msg = final_state_dict.get('error') if final_state_dict and isinstance(final_state_dict, dict) else 'N/A'
        print(f"❌ 검색 및 분석 결과가 없습니다. (Error: {error_msg})")
    
    print("\n=======================================================")


if __name__ == "__main__":
    asyncio.run(interactive_test_main())