import sys
import os

# Add current directory to sys.path
sys.path.append(os.getcwd())

try:
    from backend.agents.supervisor.models import SupervisorInput
    print("Import successful!")
except Exception as e:
    print(f"Import failed: {e}")
    import traceback
    traceback.print_exc()
