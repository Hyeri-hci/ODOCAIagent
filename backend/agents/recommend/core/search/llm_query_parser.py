import re
from typing import Dict, Tuple, Optional
from backend.agents.recommend.config.setting import settings
import logging

logger = logging.getLogger(__name__)

def parse_github_query(query_json: Dict) -> Tuple[str, Optional[str], Optional[str], Optional[str]]:
    """
    LLM이 생성한 JSON 쿼리를 GitHub Search API 파라미터로 변환.
    - 정규표현식을 사용하여 topic 문법 오류(공백, 따옴표 누락)를 지능적으로 교정
    - 최소 품질 기준 적용
    - 최대 조건 개수 제한
    """
    print("\n🟢 [QueryParser] Starting GitHub Query Parsing...")

    # 1. q 가져오기
    raw_q = query_json.get("q", "").strip()
    print(f"   - Initial raw query (q): '{raw_q}'")
    
    # -------------------------------------------------------------------------
    # [FIX] Topic 문법 지능형 교정 (Intelligent Correction)
    # -------------------------------------------------------------------------
    
    filter_keys = [
        "stars", "forks", "language", "pushed", "created", 
        "license", "archived", "good-first-issues", "topic", "is"
    ]
    
    # 정규식 설명: 'topic:' 뒤의 값을 다음 필터 키워드나 문자열 끝까지 캡처
    pattern = r'topic:\s*(.*?)(?=\s+(?:' + '|'.join(filter_keys) + r'):|$)'

    def fix_topic_syntax(match):
        content = match.group(1).strip()
        
        # 💡 [로그] 교정 전 값 출력
        logger.debug(f"   [Topic Fix] Found value: '{content}'")
        
        # 1. 값이 비어있으면(Dangling) -> 삭제 (빈 문자열 반환)
        if not content:
            return ""
        
        # 2. 이미 따옴표가 잘 씌워져 있는 경우 -> 그대로 유지 + 공백 제거
        if (content.startswith('"') and content.endswith('"')) or \
           (content.startswith("'") and content.endswith("'")):
            return f"topic:{content}"
        
        # 3. 내부에 공백이 있는 경우 -> 따옴표 씌우기
        if ' ' in content:
            return f'topic:"{content}"'
        
        # 4. 공백이 없는 단일 단어인 경우 -> 그대로 붙이기
        return f"topic:{content}"

    # 정규식 적용
    if "topic:" in raw_q.lower(): # 대소문자 구분 없이 'topic:'이 있는지 확인
        original_q_before_fix = raw_q
        raw_q = re.sub(pattern, fix_topic_syntax, raw_q, flags=re.IGNORECASE)
        
        # 다중 공백 정리
        raw_q = re.sub(r'\s+', ' ', raw_q).strip()

        print("   - Topic syntax correction applied.")
        logger.info(f"   [Correction Log] Before: '{original_q_before_fix}' -> After: '{raw_q}'")
    
    # -------------------------------------------------------------------------

    if not raw_q.strip():
        q = settings.github.base_search_query
        print(f"   - Query was empty. Using base query: '{q}'")
    else:
        q = raw_q

    # 3. 품질 조건 추가 로직
    q_parts = q.split()

    min_conditions = {
        "stars": f"stars:>={settings.github.DEFAULT_MIN_STARS}",
        "forks": f"forks:>={settings.github.DEFAULT_MIN_FORKS}",
        "pushed": f"pushed:>={settings.github.DEFAULT_PUSHED_AFTER}"
    }

    added_conditions = []
    
    # 조건 추가 (최대 5개 제한)
    for key, cond in min_conditions.items():
        # 이미 해당 조건이 있는지 확인 (대소문자 무시)
        if not any(part.lower().startswith(f"{key}:") for part in q_parts):
            if len(q_parts) < 5: 
                q_parts.append(cond)
                added_conditions.append(cond)

    if added_conditions:
        print(f"   - Added min quality filters: {', '.join(added_conditions)}")
    else:
        print("   - No min quality filters added (conditions already exist or limit reached).")
        
    # 5개로 자르기
    original_len = len(q_parts)
    q_parts = q_parts[:5]
    if original_len > 5:
        print(f"   ⚠️ Warning: Query length truncated from {original_len} to 5 conditions.")
        
    final_q = " ".join(q_parts)

    # 2. sort/order 처리
    sort = query_json.get("sort")
    if sort: sort = sort.strip()

    order = query_json.get("order")
    if order: order = order.strip()
    
    print(f"✅ [QueryParser] Final API Query (q): '{final_q}'")
    print(f"   - Sort/Order: {sort}/{order}")
    print("-------------------------------------------------------")

    return final_q, sort, order