import requests
import json

r = requests.post('http://localhost:8000/api/analyze', json={'repo_url': 'https://github.com/pallets/flask'})
data = r.json()

# Save to file
with open('api_test_result_v2.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print(f'Status: {r.status_code}')
print(f'Saved to api_test_result_v2.json')
print(f'score: {data.get("score")}')

print('\n=== Analysis ===')
analysis = data.get('analysis', {})
print(f"Interpretation: {analysis.get('health_score_interpretation')}")
print(f"Level Desc: {analysis.get('health_level_description')}")
print(f"Last Commit: {analysis.get('days_since_last_commit')} days ago")
print(f"Commits(30d): {analysis.get('total_commits_30d')}")
print(f"Contributors: {analysis.get('unique_contributors')}")
print(f"README Sections: {analysis.get('readme_sections')}")

print(f'\nrisks count: {len(data.get("risks", []))}')
if data.get("risks"):
    print(f"First risk: {data['risks'][0]['description']}")

print(f'actions count: {len(data.get("actions", []))}')

readme_summary = data.get("readme_summary")
print(f'has summary: {readme_summary is not None}')
if readme_summary:
    print(f"Summary len: {len(readme_summary)}")

rec_issues = data.get("recommended_issues")
print(f'\nRecommended Issues: {len(rec_issues) if rec_issues else 0}')
if rec_issues:
    print(f"First Issue: {rec_issues[0].get('title')} ({rec_issues[0].get('html_url')})")


