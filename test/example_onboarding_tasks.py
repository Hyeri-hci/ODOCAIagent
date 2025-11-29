"""
Onboarding Tasks 실제 동작 테스트.

실제 GitHub API를 호출하여 저장소의 기여 가능한 Task 목록을 확인합니다.
새로운 구조: reason_tags, meta_flags, fallback_reason
"""
import json
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

from backend.agents.diagnosis.service import run_diagnosis


def main():
    # 테스트할 저장소
    repos = [
        ("Hyeri-hci", "OSSDoctor"),
        ("facebookarchive", "flux"),
    ]
    
    for owner, repo in repos:
        print("\n" + "=" * 70)
        print(f"Repository: {owner}/{repo}")
        print("=" * 70)
        
        result = run_diagnosis({
            "owner": owner,
            "repo": repo,
            "task_type": "full",
        })
        
        # 기본 정보
        scores = result.get("scores", {})
        labels = result.get("labels", {})
        print(f"\n건강 점수: {scores.get('health_score')}/100")
        print(f"온보딩 점수: {scores.get('onboarding_score')}/100")
        print(f"건강 레벨: {labels.get('health_level')}")
        print(f"온보딩 레벨: {labels.get('onboarding_level')}")
        print(f"문서 이슈: {labels.get('docs_issues')}")
        print(f"활동 이슈: {labels.get('activity_issues')}")
        
        # Onboarding Tasks
        tasks = result.get("onboarding_tasks")
        if not tasks:
            print("\n[!] onboarding_tasks 블록 없음")
            continue
        
        meta = tasks.get("meta", {})
        print(f"\n총 Task 수: {meta.get('total_count')}")
        print(f"  - 이슈 기반: {meta.get('issue_count')}")
        print(f"  - 메타 Task: {meta.get('meta_count')}")
        
        # 난이도별 출력
        for difficulty in ["beginner", "intermediate", "advanced"]:
            task_list = tasks.get(difficulty, [])
            print(f"\n{difficulty.upper()} ({len(task_list)}개):")
            for task in task_list[:5]:  # 최대 5개만 출력
                level = task.get("level", "?")
                kind = task.get("kind", "?")
                title = task.get("title", "")[:50]
                task_id = task.get("id", "")
                
                # 새로운 필드
                reason_tags = task.get("reason_tags", [])
                meta_flags = task.get("meta_flags", [])
                fallback_reason = task.get("fallback_reason", "")
                
                print(f"  [Lv.{level}] [{kind}] {title}")
                print(f"         ID: {task_id}")
                if reason_tags:
                    print(f"         태그: {reason_tags}")
                if meta_flags:
                    print(f"         플래그: {meta_flags}")
                if fallback_reason:
                    print(f"         Fallback: {fallback_reason[:60]}...")
    
    print("\n" + "=" * 70)
    print("테스트 완료!")
    print("=" * 70)


if __name__ == "__main__":
    main()
