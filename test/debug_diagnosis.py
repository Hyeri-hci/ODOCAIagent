# tests/debug_diagnosis.py
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.agents.diagnosis.service import run_diagnosis

if __name__ == "__main__":
    payload = {
        "owner": "cn",
        "repo": "GB2260",
        "task_type": "full_diagnosis",
        "focus": ["documentation"],
        "user_context": {"level": "beginner"},
    }
  
try:
    result = run_diagnosis(payload)
    print(result)
except Exception:
    traceback.print_exc()
    traceback.print_exc()