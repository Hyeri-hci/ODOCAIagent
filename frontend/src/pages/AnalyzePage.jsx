import React, { useState, useEffect } from "react";
import UserProfileForm from "../components/analyze/UserProfileForm";
import AnalysisChat from "../components/analyze/AnalysisChat";
import AnalysisLoading from "../components/analyze/AnalysisLoading";
import { analyzeRepository } from "../lib/api";

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

  const handleProfileSubmit = async (profileData) => {
    setUserProfile(profileData);
    setStep("loading");
    setError(null);

    try {
      // 실제 백엔드 API 호출
      const apiResponse = await analyzeRepository(profileData.repositoryUrl);

      // API 응답을 프론트엔드 형식으로 변환
      const analysis = apiResponse.analysis || {};
      const transformedResult = {
        repositoryUrl: profileData.repositoryUrl,
        analysisId: apiResponse.job_id || `analysis_${Date.now()}`,
        summary: {
          score: apiResponse.score || analysis.health_score || 0,
          healthStatus:
            analysis.health_level === "good"
              ? "excellent"
              : analysis.health_level === "warning"
              ? "moderate"
              : "needs-attention",
          contributionOpportunities: (apiResponse.recommended_issues || [])
            .length,
          estimatedImpact:
            analysis.health_score >= 70
              ? "high"
              : analysis.health_score >= 50
              ? "medium"
              : "low",
        },
        projectSummary:
          apiResponse.readme_summary ||
          `이 저장소의 건강 점수는 ${apiResponse.score}점입니다. ${
            analysis.health_score_interpretation || ""
          }`,
        recommendations: (apiResponse.actions || []).map((action, idx) => ({
          id: `rec_${idx + 1}`,
          title: action.title,
          description: action.description,
          difficulty: action.priority === "high" ? "easy" : "medium",
          estimatedTime: action.duration,
          impact: action.priority,
          tags: action.url ? ["good-first-issue"] : ["improvement"],
          url: action.url,
          issueNumber: action.issue_number,
        })),
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
            analysis.days_since_last_commit !== null
              ? `${analysis.days_since_last_commit}일 전`
              : "알 수 없음",
          openIssues: analysis.open_issues_count || 0,
          contributors: analysis.unique_contributors || 0,
          stars: 0,
          forks: 0,
          // 새 메트릭 추가
          issueCloseRate: analysis.issue_close_rate_pct || "N/A",
          prMergeTime: analysis.median_pr_merge_days_text || "N/A",
          totalCommits30d: analysis.total_commits_30d || 0,
        },
        relatedProjects: [],
        // 추천 이슈 (Good First Issues)
        recommendedIssues: apiResponse.recommended_issues || [],
        // 원본 API 응답 보관
        rawAnalysis: analysis,
      };

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

      {step === "loading" && <AnalysisLoading userProfile={userProfile} />}

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
