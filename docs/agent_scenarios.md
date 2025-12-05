# ODOC Agent Hero Scenarios

## 1. diagnose_repo
- **목적**: 특정 OSS 레포의 건강도 및 온보딩 난이도 진단.
- **입력**:
  - `owner` (str): 필수
  - `repo` (str): 필수
- **출력**:
  - `health_score` (0~100)
  - `health_level` ("good" | "warning" | "bad")
  - `onboarding_score` (0~100)
  - `onboarding_level` ("easy" | "medium" | "hard")
  - 주요 메트릭 요약 (docs/activity/structure)
  - 사용자용 자연어 요약 (`summary_for_user`)

### 입력 예시(JSON)

```json
{
  "task_type": "diagnose_repo",
  "owner": "Hyeri-hci",
  "repo": "ODOCAIagent"
}
```

### 출력 예시(JSON, 축약)

```json
{
  "task_type": "diagnose_repo",
  "ok": true,
  "data": {
    "diagnosis": {
      "repo_id": "Hyeri-hci/ODOCAIagent",
      "health_score": 78.5,
      "health_level": "warning",
      "onboarding_score": 62.0,
      "onboarding_level": "hard",
      "summary_for_user": "...",
      "docs": { "...": "..." },
      "activity": { "...": "..." },
      "structure": { "...": "..." }
    }
  }
}
```

## 2. build_onboarding_plan

- **목적**: 특정 레포에 대해 1~4주 OSS 온보딩 플랜 및 추천 이슈/PR을 생성.
- **입력**:
  - `owner` (str): 필수
  - `repo` (str): 필수
  - `user_context` (dict): 사용자 프로필
    - `experience_level`: "beginner" | "junior" | "senior"
    - `experience_days`: int (예: 10) - **Hero Scenario Persona**
    - `primary_language`: str
    - `time_per_week_hours`: int
    - `goals`: string 배열

### 입력 예시(JSON) - Hero Persona (신입 10일차)

```json
{
  "task_type": "build_onboarding_plan",
  "owner": "facebook",
  "repo": "react",
  "user_context": {
    "experience_level": "junior",
    "experience_days": 10,
    "primary_language": "TypeScript",
    "time_per_week_hours": 10,
    "goals": ["frontend 경험", "대형 OSS 코드리딩 경험"]
  }
}
```

### 출력 예시(JSON, 축약)

```json
{
  "task_type": "build_onboarding_plan",
  "ok": true,
  "data": {
    "diagnosis": { "...": "..." },
    "onboarding_plan": {
      "weeks": [
        { "week": 1, "goals": ["..."], "tasks": ["..."] },
        { "week": 2, "goals": ["..."], "tasks": ["..."] }
      ]
    },
    "candidate_issues": [
      { "number": 123, "title": "...", "labels": ["good first issue"] }
    ]
  }
}
```
