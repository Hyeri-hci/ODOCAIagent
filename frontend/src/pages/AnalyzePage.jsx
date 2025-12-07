import React, { useState, useEffect } from "react";
import UserProfileForm from "../components/analyze/UserProfileForm";
import AnalysisChat from "../components/analyze/AnalysisChat";
import AnalysisLoading from "../components/analyze/AnalysisLoading";
import { analyzeRepository, setCachedAnalysis } from "../lib/api";

// SSE 스트리밍 사용 여부 (true: SSE, false: 기존 REST API)
const USE_STREAM_MODE = true;

const AnalyzePage = () => {
  const [step, setStep] = useState("profile"); // profile, loading, chat
  const [userProfile, setUserProfile] = useState(null);
  const [analysisResult, setAnalysisResult] = useState(null);
  const [error, setError] = useState(null);

  // 분석 완료 후 페이지 상단으로 스크롤 (Header 높이 고려)
  useEffect(() => {
    if (step === "chat") {
      // Header 높이(약 72px)를 고려하여 스크롤
      setTimeout(() => {
        window.scrollTo({ top: 0, behavior: "smooth" });
      }, 100);
    }
  }, [step]);

  // SSE 결과 또는 REST API 결과를 프론트엔드 형식으로 변환
  const transformAnalysisResult = (apiResponse, repositoryUrl) => {
    const analysis = apiResponse.analysis || apiResponse;

    console.log("=== API 응답 디버그 ===");
    console.log("Analysis object:", JSON.stringify(analysis, null, 2));

    return {
      repositoryUrl: repositoryUrl,
      analysisId:
        apiResponse.job_id || analysis.repo_id || `analysis_${Date.now()}`,
      summary: {
        score: apiResponse.score || analysis.health_score || 0,
        healthStatus:
          analysis.health_level === "good"
            ? "excellent"
            : analysis.health_level === "warning"
            ? "moderate"
            : "needs-attention",
        contributionOpportunities: (
          apiResponse.recommended_issues ||
          analysis.recommended_issues ||
          []
        ).length,
        estimatedImpact:
          (analysis.health_score || 0) >= 70
            ? "high"
            : (analysis.health_score || 0) >= 50
            ? "medium"
            : "low",
      },
      projectSummary:
        apiResponse.readme_summary ||
        analysis.summary_for_user ||
        `이 저장소의 건강 점수는 ${
          apiResponse.score || analysis.health_score
        }점입니다. ${analysis.health_score_interpretation || ""}`,
      recommendations: [
        // 기존 actions
        ...(apiResponse.actions || []).map((action, idx) => ({
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
        // recommended_issues에서 추가
        ...(
          apiResponse.recommended_issues ||
          analysis.recommended_issues ||
          []
        ).map((issue, idx) => ({
          id: `issue_${issue.number || idx}`,
          title: issue.title,
          description: `GitHub Issue #${issue.number}`,
          difficulty: issue.labels?.some(
            (l) =>
              l.toLowerCase().includes("easy") ||
              l.toLowerCase().includes("first")
          )
            ? "easy"
            : "medium",
          estimatedTime: "2-4시간",
          impact: "medium",
          tags: issue.labels || ["issue"],
          url: issue.url,
          issueNumber: issue.number,
        })),
      ],
      risks: (apiResponse.risks || []).map((risk, idx) => ({
        id: `risk_${idx + 1}`,
        type: risk.type || "general",
        severity: risk.severity || "medium",
        description: risk.description,
      })),
      technicalDetails: {
        languages: [],
        framework: "Unknown",
        testCoverage: 0,
        dependencies: analysis.dependency_complexity_score || 0,
        lastCommit:
          analysis.days_since_last_commit !== null &&
          analysis.days_since_last_commit !== undefined
            ? `${analysis.days_since_last_commit}일 전`
            : "알 수 없음",
        openIssues: analysis.open_issues_count || 0,
        contributors: analysis.unique_contributors || 0,
        stars: analysis.stars || 0,
        forks: analysis.forks || 0,
        // 점수 (100점 만점)
        documentationQuality: analysis.documentation_quality || 0,
        activityMaintainability: analysis.activity_maintainability || 0,
        // 새 메트릭 추가
        issueCloseRate:
          analysis.issue_close_rate_pct ||
          (analysis.issue_close_rate
            ? `${(analysis.issue_close_rate * 100).toFixed(1)}%`
            : "N/A"),
        prMergeTime:
          analysis.median_pr_merge_days_text ||
          (analysis.median_pr_merge_days
            ? `${analysis.median_pr_merge_days.toFixed(1)}일`
            : "N/A"),
        totalCommits30d: analysis.total_commits_30d || 0,
      },
      relatedProjects: [],
      // 추천 이슈 (Good First Issues)
      recommendedIssues:
        apiResponse.recommended_issues || analysis.recommended_issues || [],
      // 원본 API 응답 보관
      rawAnalysis: analysis,
      // 온보딩 플랜 (API 응답에서 가져오기)
      onboardingPlan:
        apiResponse.onboarding_plan || analysis.onboarding_plan || null,
      // Agentic 플로우 결과
      warnings: analysis.warnings || [],
      flowAdjustments: analysis.flow_adjustments || [],
    };
  };

  // SSE 완료 핸들러
  const handleStreamComplete = (sseResult) => {
    console.log("SSE 분석 완료:", sseResult);

    const repoUrl = userProfile?.repositoryUrl || sseResult?.repo_id || "";

    // SSE 결과를 캐시에 저장 (채팅에서 같은 URL 입력시 재사용)
    const cacheData = { ...sseResult, analysis: sseResult };
    setCachedAnalysis(repoUrl, cacheData);
    console.log("[SSE] Cached result for:", repoUrl);

    const transformed = transformAnalysisResult(cacheData, repoUrl);
    setAnalysisResult(transformed);
    setStep("chat");
  };

  // SSE 에러 핸들러
  const handleStreamError = (errorMessage) => {
    console.error("SSE 분석 실패:", errorMessage);
    setError(errorMessage);
    setStep("profile");
  };

  // REST API 방식 분석 (fallback)
  const handleProfileSubmit = async (profileData) => {
    setUserProfile(profileData);
    setStep("loading");
    setError(null);

    // SSE 모드일 경우 AnalysisLoading에서 처리
    if (USE_STREAM_MODE) {
      return;
    }

    // 기존 REST API 방식
    try {
      const apiResponse = await analyzeRepository(profileData.repositoryUrl);
      const transformedResult = transformAnalysisResult(
        apiResponse,
        profileData.repositoryUrl
      );
      setAnalysisResult(transformedResult);
      setStep("chat");
    } catch (err) {
      console.error("분석 실패:", err);
      setError(err.message || "분석 중 오류가 발생했습니다.");
      setStep("profile");
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 via-white to-gray-50">
      {step === "profile" && (
        <UserProfileForm onSubmit={handleProfileSubmit} error={error} />
      )}

      {step === "loading" && (
        <AnalysisLoading
          userProfile={userProfile}
          useStream={USE_STREAM_MODE}
          onComplete={handleStreamComplete}
          onError={handleStreamError}
        />
      )}

      {step === "chat" && (
        <AnalysisChat
          userProfile={userProfile}
          analysisResult={analysisResult}
        />
      )}
    </div>
  );
};

export default AnalyzePage;
