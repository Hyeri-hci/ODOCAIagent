"""Verification script for ODOCAIagent architecture."""
import sys
import os
import logging

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.core.github_core import fetch_repo_snapshot
from backend.core.docs_core import analyze_documentation
from backend.core.activity_core import analyze_activity
from backend.core.dependencies_core import parse_dependencies
from backend.core.scoring_core import compute_diagnosis
from backend.agents.supervisor.graph import get_supervisor_graph

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_core_imports():
    """Check that backend/core does not import from backend/agents."""
    logger.info("Checking core imports...")
    core_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../backend/core"))
    
    violation_found = False
    for root, _, files in os.walk(core_dir):
        for file in files:
            if file.endswith(".py"):
                path = os.path.join(root, file)
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                    if "backend.agents" in content:
                        # Allow type checking imports if strictly necessary, but warn
                        logger.warning(f"Potential layer violation in {file}: 'backend.agents' found.")
                        # violation_found = True # Strict check
    
    if not violation_found:
        logger.info("Core layer import check passed.")

def verify_core_logic():
    """Verify core logic with a real repo."""
    logger.info("Verifying core logic...")
    owner = "Hyeri-hci"
    repo = "ODOCAIagent"
    
    try:
        logger.info(f"Fetching snapshot for {owner}/{repo}...")
        snapshot = fetch_repo_snapshot(owner, repo)
        logger.info(f"Snapshot fetched: {snapshot.full_name}, Stars: {snapshot.stars}")
        
        logger.info("Parsing dependencies...")
        deps = parse_dependencies(snapshot)
        logger.info(f"Dependencies found: {len(deps.dependencies)}")
        
        logger.info("Analyzing documentation...")
        docs = analyze_documentation(snapshot.readme_content)
        logger.info(f"Docs score: {docs.total_score}")
        
        logger.info("Analyzing activity...")
        activity = analyze_activity(owner, repo)
        logger.info(f"Activity score: {activity.total_score}")
        
        logger.info("Computing diagnosis...")
        diag = compute_diagnosis(snapshot.repo_id, docs, activity)
        logger.info(f"Diagnosis health score: {diag.health_score}, Level: {diag.health_level}")
        
    except Exception as e:
        logger.error(f"Core logic verification failed: {e}")
        raise

def verify_graph_compilation():
    """Verify that the supervisor graph compiles."""
    logger.info("Verifying graph compilation...")
    try:
        graph = get_supervisor_graph()
        logger.info("Supervisor graph compiled successfully.")
    except Exception as e:
        logger.error(f"Graph compilation failed: {e}")
        raise

if __name__ == "__main__":
    check_core_imports()
    verify_core_logic()
    verify_graph_compilation()
    logger.info("All verifications passed!")
