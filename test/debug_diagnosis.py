# tests/debug_diagnosis.py
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.agents.diagnosis.service import run_diagnosis

if __name__ == "__main__":
    payload = {
        "owner": "microsoft",
        "repo": "vscode",
        "task_type": "full_diagnosis",
        "focus": ["documentation"],
        "user_context": {"level": "beginner"},
    }
    result = run_diagnosis(payload)
    docs = result.get("details", {}).get("docs", {})
    print("=== readme_category_score ===")
    print(docs.get("readme_category_score"))
    print("\n=== readme_categories ===")
    import json
    print(json.dumps(docs.get("readme_categories", {}), indent=2, ensure_ascii=False))
    print("\n=== docs_overall_summary ===")
    print(result.get("docs_overall_summary"))
