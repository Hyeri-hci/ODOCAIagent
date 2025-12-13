import React, { useState } from "react";
import ReactMarkdown from "react-markdown";
import {
  ChevronDown,
  ChevronUp,
  Star,
  GitFork,
  Users,
  Activity,
  TrendingUp,
  CheckCircle,
  AlertTriangle,
  AlertCircle,
  FileText,
  Clock,
  GitPullRequest,
  MessageSquare,
  Shield,
  Zap,
  Target,
  BookOpen,
  Lightbulb,
  FolderGit2,
  ExternalLink,
  Info,
  GitBranch,
  Code2,
  HelpCircle,
} from "lucide-react";
import { formatNumber } from "../../utils/formatNumber";
import OnboardingPlanSection from "./OnboardingPlanSection";
import ContributorGuideSection from "./ContributorGuideSection";
import { AnalysisReportSkeleton } from "./SkeletonLoader";
import ExportReportButton from "./ExportReportButton";

// === 섹션별 가이드 정보 ===
const SECTION_GUIDES = {
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

// === 가이드 메시지 포맷 함수 ===
const formatGuideMessage = (guide) => {
  let message = `📖 **${guide.title}**\n\n${guide.description}`;

  if (guide.formula) {
    message += `\n\n---\n\n**📊 계산 공식**\n\n\`${guide.formula}\``;
  }

  if (guide.grades) {
    message += `\n\n---\n\n**📈 등급 기준**\n`;
    guide.grades.forEach((g) => {
      const emoji =
        g.color === "green"
          ? "🟢"
          : g.color === "yellow"
            ? "🟡"
            : g.color === "orange"
              ? "🟠"
              : "🔴";
      message += `\n- ${emoji} **${g.label}**: ${g.range}`;
    });
  }

  if (guide.details) {
    message += `\n\n---\n\n**📋 상세 정보**`;
    guide.details.forEach((d) => {
      if (d.items) {
        message += `\n\n**${d.name}**`;
        d.items.forEach((item) => {
          message += `\n- ${item}`;
        });
      } else {
        message += `\n- **${d.name}**: ${d.desc}`;
      }
    });
  }

  if (guide.severities) {
    message += `\n\n---\n\n**⚠️ 취약점 심각도**\n`;
    guide.severities.forEach((s) => {
      message += `\n- **${s.label}**: ${s.range}`;
    });
  }

  if (guide.riskTypes) {
    message += `\n\n---\n\n**🔍 감지 기준**`;
    guide.riskTypes.forEach((r) => {
      message += `\n\n**${r.category} 관련**`;
      r.items.forEach((item) => {
        message += `\n- ${item}`;
      });
    });
  }

  if (guide.labels) {
    message += `\n\n---\n\n**🏷️ 검색 라벨**\n\n${guide.labels.join(", ")}`;
  }

  if (guide.examples) {
    message += `\n\n---\n\n**📝 추천 작업 예시**\n`;
    guide.examples.forEach((ex) => {
      message += `\n- ${ex.problem} → **${ex.action}**`;
    });
  }

  if (guide.criteria) {
    message += `\n\n---\n\n**🎯 정렬 기준**\n`;
    guide.criteria.forEach((c) => {
      message += `\n- **${c.purpose}**: ${c.sort}`;
    });
  }

  if (guide.tips && guide.tips.length > 0) {
    message += `\n\n---\n\n**💡 팁**\n`;
    guide.tips.forEach((tip) => {
      message += `\n- ${tip}`;
    });
  }

  return message;
};

// === 섹션 순서 상수 ===
const SECTION_ORDER = [
  "overview",
  "metrics",
  "projectSummary",
  "security",
  "contributor",
  "risks",
  "recommendedTasks",
  "contributions",
  "similarProjects",
];

// === 메인 컴포넌트 ===
const AnalysisReportSection = ({
  analysisResult,
  isLoading = false,
  onSendGuideMessage,
}) => {
  const [expandedSections, setExpandedSections] = useState({
    onboarding: true,
    overview: true,
    metrics: true,
    projectSummary: true,
    security: true,
    recommendedTasks: true,
    contributions: true,
    risks: true,
    similarProjects: true,
  });

  const toggleSection = (section) => {
    setExpandedSections((prev) => ({ ...prev, [section]: !prev[section] }));
  };

  // 가이드 메시지를 채팅으로 보내는 함수
  const handleOpenGuide = (guideKey) => {
    if (onSendGuideMessage && SECTION_GUIDES[guideKey]) {
      const guide = SECTION_GUIDES[guideKey];
      const message = formatGuideMessage(guide);
      onSendGuideMessage(message);
    }
  };

  // 로딩 중일 때 스켈레톤 표시
  if (isLoading) {
    return <AnalysisReportSkeleton />;
  }

  // 데이터가 없을 때 Empty State
  // summary 없어도 온보딩 플랜, 보안 결과, 추천 결과 등이 있으면 리포트 표시
  const hasAnyContent =
    analysisResult &&
    (analysisResult.summary ||
      (Array.isArray(analysisResult.onboardingPlan) &&
        analysisResult.onboardingPlan.length > 0) ||
      analysisResult.onboardingPlan?.plan?.length > 0 ||
      analysisResult.security ||
      analysisResult.recommendations?.length > 0 ||
      analysisResult.similarProjects?.length > 0); // 추천 결과 포함

  if (!hasAnyContent) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-12 text-center">
        <div className="w-16 h-16 bg-gray-100 dark:bg-gray-700 rounded-xl flex items-center justify-center mx-auto mb-4">
          <FileText className="w-8 h-8 text-gray-400" />
        </div>
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
          분석 결과가 없습니다
        </h3>
        <p className="text-sm text-gray-500 dark:text-gray-400 max-w-sm mx-auto">
          GitHub 저장소 URL을 입력하면 AI가 프로젝트를 분석하여 상세한 리포트를
          생성합니다.
        </p>
      </div>
    );
  }

  const { summary, technicalDetails, rawAnalysis } = analysisResult || {};
  const statusConfig = getStatusConfig(summary?.score || 0);

  // 데이터 유효성 검사 함수
  const hasValidOverviewData = () => {
    return (
      summary?.score > 0 ||
      technicalDetails?.stars > 0 ||
      technicalDetails?.forks > 0 ||
      technicalDetails?.contributors > 0 ||
      technicalDetails?.documentationQuality > 0 ||
      technicalDetails?.activityMaintainability > 0
    );
  };

  const hasValidMetricsData = () => {
    return (
      technicalDetails?.daysSinceLastCommit !== undefined ||
      technicalDetails?.commits30d > 0 ||
      technicalDetails?.issueCloseRate > 0 ||
      technicalDetails?.prMergeSpeed !== undefined ||
      technicalDetails?.openIssues > 0 ||
      technicalDetails?.openPRs > 0
    );
  };

  // 섹션 렌더링 함수
  const renderSection = (sectionId) => {
    switch (sectionId) {
      case "overview":
        // 유효한 데이터가 없으면 표시하지 않음
        if (!hasValidOverviewData()) return null;
        return (
          <div key="overview">
            <CollapsibleCard
              title="분석 결과 리포트"
              isExpanded={expandedSections.overview}
              onToggle={() => toggleSection("overview")}
              guideKey="overview"
              onOpenGuide={handleOpenGuide}
            >
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
                <div className="lg:col-span-4">
                  <ScoreCard
                    score={summary.score}
                    statusConfig={statusConfig}
                  />
                </div>
                <div className="lg:col-span-8">
                  <h2 className="text-2xl font-black text-gray-900 mb-6">
                    Repository Statistics
                  </h2>
                  <div className="grid grid-cols-3 gap-4 mb-6">
                    <StatCard
                      icon={Star}
                      value={formatNumber(technicalDetails?.stars || 0)}
                      label="GitHub Stars"
                      borderColor="border-yellow-200"
                      iconColor="text-yellow-500"
                    />
                    <StatCard
                      icon={GitFork}
                      value={formatNumber(technicalDetails?.forks || 0)}
                      label="Forks"
                      borderColor="border-cyan-200"
                      iconColor="text-cyan-600"
                    />
                    <StatCard
                      icon={Users}
                      value={formatNumber(technicalDetails?.contributors || 0)}
                      label="Contributors"
                      borderColor="border-purple-200"
                      iconColor="text-purple-600"
                    />
                  </div>
                  <div className="space-y-4">
                    <MetricBar
                      label="문서 품질"
                      value={technicalDetails?.documentationQuality || 0}
                      color="green"
                    />
                    <MetricBar
                      label="활동성/유지보수"
                      value={technicalDetails?.activityMaintainability || 0}
                      color="blue"
                    />
                    <MetricBar
                      label="온보딩 용이성"
                      value={
                        technicalDetails?.onboardingScore ||
                        rawAnalysis?.onboarding_score ||
                        0
                      }
                      color="purple"
                    />
                  </div>
                </div>
              </div>
            </CollapsibleCard>
          </div>
        );

      case "metrics":
        // 유효한 메트릭 데이터가 없으면 표시하지 않음
        if (!hasValidMetricsData()) return null;
        return (
          <div key="metrics">
            <CollapsibleCard
              title="상세 메트릭"
              icon={<Zap className="w-5 h-5 text-gray-500" />}
              subtitle="프로젝트 활동성과 응답성 지표"
              isExpanded={expandedSections.metrics}
              onToggle={() => toggleSection("metrics")}
              guideKey="metrics"
              onOpenGuide={handleOpenGuide}
            >
              <DetailedMetrics technicalDetails={technicalDetails} />
            </CollapsibleCard>
          </div>
        );

      case "projectSummary":
        if (!analysisResult.projectSummary) return null;
        return (
          <div key="projectSummary">
            <CollapsibleCard
              title="프로젝트 요약"
              icon={<FileText className="w-5 h-5 text-gray-500" />}
              isExpanded={expandedSections.projectSummary}
              onToggle={() => toggleSection("projectSummary")}
            >
              <ProjectSummary
                summary={analysisResult.projectSummary}
                interpretation={summary.healthScoreInterpretation}
                levelDescription={summary.healthLevelDescription}
              />
            </CollapsibleCard>
          </div>
        );

      case "security":
        // 보안 결과가 있거나, 명시적으로 보안 분석이 요청된 경우 표시
        // securityRequested는 analysisResult에 추가됨
        if (!analysisResult.security && !analysisResult.securityRequested)
          return null;
        return (
          <div key="security">
            <CollapsibleCard
              title="보안 분석"
              icon={<Shield className="w-5 h-5 text-gray-500" />}
              subtitle={
                analysisResult.security
                  ? `취약점 ${analysisResult.security.vulnerability_count || 0
                  }개 발견`
                  : "분석 완료"
              }
              isExpanded={expandedSections.security}
              onToggle={() => toggleSection("security")}
              guideKey="security"
              onOpenGuide={handleOpenGuide}
            >
              {analysisResult.security ? (
                <SecuritySection security={analysisResult.security} />
              ) : (
                <EmptySecuritySection />
              )}
            </CollapsibleCard>
          </div>
        );

      case "risks":
        if (!analysisResult.risks?.length) return null;
        return (
          <div key="risks">
            <CollapsibleCard
              title="발견된 위험 요소"
              icon={<AlertTriangle className="w-5 h-5 text-gray-500" />}
              subtitle={`${analysisResult.risks.length}개 위험 요소`}
              isExpanded={expandedSections.risks}
              onToggle={() => toggleSection("risks")}
              guideKey="risks"
              onOpenGuide={handleOpenGuide}
            >
              <div className="space-y-3">
                {analysisResult.risks.map((risk) => (
                  <RiskItem key={risk.id} risk={risk} />
                ))}
              </div>
            </CollapsibleCard>
          </div>
        );

      case "recommendedTasks":
        if (!analysisResult.recommendedIssues?.length) return null;
        return (
          <div key="recommendedTasks">
            <CollapsibleCard
              title="추천 첫 기여 이슈"
              icon={<Lightbulb className="w-5 h-5 text-gray-500" />}
              subtitle={`입문자를 위한 ${analysisResult.recommendedIssues.length}개 이슈`}
              isExpanded={expandedSections.recommendedTasks}
              onToggle={() => toggleSection("recommendedTasks")}
              guideKey="recommendedTasks"
              onOpenGuide={handleOpenGuide}
            >
              <RecommendedIssuesSection
                issues={analysisResult.recommendedIssues}
              />
            </CollapsibleCard>
          </div>
        );

      case "contributions":
        if (!analysisResult.recommendations?.length) return null;
        return (
          <div key="contributions">
            <CollapsibleCard
              title="추천 기여 작업"
              icon={<Target className="w-5 h-5 text-gray-500" />}
              subtitle={`${analysisResult.recommendations.length}개 작업 추천`}
              isExpanded={expandedSections.contributions}
              onToggle={() => toggleSection("contributions")}
              guideKey="contributions"
              onOpenGuide={handleOpenGuide}
            >
              <ContributionsSection
                recommendations={analysisResult.recommendations}
              />
            </CollapsibleCard>
          </div>
        );

      case "similarProjects":
        // 유사 프로젝트 데이터가 없으면 표시하지 않음
        if (!analysisResult.similarProjects?.length) return null;
        return (
          <div key="similarProjects">
            <CollapsibleCard
              title="유사 프로젝트 추천"
              icon={<FolderGit2 className="w-5 h-5 text-gray-500" />}
              subtitle={`${analysisResult.similarProjects.length}개 프로젝트 추천`}
              isExpanded={expandedSections.similarProjects}
              onToggle={() => toggleSection("similarProjects")}
              guideKey="similarProjects"
              onOpenGuide={handleOpenGuide}
            >
              <SimilarProjectsSection
                projects={analysisResult.similarProjects}
              />
            </CollapsibleCard>
          </div>
        );


      case "contributor":
        // 신규 기여자 가이드 데이터가 없으면 표시하지 않음
        if (
          !analysisResult.contributorGuide?.markdown &&
          !analysisResult.contributorGuide &&
          !analysisResult.firstContributionGuide &&
          !analysisResult.contributionChecklist &&
          !analysisResult.structureVisualization
        )
          return null;
        return (
          <div key="contributor">
            <ContributorGuideSection
              contributorGuide={analysisResult.contributorGuide}
              firstContributionGuide={analysisResult.firstContributionGuide}
              contributionChecklist={analysisResult.contributionChecklist}
              communityAnalysis={analysisResult.communityAnalysis}
              issueMatching={analysisResult.issueMatching}
              structureVisualization={analysisResult.structureVisualization}
            />
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <div className="relative space-y-3">
      {/* 리포트 헤더 - 내보내기 버튼 */}
      <div className="flex items-center justify-end mb-2">
        <ExportReportButton analysisResult={analysisResult} />
      </div>

      {/* 온보딩 가이드 (고정 - 항상 최상단) */}
      {/* 배열인 경우: 직접 length 체크, 객체인 경우: plan 필드에서 추출 */}
      {(Array.isArray(analysisResult.onboardingPlan)
        ? analysisResult.onboardingPlan.length > 0
        : analysisResult.onboardingPlan?.plan?.length > 0) && (
          <OnboardingPlanSection
            plan={
              Array.isArray(analysisResult.onboardingPlan)
                ? analysisResult.onboardingPlan
                : analysisResult.onboardingPlan?.plan || []
            }
            userProfile={{ repositoryUrl: analysisResult.repositoryUrl }}
            onGeneratePlan={() => {
              if (onSendGuideMessage) {
                // 캐시 무시하고 새로 생성하도록 명시적 키워드 포함
                onSendGuideMessage(
                  "온보딩 플랜을 새로 다시 생성해줘 (캐시 무시)",
                  { asUserMessage: true }
                );
              }
            }}
          />
        )}

      {/* 섹션 목록 */}
      <div className="space-y-4">
        {SECTION_ORDER.map((sectionId) => renderSection(sectionId))}
      </div>
    </div>
  );
};

// === 서브 컴포넌트들 ===

// 로딩 오버레이
const LoadingOverlay = () => (
  <div className="absolute inset-0 bg-white/80 backdrop-blur-sm z-50 rounded-3xl flex items-center justify-center">
    <div className="text-center">
      <div className="relative w-20 h-20 mx-auto mb-4">
        <div className="absolute inset-0 border-4 border-blue-200 rounded-full"></div>
        <div className="absolute inset-0 border-4 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
      </div>
      <p className="text-lg font-semibold text-gray-900 mb-1">분석 중입니다</p>
      <p className="text-sm text-gray-600">
        새로운 프로젝트를 분석하고 있습니다...
      </p>
    </div>
  </div>
);

// 점수 카드
const ScoreCard = ({ score, statusConfig }) => (
  <div className="bg-gray-800 dark:bg-gray-900 rounded-xl p-6 h-full relative overflow-hidden">
    {/* 배경 장식 */}
    <div
      className={`absolute top-0 right-0 w-32 h-32 ${statusConfig.bgGlow} opacity-20 blur-3xl`}
    />

    <div className="flex items-center gap-3 mb-5 relative">
      <div className="w-10 h-10 bg-gray-700 rounded-lg flex items-center justify-center">
        <TrendingUp className="w-5 h-5 text-gray-300" />
      </div>
      <div>
        <h3 className="text-white font-medium">Health Score</h3>
        <p className="text-gray-400 text-sm">프로젝트 분석</p>
      </div>
    </div>

    <div className="bg-white dark:bg-gray-800 rounded-xl p-5 text-center mb-5 relative">
      {/* 점수 표시 */}
      <div className="mb-3">
        <span className="text-5xl font-bold text-gray-900 dark:text-white">
          {score}
        </span>
        <span className="text-2xl text-gray-400 dark:text-gray-500">/100</span>
      </div>
      <div className="text-gray-500 dark:text-gray-400 text-sm mb-3">
        종합 점수
      </div>
      {/* 프로그레스 바 */}
      <div className="h-2 bg-gray-100 dark:bg-gray-700 rounded-full overflow-hidden">
        <div
          className={`h-full ${statusConfig.barColor || "bg-blue-500"
            } transition-all duration-500`}
          style={{ width: `${score}%` }}
        />
      </div>
    </div>

    <div
      className={`${statusConfig.bgColor} ${statusConfig.borderColor} border px-4 py-2.5 rounded-lg flex items-center gap-2 justify-center`}
    >
      <CheckCircle className={`w-4 h-4 ${statusConfig.textColor}`} />
      <span className={`${statusConfig.textColor} font-medium text-sm`}>
        {statusConfig.label}
      </span>
    </div>
  </div>
);

// 통계 카드
const StatCard = (props) => {
  const { icon: Icon, value, label, borderColor, iconColor } = props;
  return (
    <div
      className={`bg-gray-50 dark:bg-gray-800 rounded-xl p-4 border ${borderColor || "border-gray-200 dark:border-gray-700"
        } hover:shadow-md transition-shadow`}
    >
      <Icon className={`w-5 h-5 ${iconColor} mb-2`} />
      <div className="text-2xl font-bold text-gray-900 dark:text-white mb-1">
        {value}
      </div>
      <div className="text-xs text-gray-500 dark:text-gray-400">{label}</div>
    </div>
  );
};

// 메트릭 바
const MetricBar = ({ label, value, color }) => {
  const colorConfig = {
    green: { text: "text-green-600 dark:text-green-400", bar: "bg-green-500" },
    blue: { text: "text-blue-600 dark:text-blue-400", bar: "bg-blue-500" },
    purple: {
      text: "text-purple-600 dark:text-purple-400",
      bar: "bg-purple-500",
    },
  };
  const config = colorConfig[color] || colorConfig.blue;

  return (
    <div>
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-sm font-medium text-gray-700">{label}</span>
        <span className={`text-sm font-semibold ${config.text}`}>
          {value}점
        </span>
      </div>
      <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
        <div
          className={`h-full ${config.bar} rounded-full`}
          style={{ width: `${value}%` }}
        />
      </div>
    </div>
  );
};

// 상세 메트릭 섹션
const DetailedMetrics = ({ technicalDetails }) => {
  const metrics = [
    {
      icon: Clock,
      label: "마지막 커밋",
      value: technicalDetails?.lastCommit || "알 수 없음",
      color: "blue",
    },
    {
      icon: Activity,
      label: "최근 30일 커밋",
      value: `${technicalDetails?.totalCommits30d || 0}`,
      subtext: "commits",
      color: "green",
    },
    {
      icon: MessageSquare,
      label: "이슈 해결률",
      value: technicalDetails?.issueCloseRatePct || "N/A",
      color: "purple",
    },
    {
      icon: GitPullRequest,
      label: "PR 병합 속도",
      value: technicalDetails?.medianPRMergeDaysText || "N/A",
      subtext: "중앙값",
      color: "cyan",
    },
    {
      icon: AlertCircle,
      label: "열린 이슈",
      value: `${technicalDetails?.openIssues || 0}`,
      subtext: "issues",
      color: "orange",
    },
    {
      icon: GitPullRequest,
      label: "열린 PR",
      value: `${technicalDetails?.openPRs || 0}`,
      subtext: "pull requests",
      color: "pink",
    },
  ];

  const colorMap = {
    blue: "border-blue-200 text-blue-600",
    green: "border-green-200 text-green-600",
    purple: "border-purple-200 text-purple-600",
    cyan: "border-cyan-200 text-cyan-600",
    orange: "border-orange-200 text-orange-600",
    pink: "border-pink-200 text-pink-600",
  };

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
      {metrics.map((metric, idx) => {
        const colors = colorMap[metric.color];
        return (
          <div
            key={idx}
            className={`bg-gray-50 rounded-lg p-3 border ${colors.split(" ")[0]
              } text-center`}
          >
            <metric.icon
              className={`w-4 h-4 mx-auto mb-1.5 ${colors.split(" ")[1]}`}
            />
            <div className="text-lg font-semibold text-gray-900">
              {metric.value}
            </div>
            <div className="text-xs text-gray-500 mt-0.5">{metric.label}</div>
            {metric.subtext && (
              <div className="text-xs text-gray-400">{metric.subtext}</div>
            )}
          </div>
        );
      })}
    </div>
  );
};

// 프로젝트 요약
const ProjectSummary = ({ summary, interpretation, levelDescription }) => (
  <div className="space-y-4">
    {interpretation && (
      <div className="bg-indigo-50 border border-indigo-200 rounded-xl p-4">
        <p className="text-sm text-indigo-800 font-medium">{interpretation}</p>
      </div>
    )}
    {levelDescription && (
      <div className="bg-gray-50 border border-gray-200 rounded-xl p-4">
        <p className="text-sm text-gray-700">{levelDescription}</p>
      </div>
    )}
    <div className="prose prose-sm max-w-none text-gray-700">
      <ReactMarkdown
        components={{
          h1: ({ children }) => (
            <h3 className="text-lg font-bold text-gray-900 mb-3">{children}</h3>
          ),
          h2: ({ children }) => (
            <h4 className="text-base font-bold text-gray-900 mb-2 mt-4">
              {children}
            </h4>
          ),
          p: ({ children }) => (
            <p className="text-sm text-gray-700 mb-3 leading-relaxed">
              {children}
            </p>
          ),
          ul: ({ children }) => (
            <ul className="list-disc pl-5 mb-3 space-y-1">{children}</ul>
          ),
          li: ({ children }) => (
            <li className="text-sm text-gray-700">{children}</li>
          ),
          strong: ({ children }) => (
            <strong className="font-bold text-gray-900">{children}</strong>
          ),
        }}
      >
        {summary}
      </ReactMarkdown>
    </div>
  </div>
);

// 빈 보안 섹션 (취약점 없음)
const EmptySecuritySection = () => (
  <div className="text-center py-8">
    <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
      <Shield className="w-8 h-8 text-green-600" />
    </div>
    <h3 className="text-lg font-semibold text-gray-900 mb-2">
      보안 취약점이 발견되지 않았습니다
    </h3>
    <p className="text-sm text-gray-500 max-w-md mx-auto">
      의존성 패키지에서 알려진 보안 취약점(CVE)이 감지되지 않았습니다.
      프로젝트가 안전한 상태입니다.
    </p>
    <div className="mt-4 inline-flex items-center gap-2 px-4 py-2 bg-green-50 text-green-700 rounded-full text-sm font-medium">
      <CheckCircle className="w-4 h-4" />
      안전함
    </div>
  </div>
);

// 보안 섹션
const SecuritySection = ({ security }) => {
  const gradeConfig = {
    A: { color: "text-green-600", bg: "bg-green-100" },
    B: { color: "text-blue-600", bg: "bg-blue-100" },
    C: { color: "text-yellow-600", bg: "bg-yellow-100" },
    D: { color: "text-orange-600", bg: "bg-orange-100" },
    F: { color: "text-red-600", bg: "bg-red-100" },
  };
  const grade = gradeConfig[security.grade] || gradeConfig.C;

  // 취약점 상세 정보
  const vulnerabilities = security.vulnerabilities || [];

  return (
    <div className="space-y-4">
      {/* 점수 카드 */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-gray-50 rounded-xl p-4 text-center border border-gray-200">
          <div className="text-3xl font-black text-gray-900">
            {security.score ?? "N/A"}
          </div>
          <div className="text-xs text-gray-500 mt-1">Security Score</div>
        </div>
        <div className={`rounded-xl p-4 text-center ${grade.bg}`}>
          <div className={`text-3xl font-black ${grade.color}`}>
            {security.grade || "N/A"}
          </div>
          <div className="text-xs text-gray-600 mt-1">Grade</div>
        </div>
        <div className="bg-red-50 rounded-xl p-4 text-center border border-red-200">
          <div className="text-3xl font-black text-red-600">
            {security.vulnerability_count || 0}
          </div>
          <div className="text-xs text-gray-600 mt-1">취약점</div>
        </div>
      </div>

      {/* 심각도별 카운트 */}
      <div className="grid grid-cols-4 gap-3">
        {[
          {
            label: "Critical",
            count: security.critical || 0,
            bgColor: "bg-red-50",
            borderColor: "border-red-200",
            textColor: "text-red-600",
          },
          {
            label: "High",
            count: security.high || 0,
            bgColor: "bg-orange-50",
            borderColor: "border-orange-200",
            textColor: "text-orange-600",
          },
          {
            label: "Medium",
            count: security.medium || 0,
            bgColor: "bg-yellow-50",
            borderColor: "border-yellow-200",
            textColor: "text-yellow-600",
          },
          {
            label: "Low",
            count: security.low || 0,
            bgColor: "bg-blue-50",
            borderColor: "border-blue-200",
            textColor: "text-blue-600",
          },
        ].map((item) => (
          <div
            key={item.label}
            className={`text-center p-3 ${item.bgColor} rounded-lg border ${item.borderColor}`}
          >
            <div className={`text-2xl font-bold ${item.textColor}`}>
              {item.count}
            </div>
            <div className={`text-xs ${item.textColor} font-medium`}>
              {item.label}
            </div>
          </div>
        ))}
      </div>

      {/* 요약 */}
      {security.summary && (
        <div className="text-sm text-gray-600 p-3 bg-blue-50 rounded-lg border border-blue-100">
          {security.summary}
        </div>
      )}

      {/* CVE 상세 정보 */}
      {vulnerabilities.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-sm font-semibold text-gray-700">발견된 취약점</h4>
          <div className="space-y-2 max-h-60 overflow-y-auto">
            {vulnerabilities.map((vuln, idx) => (
              <div
                key={idx}
                className="p-3 bg-gray-50 rounded-lg border border-gray-200"
              >
                <div className="flex items-center justify-between">
                  <span className="font-medium text-gray-900">
                    {vuln.cve_id || vuln.package || `취약점 #${idx + 1}`}
                  </span>
                  <span
                    className={`px-2 py-0.5 text-xs font-medium rounded ${vuln.severity === "critical"
                      ? "bg-red-100 text-red-700"
                      : vuln.severity === "high"
                        ? "bg-orange-100 text-orange-700"
                        : vuln.severity === "medium"
                          ? "bg-yellow-100 text-yellow-700"
                          : "bg-blue-100 text-blue-700"
                      }`}
                  >
                    {vuln.severity || "unknown"}
                  </span>
                </div>
                {vuln.package && (
                  <div className="text-xs text-gray-500 mt-1">
                    패키지: {vuln.package}
                  </div>
                )}
                {vuln.description && (
                  <div className="text-xs text-gray-600 mt-1">
                    {vuln.description}
                  </div>
                )}
                {vuln.cve_id && (
                  <a
                    href={`https://nvd.nist.gov/vuln/detail/${vuln.cve_id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-indigo-600 hover:underline mt-1 inline-block"
                  >
                    NVD에서 보기
                  </a>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 취약점 없음 메시지 */}
      {security.vulnerability_count === 0 && (
        <div className="text-center py-4 text-green-600 bg-green-50 rounded-lg">
          취약점이 발견되지 않았습니다!
        </div>
      )}
    </div>
  );
};

// 위험 요소 아이템
const RiskItem = ({ risk }) => {
  const severityConfig = {
    high: {
      container: "border-red-500 bg-red-50",
      badge: "bg-red-500 text-white",
    },
    medium: {
      container: "border-yellow-500 bg-yellow-50",
      badge: "bg-yellow-500 text-white",
    },
    low: {
      container: "border-blue-500 bg-blue-50",
      badge: "bg-blue-500 text-white",
    },
  };
  const config = severityConfig[risk.severity] || severityConfig.medium;

  return (
    <div className={`rounded-xl p-4 border-l-4 ${config.container}`}>
      <div className="flex items-start justify-between mb-2">
        <span
          className={`text-xs px-3 py-1 rounded-full font-bold ${config.badge}`}
        >
          {risk.severity?.toUpperCase() || "MEDIUM"}
        </span>
        <span className="text-xs text-gray-500">{risk.type}</span>
      </div>
      <p className="text-sm font-medium text-gray-900">{risk.description}</p>
    </div>
  );
};

// 가이드 버튼 컴포넌트
const InfoGuideButton = ({ guideKey, onOpenGuide }) => {
  if (!SECTION_GUIDES[guideKey]) return null;

  return (
    <button
      onClick={(e) => {
        e.stopPropagation();
        onOpenGuide(guideKey);
      }}
      className="p-1 hover:bg-gray-200 dark:hover:bg-gray-600 rounded-full transition-colors"
      title="이 점수가 어떻게 계산되나요?"
    >
      <HelpCircle className="w-4 h-4 text-gray-400 hover:text-blue-500" />
    </button>
  );
};

// 접을 수 있는 카드
const CollapsibleCard = ({
  title,
  subtitle,
  icon,
  isExpanded,
  onToggle,
  children,
  guideKey,
  onOpenGuide,
}) => (
  <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
    <div className="w-full px-5 py-4 border-b border-gray-100 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors flex items-center justify-between">
      <div className="flex items-center gap-2">
        {icon}
        <div className="text-left">
          <div className="flex items-center gap-1">
            <h3 className="text-base font-semibold text-gray-900 dark:text-white">
              {title}
            </h3>
            {guideKey && onOpenGuide && (
              <InfoGuideButton guideKey={guideKey} onOpenGuide={onOpenGuide} />
            )}
          </div>
          {subtitle && (
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
              {subtitle}
            </p>
          )}
        </div>
      </div>
      <button
        onClick={onToggle}
        className="p-1 hover:bg-gray-200 dark:hover:bg-gray-600 rounded transition-colors"
        aria-label={isExpanded ? "섹션 접기" : "섹션 펼치기"}
      >
        {isExpanded ? (
          <ChevronUp className="w-5 h-5 text-gray-400" />
        ) : (
          <ChevronDown className="w-5 h-5 text-gray-400" />
        )}
      </button>
    </div>
    {isExpanded && <div className="p-5">{children}</div>}
  </div>
);

// === 새로운 미니멀 스타일 섹션들 ===

// 추천 이슈 섹션 (미니멀 스타일)
const RecommendedIssuesSection = ({ issues }) => {
  if (!issues || issues.length === 0) {
    return (
      <div className="text-center text-gray-500 py-8">
        <Lightbulb className="w-12 h-12 mx-auto mb-3 text-gray-300" />
        <p>추천 이슈가 없습니다.</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {issues.map((issue, idx) => (
        <a
          key={issue.number || idx}
          href={issue.url}
          target="_blank"
          rel="noopener noreferrer"
          className="block p-4 bg-amber-50/50 hover:bg-amber-100/50 rounded-xl border border-amber-200/60 transition-colors group"
        >
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1.5">
                <span className="text-xs font-semibold text-amber-600 bg-amber-100 px-2 py-0.5 rounded">
                  #{issue.number}
                </span>
                {issue.labels?.slice(0, 2).map((label) => (
                  <span
                    key={label}
                    className="text-xs text-gray-500 bg-gray-100 px-2 py-0.5 rounded"
                  >
                    {label}
                  </span>
                ))}
              </div>
              <h4 className="text-sm font-semibold text-gray-900 group-hover:text-amber-700 transition-colors">
                {issue.title}
              </h4>
              {issue.body && (
                <p className="text-xs text-gray-500 mt-1.5 line-clamp-2">
                  {issue.body.substring(0, 120)}
                  {issue.body.length > 120 ? "..." : ""}
                </p>
              )}
            </div>
            <ExternalLink className="w-4 h-4 text-amber-400 group-hover:text-amber-600 flex-shrink-0 mt-1 transition-colors" />
          </div>
        </a>
      ))}
    </div>
  );
};

// 추천 기여 작업 섹션 (미니멀 스타일)
const ContributionsSection = ({ recommendations }) => {
  if (!recommendations || recommendations.length === 0) {
    return (
      <div className="text-center text-gray-500 py-8">
        <Target className="w-12 h-12 mx-auto mb-3 text-gray-300" />
        <p>추천 작업이 없습니다.</p>
      </div>
    );
  }

  const getDifficultyStyle = (difficulty) => {
    switch (difficulty) {
      case "easy":
        return "bg-green-100 text-green-700";
      case "hard":
        return "bg-red-100 text-red-700";
      default:
        return "bg-yellow-100 text-yellow-700";
    }
  };

  const getDifficultyLabel = (difficulty) => {
    switch (difficulty) {
      case "easy":
        return "쉬움";
      case "hard":
        return "어려움";
      default:
        return "보통";
    }
  };

  return (
    <div className="space-y-3">
      {recommendations.map((rec, idx) => (
        <div
          key={rec.id || idx}
          className="p-4 bg-green-50/50 rounded-xl border border-green-200/60"
        >
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1.5">
                <span
                  className={`text-xs font-semibold px-2 py-0.5 rounded ${getDifficultyStyle(
                    rec.difficulty
                  )}`}
                >
                  {getDifficultyLabel(rec.difficulty)}
                </span>
              </div>
              <h4 className="text-sm font-semibold text-gray-900">
                {rec.title}
              </h4>
              <p className="text-xs text-gray-500 mt-1">{rec.description}</p>
              {rec.tags?.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mt-2">
                  {rec.tags.slice(0, 3).map((tag) => (
                    <span
                      key={tag}
                      className="text-xs text-gray-500 bg-white px-2 py-0.5 rounded border border-gray-200"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              )}
            </div>
            {rec.url && (
              <a
                href={rec.url}
                target="_blank"
                rel="noopener noreferrer"
                className="p-2 hover:bg-green-100 rounded-lg transition-colors"
              >
                <ExternalLink className="w-4 h-4 text-green-500" />
              </a>
            )}
          </div>
        </div>
      ))}
    </div>
  );
};

// 유사 프로젝트 섹션 (미니멀 스타일)
const SimilarProjectsSection = ({ projects }) => {
  if (!projects || projects.length === 0) {
    return (
      <div className="text-center py-10">
        <FolderGit2 className="w-14 h-14 mx-auto mb-4 text-violet-200" />
        <h4 className="text-base font-semibold text-gray-700 mb-2">
          유사 프로젝트 분석 예정
        </h4>
        <p className="text-sm text-gray-400 max-w-sm mx-auto mb-4">
          기술 스택과 구조가 비슷한 프로젝트를 추천하여 학습과 참고에 도움을
          드릴 예정입니다.
        </p>
        <p className="text-xs text-gray-400 italic">
          * 온보딩 점수를 기반으로 추천됩니다.
        </p>
      </div>
    );
  }

  return (
    <div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {projects.slice(0, 6).map((project, idx) => (
          <a
            key={project.repo || idx}
            href={project.url}
            target="_blank"
            rel="noopener noreferrer"
            className="block p-4 bg-violet-50/50 hover:bg-violet-100/50 rounded-xl border border-violet-200/60 transition-colors group min-h-[140px]"
          >
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 bg-violet-100 rounded-lg flex items-center justify-center flex-shrink-0">
                <GitBranch className="w-5 h-5 text-violet-500" />
              </div>
              <div className="flex-1 min-w-0">
                <h4 className="text-sm font-semibold text-gray-900 group-hover:text-violet-700 truncate transition-colors">
                  {project.name || project.repo?.split("/")[1] || "Unknown"}
                </h4>
                <p className="text-xs text-gray-400 truncate">
                  {project.owner || project.repo?.split("/")[0]}
                </p>
                <div className="flex items-center gap-3 mt-2">
                  {project.stars !== undefined && (
                    <span className="flex items-center gap-1 text-xs text-gray-500">
                      <Star className="w-3 h-3 text-yellow-500" />
                      {formatNumber(project.stars)}
                    </span>
                  )}
                  {project.forks !== undefined && (
                    <span className="flex items-center gap-1 text-xs text-gray-500">
                      <GitFork className="w-3 h-3 text-blue-400" />
                      {formatNumber(project.forks)}
                    </span>
                  )}
                  {project.language && (
                    <span className="flex items-center gap-1 text-xs text-gray-500">
                      <Code2 className="w-3 h-3 text-green-500" />
                      {project.language}
                    </span>
                  )}
                </div>
                {project.reason && (
                  <p className="text-xs text-violet-600 mt-2 max-h-16 overflow-y-auto bg-violet-100/50 px-2 py-1 rounded">
                    {project.reason}
                  </p>
                )}
                {/* 온보딩 점수 표시 (유사도 대신) */}
                {project.onboarding_score !== undefined && (
                  <div className="flex items-center gap-2 mt-2">
                    <span className="text-xs text-violet-500 font-medium">
                      온보딩 점수: {project.onboarding_score}점
                    </span>
                  </div>
                )}
              </div>
            </div>
          </a>
        ))}
      </div>
      <p className="text-xs text-gray-400 text-center mt-4 italic">
        * 온보딩 점수를 기반으로 추천됩니다.
      </p>
    </div>
  );
};

// Agentic Flow 정보 섹션
const AgenticFlowSection = ({ warnings, flowAdjustments }) => {
  return (
    <div className="space-y-4">
      {warnings?.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
          <h4 className="flex items-center gap-2 text-sm font-bold text-amber-800 mb-3">
            <AlertTriangle className="w-4 h-4" />
            분석 중 발생한 경고
          </h4>
          <ul className="space-y-2">
            {warnings.map((warning, idx) => (
              <li
                key={idx}
                className="text-xs text-amber-700 flex items-start gap-2"
              >
                <span className="mt-1">•</span>
                <span>{warning}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {flowAdjustments?.length > 0 && (
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-4">
          <h4 className="flex items-center gap-2 text-sm font-bold text-blue-800 mb-3">
            <Info className="w-4 h-4" />
            분석 플로우 조정
          </h4>
          <ul className="space-y-2">
            {flowAdjustments.map((adjustment, idx) => (
              <li
                key={idx}
                className="text-xs text-blue-700 flex items-start gap-2"
              >
                <span className="mt-1">→</span>
                <span>{adjustment}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {(!warnings || warnings.length === 0) &&
        (!flowAdjustments || flowAdjustments.length === 0) && (
          <div className="text-center text-gray-500 py-4">
            <Info className="w-8 h-8 mx-auto mb-2 text-gray-300" />
            <p className="text-sm">분석 과정에서 특별한 이슈가 없었습니다.</p>
          </div>
        )}
    </div>
  );
};

// === 유틸리티 함수 ===

function getStatusConfig(score) {
  if (score >= 80)
    return {
      label: "Excellent",
      barColor: "bg-green-500",
      ringColor: "text-green-500",
      bgGlow: "bg-green-500",
      textColor: "text-green-700 dark:text-green-400",
      bgColor: "bg-green-50 dark:bg-green-900/30",
      borderColor: "border-green-200 dark:border-green-800",
    };
  if (score >= 60)
    return {
      label: "Good",
      barColor: "bg-yellow-500",
      ringColor: "text-yellow-500",
      bgGlow: "bg-yellow-500",
      textColor: "text-yellow-700 dark:text-yellow-400",
      bgColor: "bg-yellow-50 dark:bg-yellow-900/30",
      borderColor: "border-yellow-200 dark:border-yellow-800",
    };
  return {
    label: "Needs Attention",
    barColor: "bg-red-500",
    ringColor: "text-red-500",
    bgGlow: "bg-red-500",
    textColor: "text-red-700 dark:text-red-400",
    bgColor: "bg-red-50 dark:bg-red-900/30",
    borderColor: "border-red-200 dark:border-red-800",
  };
}

export default AnalysisReportSection;
