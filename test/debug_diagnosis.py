# tests/debug_diagnosis.py
import os
import sys
import json
import traceback

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.agents.diagnosis.service import run_diagnosis

if __name__ == "__main__":
    payload = {
        "owner": "Hyeri-hci",
        "repo": "OSSDoctor",
        "task_type": "full_diagnosis",
        "focus": ["documentation"],
        "user_context": {"level": "beginner"},
    }

    try:
        result = run_diagnosis(payload)
        docs = result.get("details", {}).get("docs", {})
        
        print("=== readme_category_score ===")
        print(docs.get("readme_category_score"))
        
        print("\n=== 통합 README 요약 ===")
        print(f"[임베딩용 영어] {docs.get('readme_summary_for_embedding', '(없음)')[:400]}")
        print(f"\n[사용자용 한국어] {docs.get('readme_summary_for_user', '(없음)')}")
        
        print("\n=== readme_categories (with semantic_summary_en) ===")
        categories = docs.get("readme_categories", {})
        for cat_name, cat_info in categories.items():
            print(f"\n--- {cat_name} ---")
            print(f"  present: {cat_info.get('present')}")
            print(f"  coverage_score: {cat_info.get('coverage_score', 0):.2f}")
            semantic = cat_info.get("semantic_summary_en", "")
            if semantic:
                print(f"  semantic_summary_en: {semantic[:200]}...")
            else:
                print(f"  semantic_summary_en: (없음)")
        
        print("\n=== natural_language_summary_for_user (진단 전체 요약) ===")
        print(result.get("natural_language_summary_for_user", "")[:800])
        
    except Exception:
        traceback.print_exc()