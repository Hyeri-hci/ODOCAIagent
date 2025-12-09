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
  Search,
  ArrowRight,
  Info,
  BookOpen,
  Shield,
} from "lucide-react";
import { formatNumber } from "../../utils/formatNumber";
import OnboardingPlanSection from "./OnboardingPlanSection";

const formatAdjustment = (adjustment) => {
  const adjustmentMap = {
    recommend_deep_analysis: "AI가 이 프로젝트에 대해 심층 분석을 권장합니다",
    skip_optional_checks: "빠른 결과를 위해 일부 선택적 검사를 생략했습니다",
    prioritize_documentation: "문서화 상태가 중요하여 우선 분석했습니다",
    expand_activity_window: "더 정확한 분석을 위해 활동성 기간을 확장했습니다",
    include_beginner_tips: "초보자를 위한 추가 팁이 포함되었습니다",
    simplify_recommendations: "이해하기 쉽도록 추천 항목을 단순화했습니다",
    add_health_warning: "이 프로젝트의 건강 상태에 주의가 필요합니다",
    beginner_friendly_plan: "초보자 친화적인 온보딩 플랜이 적용되었습니다",
  };
  return adjustmentMap[adjustment] || adjustment;
};

const AnalysisReportSection = ({ analysisResult, isLoading = false }) => {
  const [expandedSections, setExpandedSections] = useState({
    onboarding: true,  // 온보딩 가이드
    overview: true,
    projectSummary: true,
    security: true,  // 보안 분석
    contributions: true,
    relatedProjects: false,
  });

  const toggleSection = (section) => {
    setExpandedSections((prev) => ({
      ...prev,
      [section]: !prev[section],
    }));
  };

  const getStatusConfig = (score) => {
    if (score >= 80)
      return {
        label: "Excellent",
        color: "from-green-400 to-emerald-500",
        textColor: "text-green-700",
        bgColor: "bg-green-50",
        borderColor: "border-green-200",
      };
    if (score >= 60)
      return {
        label: "Good",
        color: "from-yellow-400 to-orange-500",
        textColor: "text-yellow-700",
        bgColor: "bg-yellow-50",
        borderColor: "border-yellow-200",
      };
    return {
      label: "Needs Attention",
      color: "from-red-400 to-rose-500",
      textColor: "text-red-700",
      bgColor: "bg-red-50",
      borderColor: "border-red-200",
    };
  };

  // 안전한 데이터 접근
  if (!analysisResult || !analysisResult.summary) {
    return (
      <div className="text-center text-gray-500 py-8">
        분석 결과를 불러오는 중...
      </div>
    );
  }

  const statusConfig = getStatusConfig(analysisResult.summary.score);

  return (
    <div className="relative space-y-4">
      {/* 로딩 오버레이 */}
      {isLoading && (
        <div className="absolute inset-0 bg-white/80 backdrop-blur-sm z-50 rounded-3xl flex items-center justify-center">
          <div className="text-center">
            <div className="relative w-20 h-20 mx-auto mb-4">
              <div className="absolute inset-0 border-4 border-blue-200 rounded-full"></div>
              <div className="absolute inset-0 border-4 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
            </div>
            <p className="text-lg font-semibold text-gray-900 mb-1">
              분석 중입니다
            </p>
            <p className="text-sm text-gray-600">
              새로운 프로젝트를 분석하고 있습니다...
            </p>
          </div>
        </div>
      )}

      {/* AI 분석 경고 배너 */}
      {analysisResult.warnings && analysisResult.warnings.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-2xl p-5 shadow-sm">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 bg-amber-100 rounded-xl flex items-center justify-center flex-shrink-0">
              <AlertCircle className="w-5 h-5 text-amber-600" />
            </div>
            <div className="flex-1">
              <h4 className="font-bold text-amber-800 mb-2">AI 분석 주의사항</h4>
              <ul className="space-y-1">
                {analysisResult.warnings.map((warning, idx) => (
                  <li key={idx} className="text-sm text-amber-700 flex items-start gap-2">
                    <span className="text-amber-400 mt-1">•</span>
                    <span>{warning}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* AI 분석 조정 정보 */}
      {analysisResult.flowAdjustments && analysisResult.flowAdjustments.length > 0 && (
        <div className="bg-blue-50 border border-blue-200 rounded-2xl p-5 shadow-sm">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 bg-blue-100 rounded-xl flex items-center justify-center flex-shrink-0">
              <Info className="w-5 h-5 text-blue-600" />
            </div>
            <div className="flex-1">
              <h4 className="font-bold text-blue-800 mb-2">AI 분석 조정</h4>
              <ul className="space-y-1">
                {analysisResult.flowAdjustments.map((adjustment, idx) => (
                  <li key={idx} className="text-sm text-blue-700 flex items-start gap-2">
                    <span className="text-blue-400 mt-1">•</span>
                    <span>{formatAdjustment(adjustment)}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* 온보딩 가이드 (onboardingPlan이 있을 때 표시) */}
      {analysisResult.onboardingPlan && analysisResult.onboardingPlan.length > 0 && (
        <OnboardingPlanSection
          plan={analysisResult.onboardingPlan}
          userProfile={{ repositoryUrl: analysisResult.repositoryUrl }}
        />
      )}

      {/* 종합 점수 및 Repository Statistics (항상 표시) */}
      <CollapsibleCard
        title="분석 결과 리포트"
        isExpanded={expandedSections.overview}
        onToggle={() => toggleSection("overview")}
      >
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          {/* 왼쪽: 점수 카드 */}
          <div className="lg:col-span-4">
            <div className="bg-indigo-600 rounded-2xl p-8 h-full shadow-xl">
              <div className="flex items-center gap-3 mb-6">
                <div className="w-12 h-12 bg-white/20 rounded-xl flex items-center justify-center">
                  <TrendingUp className="w-6 h-6 text-white" />
                </div>
                <div>
                  <h3 className="text-white font-bold text-lg">
                    프로젝트 분석
                  </h3>
                  <p className="text-indigo-200 text-sm">Health Score</p>
                </div>
              </div>

              <div className="bg-white rounded-2xl p-6 text-center mb-6">
                <div className="text-7xl font-black text-indigo-600 mb-3">
                  {analysisResult.summary.score}
                </div>
                <div className="text-gray-600 text-sm font-semibold mb-4">
                  종합 점수
                </div>
                <div className="h-3 bg-gray-100 rounded-full overflow-hidden">
                  <div
                    className={`h-full bg-gradient-to-r ${statusConfig.color} rounded-full transition-all duration-1000`}
                    style={{ width: `${analysisResult.summary.score}%` }}
                  ></div>
                </div>
              </div>

              <div
                className={`${statusConfig.bgColor} ${statusConfig.borderColor} border-2 px-4 py-3 rounded-xl flex items-center gap-2 justify-center`}
              >
                <CheckCircle className={`w-5 h-5 ${statusConfig.textColor}`} />
                <span className={`${statusConfig.textColor} font-bold`}>
                  {statusConfig.label}
                </span>
              </div>
            </div>
          </div>

          {/* 오른쪽: Repository Statistics */}
          <div className="lg:col-span-8">
            <h2 className="text-2xl font-black text-gray-900 mb-6">
              Repository Statistics
            </h2>

            {/* Stats Grid */}
            <div className="grid grid-cols-3 gap-4 mb-8">
              <div className="bg-gradient-to-br from-yellow-50 to-orange-50 rounded-2xl p-5 border border-yellow-200">
                <Star className="w-6 h-6 text-yellow-500 mb-2" />
                <div className="text-3xl font-bold text-gray-900 mb-1">
                  {formatNumber(analysisResult.technicalDetails?.stars || 0)}
                </div>
                <div className="text-sm text-gray-600">GitHub Stars</div>
              </div>
              <div className="bg-gradient-to-br from-cyan-50 to-blue-50 rounded-2xl p-5 border border-cyan-200">
                <GitFork className="w-6 h-6 text-cyan-600 mb-2" />
                <div className="text-3xl font-bold text-gray-900 mb-1">
                  {formatNumber(analysisResult.technicalDetails?.forks || 0)}
                </div>
                <div className="text-sm text-gray-600">Forks</div>
              </div>
              <div className="bg-gradient-to-br from-purple-50 to-pink-50 rounded-2xl p-5 border border-purple-200">
                <Users className="w-6 h-6 text-purple-600 mb-2" />
                <div className="text-3xl font-bold text-gray-900 mb-1">
                  {formatNumber(analysisResult.technicalDetails.contributors)}
                </div>
                <div className="text-sm text-gray-600">Contributors</div>
              </div>
            </div>

            {/* Metric Bars */}
            <div className="space-y-5">
              <MetricBar
                icon={FileText}
                label="문서 품질"
                value={
                  analysisResult.technicalDetails?.documentationQuality ||
                  analysisResult.rawAnalysis?.documentation_quality ||
                  0
                }
                color="green"
              />
              <MetricBar
                icon={Activity}
                label="활동성/유지보수"
                value={
                  analysisResult.technicalDetails?.activityMaintainability ||
                  analysisResult.rawAnalysis?.activity_maintainability ||
                  0
                }
                color="blue"
              />
              <MetricBar
                icon={Users}
                label="온보딩 용이성"
                value={analysisResult.rawAnalysis?.onboarding_score || 0}
                color="purple"
              />
            </div>
          </div>
        </div>
      </CollapsibleCard>

      {/* 프로젝트 요약 */}
      <CollapsibleCard
        title="프로젝트 요약"
        icon={<FileText className="w-5 h-5 text-indigo-600" />}
        isExpanded={expandedSections.projectSummary}
        onToggle={() => toggleSection("projectSummary")}
      >
        <div className="prose prose-sm max-w-none text-gray-700">
          <ReactMarkdown
            components={{
              h1: ({ children }) => <h3 className="text-lg font-bold text-gray-900 mb-3">{children}</h3>,
              h2: ({ children }) => <h4 className="text-base font-bold text-gray-900 mb-2 mt-4">{children}</h4>,
              h3: ({ children }) => <h5 className="text-sm font-bold text-gray-900 mb-2 mt-3">{children}</h5>,
              p: ({ children }) => <p className="text-sm text-gray-700 mb-3 leading-relaxed">{children}</p>,
              ul: ({ children }) => <ul className="list-disc pl-5 mb-3 space-y-1">{children}</ul>,
              ol: ({ children }) => <ol className="list-decimal pl-5 mb-3 space-y-1">{children}</ol>,
              li: ({ children }) => <li className="text-sm text-gray-700">{children}</li>,
              strong: ({ children }) => <strong className="font-bold text-gray-900">{children}</strong>,
            }}
          >
            {analysisResult.projectSummary ||
              `이 저장소는 ${analysisResult.technicalDetails.framework || "알 수 없는"} 프레임워크를 사용하며, ${analysisResult.technicalDetails.contributors || 0}명의 기여자가 활동 중입니다. 전반적으로 ${statusConfig.label === "Excellent" ? "훌륭한" : statusConfig.label === "Good" ? "양호한" : "개선이 필요한"} 상태의 프로젝트입니다.`}
          </ReactMarkdown>
        </div>
      </CollapsibleCard>

      {/* 보안 분석 */}
      <CollapsibleCard
        title="보안 분석"
        icon={<Shield className="w-5 h-5 text-red-500" />}
        subtitle={
          analysisResult.security
            ? `취약점 ${analysisResult.security.vulnerability_count || 0}개 발견`
            : "분석 대기 중"
        }
        isExpanded={expandedSections.security}
        onToggle={() => toggleSection("security")}
        headerBg="bg-gradient-to-r from-red-50 to-orange-50"
      >
        {analysisResult.security ? (
          <SecurityAnalysisSection security={analysisResult.security} />
        ) : (
          <p className="text-center text-gray-500 py-4">
            보안 분석이 수행되지 않았습니다. "보안 분석" 요청을 보내주세요.
          </p>
        )}
      </CollapsibleCard>

      {/* 추천 기여 작업 */}
      <CollapsibleCard
        title="추천 기여 작업"
        icon={<CheckCircle className="w-5 h-5 text-green-500" />}
        subtitle={`${analysisResult.recommendations.length}개 작업 추천`}
        isExpanded={expandedSections.contributions}
        onToggle={() => toggleSection("contributions")}
        headerBg="bg-gradient-to-r from-green-50 to-emerald-50"
      >
        <div className="space-y-3">
          {analysisResult.recommendations.map((rec) => (
            <ContributionItem key={rec.id} recommendation={rec} />
          ))}
        </div>
      </CollapsibleCard>

      {/* 관련 프로젝트 */}
      {analysisResult.relatedProjects &&
        analysisResult.relatedProjects.length > 0 && (
          <CollapsibleCard
            title="관련 프로젝트"
            icon={<Search className="w-5 h-5 text-blue-600" />}
            subtitle="관심 있을 만한 유사 저장소를 확인해보세요"
            isExpanded={expandedSections.relatedProjects}
            onToggle={() => toggleSection("relatedProjects")}
          >
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {analysisResult.relatedProjects.map((project, index) => (
                <RelatedProjectCard key={index} project={project} />
              ))}
            </div>
          </CollapsibleCard>
        )}
    </div>
  );
};

// 접을 수 있는 카드 컴포넌트
const CollapsibleCard = ({
  title,
  subtitle,
  icon,
  isExpanded,
  onToggle,
  children,
  headerBg = "bg-white/60",
}) => {
  return (
    <div className="bg-white/40 backdrop-blur-sm rounded-2xl shadow-lg overflow-hidden border border-white/60">
      <button
        onClick={onToggle}
        className={`w-full ${headerBg} px-6 py-4 border-b border-gray-100 hover:bg-white/80 transition-all flex items-center justify-between`}
      >
        <div className="flex items-center gap-2">
          {icon}
          <div className="text-left">
            <h3 className="text-xl font-black text-gray-900">{title}</h3>
            {subtitle && (
              <p className="text-sm text-gray-600 mt-1">{subtitle}</p>
            )}
          </div>
        </div>
        {isExpanded ? (
          <ChevronUp className="w-6 h-6 text-gray-600" />
        ) : (
          <ChevronDown className="w-6 h-6 text-gray-600" />
        )}
      </button>

      {isExpanded && <div className="p-6">{children}</div>}
    </div>
  );
};

// 메트릭 바 컴포넌트
const MetricBar = ({ icon: Icon, label, value, color }) => {
  const colorConfig = {
    green: {
      text: "text-green-600",
      gradient: "from-green-400 to-emerald-500",
    },
    blue: {
      text: "text-blue-600",
      gradient: "from-blue-400 to-indigo-500",
    },
    purple: {
      text: "text-purple-600",
      gradient: "from-purple-400 to-pink-500",
    },
  };

  const config = colorConfig[color] || colorConfig.blue;

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <Icon className={`w-5 h-5 ${config.text}`} />
          <span className="font-bold text-gray-900">{label}</span>
        </div>
        <span className={`text-lg font-bold ${config.text}`}>{value}점</span>
      </div>
      <div className="h-3 bg-gray-100 rounded-full overflow-hidden">
        <div
          className={`h-full bg-gradient-to-r ${config.gradient} rounded-full`}
          style={{ width: `${value}%` }}
        ></div>
      </div>
    </div>
  );
};

// 보안 분석 섹션 컴포넌트
const SecurityAnalysisSection = ({ security }) => {
  const getGradeConfig = (grade) => {
    const configs = {
      A: { color: "text-green-600", bg: "bg-green-100", label: "우수" },
      B: { color: "text-blue-600", bg: "bg-blue-100", label: "양호" },
      C: { color: "text-yellow-600", bg: "bg-yellow-100", label: "보통" },
      D: { color: "text-orange-600", bg: "bg-orange-100", label: "주의" },
      F: { color: "text-red-600", bg: "bg-red-100", label: "위험" },
    };
    return configs[grade] || configs.C;
  };

  const getRiskLevelConfig = (level) => {
    const configs = {
      Low: { color: "text-green-600", bg: "bg-green-50", border: "border-green-200" },
      Medium: { color: "text-yellow-600", bg: "bg-yellow-50", border: "border-yellow-200" },
      High: { color: "text-orange-600", bg: "bg-orange-50", border: "border-orange-200" },
      Critical: { color: "text-red-600", bg: "bg-red-50", border: "border-red-200" },
    };
    return configs[level] || configs.Medium;
  };

  const gradeConfig = getGradeConfig(security.grade);
  const riskConfig = getRiskLevelConfig(security.risk_level);

  return (
    <div className="space-y-4">
      {/* 보안 점수 및 등급 */}
      <div className="grid grid-cols-3 gap-4">
        {/* Security Score */}
        <div className="bg-gradient-to-br from-slate-50 to-gray-100 rounded-xl p-4 text-center border border-gray-200">
          <div className="text-3xl font-black text-gray-900">
            {security.score ?? "N/A"}
          </div>
          <div className="text-xs text-gray-500 mt-1">Security Score</div>
        </div>

        {/* Grade */}
        <div className={`rounded-xl p-4 text-center ${gradeConfig.bg}`}>
          <div className={`text-3xl font-black ${gradeConfig.color}`}>
            {security.grade || "N/A"}
          </div>
          <div className="text-xs text-gray-600 mt-1">{gradeConfig.label}</div>
        </div>

        {/* Risk Level */}
        <div className={`rounded-xl p-4 text-center ${riskConfig.bg} border ${riskConfig.border}`}>
          <div className={`text-xl font-bold ${riskConfig.color}`}>
            {security.risk_level || "Unknown"}
          </div>
          <div className="text-xs text-gray-500 mt-1">Risk Level</div>
        </div>
      </div>

      {/* 취약점 요약 */}
      <div className="bg-white rounded-xl p-4 border border-gray-200">
        <h4 className="font-bold text-gray-900 mb-3">취약점 요약</h4>
        <div className="grid grid-cols-4 gap-3">
          <div className="text-center p-3 bg-red-50 rounded-lg border border-red-200">
            <div className="text-2xl font-bold text-red-600">{security.critical || 0}</div>
            <div className="text-xs text-red-700 font-medium">Critical</div>
          </div>
          <div className="text-center p-3 bg-orange-50 rounded-lg border border-orange-200">
            <div className="text-2xl font-bold text-orange-600">{security.high || 0}</div>
            <div className="text-xs text-orange-700 font-medium">High</div>
          </div>
          <div className="text-center p-3 bg-yellow-50 rounded-lg border border-yellow-200">
            <div className="text-2xl font-bold text-yellow-600">{security.medium || 0}</div>
            <div className="text-xs text-yellow-700 font-medium">Medium</div>
          </div>
          <div className="text-center p-3 bg-blue-50 rounded-lg border border-blue-200">
            <div className="text-2xl font-bold text-blue-600">{security.low || 0}</div>
            <div className="text-xs text-blue-700 font-medium">Low</div>
          </div>
        </div>
      </div>

      {/* 총 취약점 */}
      <div className="flex items-center justify-between px-4 py-3 bg-gray-50 rounded-lg">
        <span className="text-sm font-medium text-gray-600">총 발견된 취약점</span>
        <span className="text-lg font-bold text-gray-900">
          {security.vulnerability_count || 0}개
        </span>
      </div>

      {/* 요약 메시지 */}
      {security.summary && (
        <div className="text-sm text-gray-600 p-3 bg-blue-50 rounded-lg border border-blue-100">
          {security.summary}
        </div>
      )}

      {/* 취약점 상세 목록 */}
      {security.vulnerability_details && security.vulnerability_details.length > 0 && (
        <div className="bg-white rounded-xl p-4 border border-gray-200">
          <h4 className="font-bold text-gray-900 mb-3">발견된 취약점 목록</h4>
          <div className="space-y-3 max-h-80 overflow-y-auto">
            {security.vulnerability_details.map((vuln, idx) => {
              const severityColors = {
                CRITICAL: { bg: "bg-red-50", border: "border-red-300", badge: "bg-red-600 text-white" },
                HIGH: { bg: "bg-orange-50", border: "border-orange-300", badge: "bg-orange-600 text-white" },
                MEDIUM: { bg: "bg-yellow-50", border: "border-yellow-300", badge: "bg-yellow-600 text-white" },
                LOW: { bg: "bg-blue-50", border: "border-blue-300", badge: "bg-blue-600 text-white" },
              };
              const colors = severityColors[vuln.severity?.toUpperCase()] || severityColors.MEDIUM;

              return (
                <div key={idx} className={`p-3 rounded-lg border-l-4 ${colors.bg} ${colors.border}`}>
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className={`text-xs px-2 py-0.5 rounded font-bold ${colors.badge}`}>
                        {vuln.severity || "UNKNOWN"}
                      </span>
                      {vuln.cve_id && (
                        <a
                          href={`https://nvd.nist.gov/vuln/detail/${vuln.cve_id}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-xs font-mono text-blue-600 hover:underline"
                        >
                          {vuln.cve_id}
                        </a>
                      )}
                    </div>
                    {vuln.cvss_score && (
                      <span className="text-xs font-bold text-gray-600">
                        CVSS: {vuln.cvss_score}
                      </span>
                    )}
                  </div>
                  <div className="text-sm font-medium text-gray-900 mb-1">
                    {vuln.package_name || vuln.dependency_name || "패키지 정보 없음"}
                    {vuln.version && <span className="text-gray-500 ml-1">({vuln.version})</span>}
                  </div>
                  {vuln.description && (
                    <p className="text-xs text-gray-600 line-clamp-2">{vuln.description}</p>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};

// 위험 요소 아이템
const RiskItem = ({ risk }) => {
  const getSeverityConfig = (severity) => {
    const configs = {
      high: {
        containerClass: "border-red-500 bg-red-50",
        badgeClass: "bg-red-500 text-white",
        label: "HIGH",
      },
      medium: {
        containerClass: "border-yellow-500 bg-yellow-50",
        badgeClass: "bg-yellow-500 text-white",
        label: "MEDIUM",
      },
      low: {
        containerClass: "border-blue-500 bg-blue-50",
        badgeClass: "bg-blue-500 text-white",
        label: "LOW",
      },
    };
    return configs[severity] || configs.medium;
  };

  const severityConfig = getSeverityConfig(
    risk.severity || risk.impact || "medium"
  );

  return (
    <div
      className={`rounded-xl p-4 border-l-4 ${severityConfig.containerClass}`}
    >
      <div className="flex items-start justify-between mb-2">
        <span
          className={`text-xs px-3 py-1 rounded-full font-bold ${severityConfig.badgeClass}`}
        >
          {severityConfig.label}
        </span>
      </div>
      <p className="text-sm font-medium text-gray-900 mb-2">
        {risk.description || risk.title}
      </p>
      <div className="text-xs text-gray-500">
        Type: {risk.type || "general"}
      </div>
    </div>
  );
};

// 기여 작업 아이템
const ContributionItem = ({ recommendation }) => {
  const getPriorityConfig = (difficulty) => {
    const configs = {
      easy: {
        containerClass: "border-green-500 bg-green-50",
        badgeClass: "bg-green-500 text-white",
        label: "쉬움",
      },
      medium: {
        containerClass: "border-yellow-500 bg-yellow-50",
        badgeClass: "bg-yellow-500 text-white",
        label: "보통",
      },
      hard: {
        containerClass: "border-red-500 bg-red-50",
        badgeClass: "bg-red-500 text-white",
        label: "어려움",
      },
    };
    return configs[difficulty] || configs.medium;
  };

  const priorityConfig = getPriorityConfig(recommendation.difficulty);

  return (
    <div
      className={`rounded-xl p-4 border-l-4 transition-all ${priorityConfig.containerClass}`}
    >
      <div className="flex items-start justify-between mb-2">
        <span
          className={`text-xs px-3 py-1 rounded-full font-bold ${priorityConfig.badgeClass}`}
        >
          {priorityConfig.label}
        </span>
      </div>
      <h4 className="text-sm font-bold text-gray-900 mb-1">
        {recommendation.title}
      </h4>
      <p className="text-xs text-gray-600 mb-2">{recommendation.description}</p>

      {recommendation.tags && recommendation.tags.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-2">
          {recommendation.tags.slice(0, 3).map((tag) => (
            <span
              key={tag}
              className="text-xs px-2 py-1 bg-gray-100 text-gray-600 rounded"
            >
              {tag}
            </span>
          ))}
        </div>
      )}

      {/* GitHub 이슈 링크 */}
      {recommendation.url && (
        <a
          href={recommendation.url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800 font-medium mt-1"
        >
          <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 16 16">
            <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.012 8.012 0 0 0 16 8c0-4.42-3.58-8-8-8z" />
          </svg>
          GitHub에서 보기 {recommendation.issueNumber ? `#${recommendation.issueNumber}` : ""}
        </a>
      )}
    </div>
  );
};

// 관련 프로젝트 카드
const RelatedProjectCard = ({ project }) => {
  const healthScore = project.score || 75;

  const getScoreConfig = (score) => {
    if (score >= 80)
      return {
        color: "text-green-600",
        bg: "bg-green-50",
        label: "Excellent",
      };
    if (score >= 60)
      return {
        color: "text-yellow-600",
        bg: "bg-yellow-50",
        label: "Good",
      };
    return {
      color: "text-red-600",
      bg: "bg-red-50",
      label: "Fair",
    };
  };

  const scoreConfig = getScoreConfig(healthScore);

  return (
    <div className="bg-white/60 backdrop-blur-sm rounded-xl p-5 shadow-md hover:shadow-xl transition-all border border-white/60">
      {/* Project Name */}
      <h4 className="text-base font-bold text-gray-900 mb-2 truncate">
        {project.name || project.title}
      </h4>

      {/* Score */}
      <div
        className={`${scoreConfig.bg} rounded-lg px-3 py-2 mb-3 flex items-center justify-between`}
      >
        <span className={`text-xs font-semibold ${scoreConfig.color}`}>
          {scoreConfig.label}
        </span>
        <span className={`text-xl font-black ${scoreConfig.color}`}>
          {healthScore}
        </span>
      </div>

      {/* Description */}
      <p className="text-sm text-gray-600 line-clamp-2 mb-3">
        {project.description || "관련 프로젝트입니다."}
      </p>

      {/* AI 추천 이유 */}
      {project.recommendationReason && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-3">
          <p className="text-xs font-semibold text-blue-900 mb-1">
            AI 추천 이유
          </p>
          <p className="text-xs text-blue-800 leading-relaxed">
            {project.recommendationReason}
          </p>
        </div>
      )}

      {/* Stats */}
      <div className="flex items-center gap-3 mb-3 text-xs text-gray-500">
        {project.stars !== undefined && (
          <div className="flex items-center gap-1">
            <Star className="w-3 h-3 text-yellow-500" />
            <span className="font-semibold text-gray-700">
              {formatNumber(project.stars)}
            </span>
          </div>
        )}
        {project.match && (
          <span className="font-semibold text-gray-700">
            {project.match}% match
          </span>
        )}
      </div>

      {/* Action Button */}
      <button className="w-full inline-flex items-center justify-center gap-2 bg-blue-600 text-white px-4 py-2.5 rounded-lg text-sm font-semibold hover:bg-blue-700 transition-all">
        <span>Analyze</span>
        <ArrowRight className="w-4 h-4" />
      </button>
    </div>
  );
};

export default AnalysisReportSection;
