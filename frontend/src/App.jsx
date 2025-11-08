import React, { useState } from "react";
import { ArrowUp } from "lucide-react";

// Hooks
import { useAnalysisFlow } from "./hooks/useAnalysisFlow";

// Layout
import { AppLayout } from "./components/layout/AppLayout";

// Common Components
import { LoadingOverlay } from "./components/common/LoadingOverlay";
import { PrimaryButton } from "./components/common/PrimaryButton";
import { SecondaryButton } from "./components/common/SecondaryButton";

// Analysis Components
import { AnalysisSummaryCard } from "./components/analysis/AnalysisSummaryCard";
import { ReadmeSummary } from "./components/analysis/ReadmeSummary";
import { DetectedRisksList } from "./components/analysis/DetectedRisksList";
import { RecommendedContributionsList } from "./components/analysis/RecommendedContributionsList";
import { RelatedProjectsSection } from "./components/analysis/RelatedProjectsSection";

// Existing Components (to be gradually migrated)
import HeroSection from "./components/HeroSection";
import AnalyzeForm from "./components/AnalyzeForm";

/**
 * Refactored ODOC AI Agent Application
 * Using unified component architecture
 */
function App() {
  const {
    // State
    isLoading,
    isCompleted,
    hasResult,
    analysisResult,
    notification,
    isCreatingMilestone,
    isSendingReport,

    // Actions
    startAnalysis,
    createMilestoneForActions,
    sendAnalysisReport,
  } = useAnalysisFlow();

  const [selectedActions, setSelectedActions] = useState([]);

  // Scroll helpers
  const scrollToAnalyze = () => {
    const analyzeSection = document.getElementById("analyze");
    if (analyzeSection) {
      analyzeSection.scrollIntoView({ behavior: "smooth" });
    }
    setTimeout(() => {
      const input = document.querySelector('#analyze input[type="text"]');
      if (input) {
        input.focus();
      }
    }, 500);
  };

  const scrollToResults = () => {
    document.getElementById("results")?.scrollIntoView({ behavior: "smooth" });
  };

  // Action handlers
  const handleAnalyze = async (repoUrl) => {
    await startAnalysis(repoUrl);
  };

  const handleCreateMilestone = async () => {
    if (selectedActions.length > 0 && analysisResult) {
      await createMilestoneForActions(selectedActions, analysisResult.analysis);
    }
  };

  const handleSendReport = async () => {
    if (analysisResult) {
      await sendAnalysisReport(analysisResult);
    }
  };

  return (
    <AppLayout notification={notification}>
      {/* Hero Section */}
      <HeroSection onAnalyzeClick={scrollToAnalyze} />

      {/* Analyze Form Section */}
      <div id="analyze">
        <AnalyzeForm
          onAnalyze={handleAnalyze}
          isAnalyzing={isLoading}
          hasResult={hasResult}
        />
      </div>

      {/* Analysis Results Section */}
      {hasResult && analysisResult && (
        <div id="results">
          <section className="py-16 bg-[#F9FAFB] animate-fadeIn">
            <div className="container mx-auto px-4">
              <div className="max-w-7xl mx-auto animate-slideUp">
                {/* Section Title */}
                <div className="text-center mb-12">
                  <div className="inline-flex items-center gap-3 bg-gradient-to-r from-[#2563EB] to-[#1E3A8A] px-6 py-3 rounded-2xl shadow-lg mb-4">
                    <svg
                      className="w-6 h-6 text-white"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M5 13l4 4L19 7"
                      />
                    </svg>
                    <span className="text-white font-bold text-lg">
                      분석 완료
                    </span>
                  </div>
                  <h2 className="text-4xl md:text-5xl font-black text-[#1E3A8A] mb-4">
                    분석 결과 리포트
                  </h2>
                  <p className="text-lg text-slate-600">
                    AI가 프로젝트를 종합적으로 분석한 결과입니다
                  </p>
                </div>

                {/* Analysis Summary Card */}
                <AnalysisSummaryCard
                  repoName={analysisResult.analysis?.repo_name || "Repository"}
                  score={analysisResult.score}
                  metrics={{
                    security: 85,
                    quality: 92,
                    activity: 78,
                  }}
                  stats={{
                    stars: analysisResult.analysis?.stars || 0,
                    forks: analysisResult.analysis?.forks || 0,
                    contributors: analysisResult.analysis?.contributors || 0,
                  }}
                  isCompleted={true}
                />

                {/* README Summary */}
                {analysisResult.readme_summary && (
                  <ReadmeSummary
                    content={analysisResult.readme_summary}
                    className="mt-6"
                  />
                )}

                {/* Action Area: Risks + Contributions */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
                  <DetectedRisksList risks={analysisResult.risks} />
                  <RecommendedContributionsList
                    actions={analysisResult.actions}
                    onSelectionChange={setSelectedActions}
                  />
                </div>

                {/* CTA Buttons */}
                <div className="flex flex-col sm:flex-row gap-4 justify-center pt-4 mt-6">
                  <SecondaryButton
                    onClick={() => window.open("#", "_blank")}
                    icon={() => (
                      <svg
                        className="w-5 h-5"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
                        />
                      </svg>
                    )}
                  >
                    View Full Report
                  </SecondaryButton>

                  <SecondaryButton
                    onClick={handleCreateMilestone}
                    disabled={selectedActions.length === 0}
                    loading={isCreatingMilestone}
                    variant="success"
                    icon={() => (
                      <svg
                        className="w-5 h-5"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
                        />
                      </svg>
                    )}
                  >
                    {isCreatingMilestone
                      ? "Creating..."
                      : "Contribute Now with Kakao"}
                  </SecondaryButton>
                </div>

                {/* Related Projects Section */}
                {analysisResult.similar && (
                  <RelatedProjectsSection
                    projects={analysisResult.similar}
                    onAnalyzeProject={(url) => handleAnalyze(url)}
                  />
                )}

                {/* Back to Top Button */}
                <div className="mt-12 text-center">
                  <PrimaryButton
                    onClick={scrollToAnalyze}
                    icon={ArrowUp}
                    size="lg"
                  >
                    새로운 프로젝트 분석하기
                  </PrimaryButton>
                  <p className="text-sm text-gray-500 mt-4">
                    다른 오픈소스 프로젝트를 분석하고 싶으신가요?
                  </p>
                </div>
              </div>
            </div>
          </section>
        </div>
      )}

      {/* How It Works Section - Only show when no result */}
      {!hasResult && (
        <section className="py-20 bg-[#F9FAFB]">
          <div className="container mx-auto px-4">
            <div className="max-w-6xl mx-auto">
              <div className="text-center mb-16">
                <h2 className="text-4xl md:text-5xl font-black text-[#1E3A8A] mb-4">
                  How It Works
                </h2>
                <p className="text-xl text-slate-600">
                  간단한 3단계로 오픈소스 기여를 시작하세요
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
                <ProcessStep
                  number="1"
                  title="프로젝트 분석"
                  description="GitHub URL을 입력하면 AI가 프로젝트의 건강도, 활동성, 보안 상태를 종합적으로 분석합니다."
                  features={[
                    "CVE 보안 검출",
                    "코드 품질 분석",
                    "커뮤니티 활성도",
                  ]}
                  color="from-[#2563EB] to-[#1E3A8A]"
                  iconColor="text-[#2563EB]"
                />

                <ProcessStep
                  number="2"
                  title="맞춤 추천"
                  description="당신의 실력과 관심사에 맞는 기여 작업을 AI가 추천하고, 우선순위와 예상 소요시간을 알려드립니다."
                  features={[
                    "난이도별 작업 분류",
                    "소요시간 예측",
                    "우선순위 설정",
                  ]}
                  color="from-purple-500 to-purple-700"
                  iconColor="text-purple-600"
                />

                <ProcessStep
                  number="3"
                  title="일정 관리"
                  description="선택한 작업을 마일스톤으로 생성하고 카카오톡 캘린더에 자동으로 등록하여 체계적으로 관리하세요."
                  features={[
                    "카카오톡 자동 연동",
                    "마일스톤 생성",
                    "진행상황 추적",
                  ]}
                  color="from-emerald-500 to-emerald-700"
                  iconColor="text-emerald-600"
                />
              </div>
            </div>
          </div>
        </section>
      )}

      {/* Loading Overlay */}
      <LoadingOverlay isVisible={isLoading} />
    </AppLayout>
  );
}

/**
 * Process Step Component for "How It Works"
 */
const ProcessStep = ({
  number,
  title,
  description,
  features,
  color,
  iconColor,
}) => (
  <div className="group bg-white rounded-2xl p-8 shadow-soft hover:shadow-2xl transition-all duration-300 border border-slate-100 hover:border-[#2563EB] hover:scale-105">
    <div
      className={`w-20 h-20 bg-gradient-to-br ${color} rounded-2xl flex items-center justify-center text-white text-3xl font-black mb-6 shadow-lg group-hover:shadow-xl transition-shadow`}
    >
      {number}
    </div>
    <h3 className="text-2xl font-bold text-slate-800 mb-4">{title}</h3>
    <p className="text-slate-600 leading-relaxed mb-4">{description}</p>
    <div className={`text-sm ${iconColor} font-semibold`}>
      {features.map((feature, idx) => (
        <div key={idx}>✓ {feature}</div>
      ))}
    </div>
  </div>
);

export default App;
