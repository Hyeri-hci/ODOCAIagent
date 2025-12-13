/**
 * 리포트 섹션별 가이드 및 도움말 데이터
 */
export const SECTION_GUIDES = {
    overview: {
        title: "종합 점수 (Health Score)",
        description: "프로젝트의 전반적인 운영 건강도를 나타냅니다.",
        formula: "문서 품질 × 30% + 활동성 × 70%",
        grades: [
            { label: "Excellent", range: "80점 이상", color: "green" },
            { label: "Good", range: "70-79점", color: "yellow" },
            { label: "Moderate", range: "50-69점", color: "orange" },
            { label: "Needs Attention", range: "50점 미만", color: "red" },
        ],
        tips: [
            "점수가 낮다면 활동성(커밋, 이슈 해결, PR 병합)이 저조하거나 문서화가 부족할 수 있습니다.",
            "점수가 높다면 꾸준한 커밋 활동, 빠른 이슈 해결, 좋은 문서화를 갖추고 있습니다.",
        ],
    },
    metrics: {
        title: "상세 메트릭",
        description:
            "CHAOSS 오픈소스 메트릭 표준을 기반으로 프로젝트 활동성을 측정합니다.",
        details: [
            {
                name: "커밋 점수 (40%)",
                items: [
                    "주당 10커밋 이상이면 빈도 만점",
                    "15일 이내 커밋 시 최신성 높음",
                    "5명 이상 기여자면 다양성 만점",
                ],
            },
            {
                name: "이슈 점수 (30%)",
                items: [
                    "이슈 50% 이상 해결 시 해결률 만점",
                    "30일 이내 해결 시 속도 높음",
                ],
            },
            {
                name: "PR 점수 (30%)",
                items: ["7일 이내 병합 시 속도 높음"],
            },
        ],
        tips: ["최근 90일간의 데이터를 기반으로 분석합니다."],
    },
    documentation: {
        title: "문서 품질",
        description: "README 파일의 완성도를 평가합니다.",
        categories: [
            { name: "WHAT", desc: "프로젝트가 무엇인지", required: true },
            { name: "WHY", desc: "왜 만들었는지", required: true },
            { name: "HOW", desc: "설치/사용 방법", required: true },
            { name: "CONTRIBUTING", desc: "기여 방법", required: true },
            { name: "WHO/WHEN/REFERENCES", desc: "부가 정보", required: false },
        ],
        formula:
            "필수 카테고리 충족률 × 70% + 선택 카테고리 × 30% + 보너스(코드 예시)",
        tips: ["코드 블록과 사용 예시가 있으면 +10점 보너스가 적용됩니다."],
    },
    security: {
        title: "보안 분석",
        description: "프로젝트 의존성의 알려진 취약점을 검사합니다.",
        details: [
            { name: "데이터 소스", desc: "NVD (National Vulnerability Database)" },
            { name: "분석 대상", desc: "package.json, requirements.txt, go.mod 등" },
        ],
        severities: [
            { label: "Critical", range: "CVSS 9.0+", color: "red" },
            { label: "High", range: "CVSS 7.0-8.9", color: "orange" },
            { label: "Medium", range: "CVSS 4.0-6.9", color: "yellow" },
            { label: "Low", range: "CVSS 0.1-3.9", color: "gray" },
        ],
    },
    risks: {
        title: "위험 요소",
        description: "분석 결과를 바탕으로 잠재적 문제점을 자동으로 감지합니다.",
        riskTypes: [
            {
                category: "문서",
                items: ["문서 점수 < 40", "필수 섹션(WHAT/WHY/HOW) 누락"],
            },
            {
                category: "활동성",
                items: ["활동성 점수 < 30", "최근 커밋 없음", "이슈 해결률 낮음"],
            },
            {
                category: "의존성",
                items: ["의존성 100개 이상", "버전 미고정 30% 이상"],
            },
        ],
        tips: ["발견된 위험 요소에 따라 '추천 기여 작업'이 자동 생성됩니다."],
    },
    recommendedTasks: {
        title: "추천 첫 기여 이슈",
        description: "입문자 친화적 라벨이 붙은 열린 이슈를 찾아 추천합니다.",
        labels: [
            "good first issue",
            "help wanted",
            "beginner",
            "easy",
            "first-timers-only",
            "hacktoberfest",
            "docs",
        ],
        tips: [
            "위 라벨이 붙은 이슈 중 최근 생성된 순서로 표시됩니다.",
            "라벨 있는 이슈가 3개 미만이면 최근 열린 이슈가 추가됩니다.",
        ],
    },
    contributions: {
        title: "추천 기여 작업",
        description: "발견된 위험 요소에 따라 개선 작업을 제안합니다.",
        examples: [
            { problem: "문서화 부족", action: "README 보완" },
            { problem: "설치 방법 없음", action: "설치 가이드 작성" },
            { problem: "기여 가이드 없음", action: "CONTRIBUTING.md 작성" },
            { problem: "비활성 프로젝트", action: "미해결 이슈 작업" },
        ],
        tips: ["작업이 없다면 프로젝트가 이미 잘 관리되고 있다는 의미입니다."],
    },
    similarProjects: {
        title: "유사 프로젝트",
        description: "분석된 프로젝트와 비교할 수 있는 유사 프로젝트를 추천합니다.",
        criteria: [
            { purpose: "학습용", sort: "온보딩 점수 높은 순" },
            { purpose: "기여용", sort: "활동성 60% + 문서화 40%" },
            { purpose: "프로덕션 참고", sort: "건강도 점수 높은 순" },
        ],
        tips: ["비교 분석 시에만 표시될 수 있습니다."],
    },
    onboarding: {
        title: "온보딩 용이성",
        description: "신규 기여자가 프로젝트에 참여하기 쉬운 정도를 나타냅니다.",
        formula: "문서 품질 × 60% + 활동성 × 40%",
        grades: [
            { label: "Easy", range: "75점 이상", color: "green" },
            { label: "Normal", range: "55-74점", color: "yellow" },
            { label: "Hard", range: "55점 미만", color: "red" },
        ],
        tips: ["문서화 품질에 더 높은 가중치를 둡니다."],
    },
};
