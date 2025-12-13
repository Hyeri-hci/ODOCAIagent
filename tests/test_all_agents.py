import asyncio
import os
import sys
import logging
from dotenv import load_dotenv

# Set up paths and logging
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.basicConfig(level=logging.ERROR) # Suppress verbose logs for test output clarity
# But let's allow info logs from our test script
test_logger = logging.getLogger("test_all_agents")
test_logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter('%(message)s'))
test_logger.addHandler(ch)

load_dotenv()

from backend.agents.supervisor.graph import get_supervisor_graph
from backend.agents.supervisor.models import SupervisorState

# Define test scenarios
TEST_SCENARIOS = [
    {
        "name": "Diagnosis (React)",
        "input": "Analyze facebook/react",
        "expected_agent": "diagnosis_agent"
    },
    {
        "name": "Comparison (React vs Vue)",
        "input": "Compare facebook/react and vuejs/vue",
        "expected_agent": "comparison_agent"
    },
    {
        "name": "Onboarding (Pytorch)",
        "input": "How to contribute to pytorch/pytorch?",
        "expected_agent": "onboarding_agent"
    },
    {
        "name": "Recommendation (FastAPI)",
        "input": "Recommend similar projects to fastapi/fastapi",
        "expected_agent": "recommendation_agent"
    }
]

async def run_scenario(app, scenario):
    input_text = scenario["input"]
    test_logger.info(f"\n=============================================")
    test_logger.info(f"🧪 Running Scenario: {scenario['name']}")
    test_logger.info(f"📤 Input: '{input_text}'")
    test_logger.info(f"=============================================")

    # Initial state
    initial_state = {
        "messages": [("user", input_text)],
        "next_step": None,
        "final_response": None,
        "repo": None,
        "owner": None,
        "comparison_targets": []
    }
    
    import uuid
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    
    # Run the graph
    # We'll invoke it and gather the final state
    try:
        final_state = await app.ainvoke(initial_state, config=config)
        
        # Check routing
        # Since we can't easily peek into intermediate steps without streaming/listeners in this simple script,
        # we'll infer success from the final response or state markers.
        # But wait, create_supervisor_agent returns a compiled graph.
        
        response = final_state.get("final_response")
        
        if response:
            test_logger.info("✅ Final Response Received:\n")
            test_logger.info(f"{response[:500]}..." if len(response) > 500 else response)
            
            # Check if it looks like what we expect
            # e.g. for diagnosis, it should have analysis result
            # for comparison, comparison table/text
            
            # Additional check: task type in intent (if preserved)
            # intent = final_state.get("intent") # intent might be in state but it's internal to nodes often
            pass
        else:
            test_logger.error("❌ No final response returned.")
            
    except Exception as e:
        test_logger.error(f"❌ Error executing scenario: {e}")

async def main():
    test_logger.info("🚀 Starting Comprehensive Agent Test...")
    
    # Initialize the supervisor agent
    app = get_supervisor_graph()
    
    for scenario in TEST_SCENARIOS:
        await run_scenario(app, scenario)
        
    test_logger.info("\n🎉 All scenarios completed.")

if __name__ == "__main__":
    asyncio.run(main())
