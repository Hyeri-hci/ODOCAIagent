
import argparse
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.agents.supervisor.service import run_supervisor_diagnosis

def main():
    parser = argparse.ArgumentParser(description="Run ODOCAIagent Diagnosis via Supervisor")
    parser.add_argument("--owner", required=True, help="Repository owner")
    parser.add_argument("--repo", required=True, help="Repository name")
    parser.add_argument("--ref", default="main", help="Repository reference (default: main)")
    
    args = parser.parse_args()
    
    print(f"Starting diagnosis for {args.owner}/{args.repo} (ref: {args.ref})...")
    
    try:
        result = run_supervisor_diagnosis(args.owner, args.repo, args.ref)
        
        if result:
            print("\n=== Diagnosis Result ===")
            print(f"Health Score: {result.health_score} ({result.health_level})")
            print(f"Docs Quality: {result.documentation_quality}")
            print(f"Activity Score: {result.activity_maintainability}")
            print(f"Onboarding Score: {result.onboarding_score} ({result.onboarding_level})")
            print("\nIssues:")
            print(f"- Docs: {', '.join(result.docs_issues) or 'None'}")
            print(f"- Activity: {', '.join(result.activity_issues) or 'None'}")
        else:
            print("\nDiagnosis failed or returned no result.")
            sys.exit(1)
            
    except Exception as e:
        print(f"\nError during diagnosis: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
