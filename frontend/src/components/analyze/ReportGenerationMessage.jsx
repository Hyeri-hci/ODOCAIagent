import React, { useState } from "react";
import {
  CheckCircle,
  Loader2,
  TrendingUp,
  Shield,
  AlertTriangle,
  Lightbulb,
  Target,
  FolderGit2,
  BookOpen,
  FileText,
  Zap,
  ChevronRight,
  ChevronDown,
  ChevronUp,
  Sparkles,
  Minimize2,
  Maximize2,
} from "lucide-react";

/**
 * 보고서 생성 진행상황을 보여주는 채팅 메시지 컴포넌트
 * Gemini Deep Research 스타일로 섹션별 진행상황 표시
 */
const ReportGenerationMessage = ({
  sections,
  onSectionClick,
  isComplete,
  analysisResult,
  isCollapsed,
  onToggleCollapse,
  progressMessage,
}) => {
  const [expandedSection, setExpandedSection] = useState(null);

  // 섹션 정의
  const sectionConfig = [
    {
      id: "overview",
      label: "종합 점수 분석",
      icon: TrendingUp,
      color: "indigo",
      description: "프로젝트 건강도 점수와 핵심 지표를 계산합니다.",
      dataKey: "summary",
    },
    {
      id: "metrics",
      label: "상세 메트릭",
      icon: Zap,
      color: "purple",
      description: "활동성, 응답성, 커밋 현황을 분석합니다.",
      dataKey: "technicalDetails",
    },
    {
      id: "projectSummary",
      label: "프로젝트 요약",
      icon: FileText,
      color: "blue",
      description: "AI가 프로젝트 특성을 요약합니다.",
      dataKey: "projectSummary",
    },
    {
      id: "security",
      label: "보안 분석",
      icon: Shield,
      color: "red",
      description: "의존성 취약점과 보안 점수를 검사합니다.",
      dataKey: "security",
    },
    {
      id: "risks",
      label: "위험 요소",
      icon: AlertTriangle,
      color: "orange",
      description: "잠재적 위험 요소를 식별합니다.",
      dataKey: "risks",
    },
    {
      id: "recommendedIssues",
      label: "추천 이슈",
      icon: Lightbulb,
      color: "amber",
      description: "입문자를 위한 Good First Issues를 추천합니다.",
      dataKey: "recommendedIssues",
    },
    {
      id: "recommendations",
      label: "기여 작업 추천",
      icon: Target,
      color: "green",
      description: "기여할 수 있는 작업을 추천합니다.",
      dataKey: "recommendations",
    },
    {
      id: "similarProjects",
      label: "유사 프로젝트",
      icon: FolderGit2,
      color: "violet",
      description: "학습에 도움이 될 유사 프로젝트를 찾습니다.",
      dataKey: "similarProjects",
    },
    {
      id: "onboardingPlan",
      label: "온보딩 플랜",
      icon: BookOpen,
      color: "cyan",
      description: "맞춤형 학습 플랜을 생성합니다.",
      dataKey: "onboardingPlan",
    },
  ];

  // 섹션 상태 결정
  const getSectionStatus = (section) => {
    const data = analysisResult?.[section.dataKey];

    if (sections[section.id] === "complete") return "complete";
    if (sections[section.id] === "loading") return "loading";
    if (sections[section.id] === "error") return "error";

    // 데이터가 있으면 complete
    if (data) {
      if (Array.isArray(data) && data.length > 0) return "complete";
      if (typeof data === "object" && Object.keys(data).length > 0)
        return "complete";
      if (typeof data === "string" && data.length > 0) return "complete";
    }

    return "pending";
  };

  // 진행률 계산
  const completedCount = sectionConfig.filter(
    (s) => getSectionStatus(s) === "complete"
  ).length;
  const progress = Math.round((completedCount / sectionConfig.length) * 100);

  const colorClasses = {
    indigo: {
      bg: "bg-indigo-50",
      text: "text-indigo-600",
      border: "border-indigo-200",
      ring: "ring-indigo-500",
    },
    purple: {
      bg: "bg-purple-50",
      text: "text-purple-600",
      border: "border-purple-200",
      ring: "ring-purple-500",
    },
    blue: {
      bg: "bg-blue-50",
      text: "text-blue-600",
      border: "border-blue-200",
      ring: "ring-blue-500",
    },
    red: {
      bg: "bg-red-50",
      text: "text-red-600",
      border: "border-red-200",
      ring: "ring-red-500",
    },
    orange: {
      bg: "bg-orange-50",
      text: "text-orange-600",
      border: "border-orange-200",
      ring: "ring-orange-500",
    },
    amber: {
      bg: "bg-amber-50",
      text: "text-amber-600",
      border: "border-amber-200",
      ring: "ring-amber-500",
    },
    green: {
      bg: "bg-green-50",
      text: "text-green-600",
      border: "border-green-200",
      ring: "ring-green-500",
    },
    violet: {
      bg: "bg-violet-50",
      text: "text-violet-600",
      border: "border-violet-200",
      ring: "ring-violet-500",
    },
    cyan: {
      bg: "bg-cyan-50",
      text: "text-cyan-600",
      border: "border-cyan-200",
      ring: "ring-cyan-500",
    },
  };

  // 축소된 상태일 때의 렌더링
  if (isCollapsed) {
    return (
      <div className="bg-gray-800 rounded-xl overflow-hidden">
        <button
          onClick={onToggleCollapse}
          className="w-full px-4 py-3 flex items-center gap-3 hover:bg-gray-700 transition-colors"
        >
          <div className="w-8 h-8 bg-gray-700 rounded-lg flex items-center justify-center">
            <FileText className="w-4 h-4 text-gray-300" />
          </div>
          <div className="flex-1 text-left">
            <span className="text-white text-sm">
              {isComplete ? "분석 보고서" : "보고서 생성 중..."}
            </span>
            <span className="text-gray-400 text-xs ml-2">
              {completedCount}/{sectionConfig.length}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-white text-sm">{progress}%</span>
            <Maximize2 className="w-4 h-4 text-gray-400" />
          </div>
        </button>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
      {/* 헤더 */}
      <div className="bg-gray-800 px-5 py-4">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 bg-gray-700 rounded-lg flex items-center justify-center">
            <FileText className="w-4 h-4 text-gray-300" />
          </div>
          <div className="flex-1">
            <h3 className="text-white text-sm font-medium">
              {isComplete ? "분석 보고서" : "보고서 생성 중..."}
            </h3>
            <p className="text-gray-400 text-xs">
              {isComplete
                ? "모든 섹션 분석 완료"
                : progressMessage ||
                  `${completedCount}/${sectionConfig.length} 섹션 완료`}
            </p>
          </div>
          <div className="text-right flex items-center gap-3">
            <div className="text-lg font-semibold text-white">{progress}%</div>
            {isComplete && onToggleCollapse && (
              <button
                onClick={onToggleCollapse}
                className="p-1.5 hover:bg-gray-700 rounded transition-colors"
                title="보고서 카드 축소"
              >
                <Minimize2 className="w-4 h-4 text-gray-400" />
              </button>
            )}
          </div>
        </div>

        {/* 진행 바 */}
        <div className="mt-3 h-1.5 bg-gray-700 rounded-full overflow-hidden">
          <div
            className="h-full bg-blue-500 rounded-full transition-all duration-300"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {/* 섹션 목록 */}
      <div className="p-4 space-y-2">
        {sectionConfig.map((section) => {
          const status = getSectionStatus(section);
          const colors = colorClasses[section.color];
          const IconComponent = section.icon;
          const isExpanded = expandedSection === section.id;

          return (
            <div
              key={section.id}
              className={`
                rounded-lg border transition-colors cursor-pointer
                ${status === "loading" ? `${colors.border} ${colors.bg}` : ""}
                ${
                  status === "complete"
                    ? "border-gray-200 hover:bg-gray-50"
                    : ""
                }
                ${status === "pending" ? "border-gray-100 bg-gray-50/50" : ""}
                ${status === "error" ? "border-red-200 bg-red-50" : ""}
              `}
              onClick={() => {
                if (status === "complete") {
                  setExpandedSection(isExpanded ? null : section.id);
                  onSectionClick?.(section.id);
                }
              }}
            >
              <div className="flex items-center gap-3 p-3">
                {/* 아이콘 */}
                <div
                  className={`
                    w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0
                    ${status === "loading" ? `${colors.bg}` : ""}
                    ${status === "complete" ? `${colors.bg}` : ""}
                    ${status === "pending" ? "bg-gray-100" : ""}
                  `}
                >
                  {status === "loading" ? (
                    <Loader2
                      className={`w-4 h-4 ${colors.text} animate-spin`}
                    />
                  ) : status === "complete" ? (
                    <IconComponent className={`w-4 h-4 ${colors.text}`} />
                  ) : (
                    <IconComponent className="w-4 h-4 text-gray-400" />
                  )}
                </div>

                {/* 텍스트 */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span
                      className={`font-semibold text-sm ${
                        status === "pending" ? "text-gray-400" : "text-gray-900"
                      }`}
                    >
                      {section.label}
                    </span>
                    {status === "loading" && (
                      <span className="text-xs text-gray-500">분석 중...</span>
                    )}
                  </div>
                  {status !== "complete" && (
                    <p className="text-xs text-gray-500 truncate">
                      {section.description}
                    </p>
                  )}
                </div>

                {/* 상태 아이콘 */}
                <div className="flex-shrink-0">
                  {status === "complete" ? (
                    <CheckCircle className="w-5 h-5 text-green-500" />
                  ) : status === "loading" ? (
                    <div className="w-5 h-5 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
                  ) : (
                    <div className="w-5 h-5 border-2 border-gray-300 rounded-full" />
                  )}
                </div>

                {status === "complete" && (
                  <ChevronRight
                    className={`w-4 h-4 text-gray-400 transition-transform ${
                      isExpanded ? "rotate-90" : ""
                    }`}
                  />
                )}
              </div>

              {/* 확장된 프리뷰 */}
              {isExpanded && status === "complete" && (
                <div className="px-3 pb-3 pt-0">
                  <SectionPreview
                    section={section}
                    data={analysisResult?.[section.dataKey]}
                  />
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* 완료 시 액션 버튼 */}
      {isComplete && (
        <div className="px-4 pb-4">
          <button
            onClick={() => onSectionClick?.("scrollToReport")}
            className="w-full py-2.5 bg-gray-800 text-white text-sm rounded-lg hover:bg-gray-700 transition-colors flex items-center justify-center gap-2"
          >
            <FileText className="w-4 h-4" />
            전체 보고서 보기
          </button>
        </div>
      )}
    </div>
  );
};

// 섹션 프리뷰 컴포넌트
const SectionPreview = ({ section, data }) => {
  if (!data) return null;

  switch (section.id) {
    case "overview":
      return (
        <div className="bg-indigo-50 rounded-lg p-3 text-sm">
          <div className="flex items-center justify-between">
            <span className="text-gray-600">종합 점수</span>
            <span className="text-2xl font-black text-indigo-600">
              {data.score || 0}
            </span>
          </div>
        </div>
      );

    case "security":
      return (
        <div className="bg-red-50 rounded-lg p-3 text-sm">
          <div className="flex items-center justify-between">
            <span className="text-gray-600">보안 등급</span>
            <span className="text-xl font-bold text-red-600">
              {data.grade || "N/A"}
            </span>
          </div>
          <div className="text-xs text-gray-500 mt-1">
            취약점 {data.vulnerability_count || 0}개 발견
          </div>
        </div>
      );

    case "risks":
      return (
        <div className="bg-orange-50 rounded-lg p-3 text-sm">
          <span className="text-gray-600">
            {Array.isArray(data)
              ? `${data.length}개 위험 요소 발견`
              : "분석 완료"}
          </span>
        </div>
      );

    case "recommendedIssues":
      return (
        <div className="bg-amber-50 rounded-lg p-3 text-sm">
          <span className="text-gray-600">
            {Array.isArray(data)
              ? `${data.length}개 추천 이슈`
              : "이슈 분석 완료"}
          </span>
        </div>
      );

    case "recommendations":
      return (
        <div className="bg-green-50 rounded-lg p-3 text-sm">
          <span className="text-gray-600">
            {Array.isArray(data)
              ? `${data.length}개 기여 작업 추천`
              : "추천 분석 완료"}
          </span>
        </div>
      );

    case "similarProjects":
      return (
        <div className="bg-violet-50 rounded-lg p-3 text-sm">
          <span className="text-gray-600">
            {Array.isArray(data)
              ? `${data.length}개 유사 프로젝트`
              : "프로젝트 검색 완료"}
          </span>
        </div>
      );

    case "onboardingPlan":
      return (
        <div className="bg-cyan-50 rounded-lg p-3 text-sm">
          <span className="text-gray-600">
            {Array.isArray(data)
              ? `${data.length}주 학습 플랜 생성됨`
              : "플랜 생성 완료"}
          </span>
        </div>
      );

    default:
      return (
        <div className="bg-gray-50 rounded-lg p-3 text-sm text-gray-600">
          분석 완료
        </div>
      );
  }
};

export default ReportGenerationMessage;
