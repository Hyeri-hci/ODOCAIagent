import sys
import os

# 프로젝트 루트 경로 확보
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/..")

from core.search.rag_query_generator import generate_rag_query_and_filters
from core.search.vector_search import vector_search_engine

def test_full_search_flow(user_input):
    print(f"\n🔵 [사용자 입력]: {user_input}")
    print("=" * 60)

    # 1. LLM: 쿼리, 필터, 그리고 '키워드' 추출
    generated = generate_rag_query_and_filters(
        user_request=user_input,
        category="semantic_search"
    )
    
    query = generated["query"]
    filters = generated["filters"]
    # 🚨 새로 추가된 키워드 리스트 가져오기
    keywords = generated.get("keywords", [])
    
    print(f"🧠 [LLM 분석 결과]")
    print(f"   👉 Query: {query}")
    print(f"   👉 Keywords: {keywords}") # 추출된 핵심 키워드 확인 (예: ['robot', 'control'])
    print(f"   👉 Filters: {filters}")
    print("-" * 60)

    # 2. Vector Search (Funnel Search + Keyword Filtering + Reranking)
    # 🚨 search 함수에 keywords 인자도 함께 전달합니다.
    result = vector_search_engine.search(
        query=query, 
        filters=filters, 
        keywords=keywords
    )
    
    recs = result.get("final_recommendations", [])
    
    print(f"✅ 최종 검색 결과: {len(recs)}건")
    
    if not recs:
        # 실패 메시지가 있으면 출력
        if "message" in result:
            print(f"   ⚠️ 결과: {result['message']}")
        return

    for i, item in enumerate(recs):
        # 리랭킹 점수가 있으면 그것을, 없으면 기본 검색 점수를 표시
        score = item.get('rerank_score') if item.get('rerank_score') else item.get('score')
        
        print(f"\n[{i+1}] {item.get('name')} (Score: {score})")
        print(f"    URL: {item.get('url')}")
        
        # 설명(Description)이 있으면 출력 (디버깅용)
        if item.get('description'):
            print(f"    Desc: {item.get('description')}")

        content = item.get('content', '')
        # 미리보기 텍스트 깔끔하게 정리
        preview = str(content)[:100].replace('\n', ' ') if content else "(내용 없음)"
        print(f"    Content: {preview}...")

if __name__ == "__main__":
    print("🔍 GitHub 의미 기반 검색 테스트 모드")
    print("q 또는 quit 입력 시 종료됩니다.\n")

    while True:
        user_input = input("\n🟣 검색어 입력: ").strip()

        if user_input.lower() in ["q", "quit"]:
            print("\n👋 테스트 종료합니다.")
            break
        
        if not user_input:
            print("⚠️ 입력이 비어있습니다. 다시 입력하세요.")
            continue

        test_full_search_flow(user_input)