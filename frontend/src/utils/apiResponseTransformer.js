/**
 * API 응답을 Frontend 형식으로 변환하는 유틸리티
 * Backend API 응답 구조에 맞춰 최적화됨
 */

/**
 * Backend API 응답을 Frontend 분석 결과 형식으로 변환
 * @param {Object} apiResponse - Backend API 응답
 * @param {string} repositoryUrl - 저장소 URL
 * @returns {Object} Frontend 분석 결과 객체
 */
export const transformApiResponse = (apiResponse, repositoryUrl) => {
  // Backend 응답 구조: { job_id, score, analysis, risks, actions, ... }
  // SSE 응답은 { result: { ... } } 또는 직접 데이터
  const rawData = apiResponse.result || apiResponse;
  const analysis = rawData.analysis || rawData;
  const healthScore = rawData.score || analysis.health_score || 0;

  return {
    repositoryUrl,
    analysisId: rawData.job_id || analysis.repo_id || `analysis_${Date.now()}`,

    // 요약 정보
    summary: {
      score: healthScore,
      healthStatus: getHealthStatus(healthScore),
      healthLevel: analysis.health_level || "unknown",
      healthLevelDescription: analysis.health_level_description || "",
      healthScoreInterpretation: analysis.health_score_interpretation || "",
      onboardingScore: analysis.onboarding_score || 0,
      onboardingLevel: analysis.onboarding_level || "unknown",
      contributionOpportunities: (
        rawData.recommended_issues ||
        analysis.recommended_issues ||
        []
      ).length,
      estimatedImpact: getImpactLevel(healthScore),
    },

    // 프로젝트 요약 (AI 생성)
    projectSummary: rawData.readme_summary || analysis.summary_for_user || "",

    // 추천 작업 (actions + recommended_issues)
    recommendations: [
      ...(rawData.actions || analysis.actions || []).map((action, idx) => ({
        id: `action_${idx + 1}`,
        title: action.title,
        description: action.description,
        difficulty: action.priority === "high" ? "easy" : "medium",
        estimatedTime: action.duration,
        impact: action.priority,
        tags: action.url ? ["good-first-issue"] : ["improvement"],
        url: action.url,
        issueNumber: action.issue_number,
      })),
      ...(rawData.recommended_issues || analysis.recommended_issues || []).map(
        (issue, idx) => ({
          id: `issue_${issue.number || idx}`,
          title: issue.title,
          description: `GitHub Issue #${issue.number}`,
          difficulty: getIssueDifficulty(issue.labels),
          estimatedTime: "2-4시간",
          impact: "medium",
          tags: issue.labels || ["issue"],
          url: issue.url,
          issueNumber: issue.number,
        })
      ),
    ],

    // 위험 요소
    risks: (rawData.risks || analysis.risks || []).map((risk, idx) => ({
      id: `risk_${idx + 1}`,
      type: risk.type || "general",
      severity: risk.severity || "medium",
      description: risk.description,
    })),

    // 상세 기술 정보
    technicalDetails: {
      // 기본 저장소 메트릭
      stars: analysis.stars || 0,
      forks: analysis.forks || 0,
      contributors: analysis.unique_contributors || 0,
      openIssues: analysis.open_issues_count || 0,
      openPRs: analysis.open_prs_count || 0,

      // 활동성 메트릭
      lastCommit: formatLastCommit(analysis.days_since_last_commit),
      totalCommits30d: analysis.total_commits_30d || 0,

      // 품질 점수 (100점 만점)
      documentationQuality: analysis.documentation_quality || 0,
      activityMaintainability: analysis.activity_maintainability || 0,
      onboardingScore: analysis.onboarding_score || 0,
      dependencyComplexity: analysis.dependency_complexity_score || 0,

      // 상세 메트릭
      issueCloseRate: analysis.issue_close_rate || 0,
      issueCloseRatePct: analysis.issue_close_rate_pct || "N/A",
      medianPRMergeDays: analysis.median_pr_merge_days,
      medianPRMergeDaysText: analysis.median_pr_merge_days_text || "N/A",
      medianIssueCloseDays: analysis.median_issue_close_days,
      medianIssueCloseDaysText: analysis.median_issue_close_days_text || "N/A",

      // README 섹션 정보
      readmeSections: analysis.readme_sections || {},
    },

    // 추천 이슈 목록 (별도 보관)
    recommendedIssues:
      rawData.recommended_issues || analysis.recommended_issues || [],

    // 온보딩 플랜
    onboardingPlan: rawData.onboarding_plan || analysis.onboarding_plan || null,

    // AI 채팅 응답
    chatResponse: rawData.chat_response || analysis.chat_response || null,

    // 보안 분석 결과
    security: rawData.security || analysis.security || null,

    // 유사 프로젝트 추천
    similarProjects:
      rawData.similar_projects ||
      analysis.similar_projects ||
      rawData.similar ||
      [],

    // 메타 에이전트 결과
    taskPlan: rawData.task_plan || analysis.task_plan || null,
    taskResults: rawData.task_results || analysis.task_results || null,

    // Agentic 플로우 결과 (warnings, flow_adjustments)
    warnings: analysis.warnings || [],
    flowAdjustments: analysis.flow_adjustments || [],

    // 신규 기여자 가이드 (contributor 에이전트 결과)
    contributorGuide: rawData.contributor_guide || analysis.contributor_guide || null,
    firstContributionGuide: rawData.first_contribution_guide || analysis.first_contribution_guide || null,
    contributionChecklist: rawData.contribution_checklist || analysis.contribution_checklist || null,
    communityAnalysis: rawData.community_analysis || analysis.community_analysis || null,
    issueMatching: rawData.issue_matching || analysis.issue_matching || null,
    structureVisualization: rawData.structure_visualization || analysis.structure_visualization || null,

    // 비교 분석 결과 (compare 에이전트 결과)
    compareResults: rawData.compare_results || analysis.compare_results || null,
    compareSummary: rawData.compare_summary || analysis.compare_summary || null,

    // 원본 analysis 객체 (필요시 참조용)
    rawAnalysis: analysis,
  };
};

// === Helper Functions ===

function getHealthStatus(score) {
  if (score >= 80) return "excellent";
  if (score >= 60) return "good";
  if (score >= 40) return "moderate";
  return "needs-attention";
}

function getImpactLevel(score) {
  if (score >= 70) return "high";
  if (score >= 50) return "medium";
  return "low";
}

function getIssueDifficulty(labels = []) {
  const easyLabels = [
    "easy",
    "first",
    "beginner",
    "good first issue",
    "help wanted",
  ];
  const hasEasyLabel = labels.some((l) =>
    easyLabels.some((easy) => l.toLowerCase().includes(easy))
  );
  return hasEasyLabel ? "easy" : "medium";
}

function formatLastCommit(days) {
  if (days === null || days === undefined) return "알 수 없음";
  if (days === 0) return "오늘";
  if (days === 1) return "어제";
  return `${days}일 전`;
}

export default transformApiResponse;
