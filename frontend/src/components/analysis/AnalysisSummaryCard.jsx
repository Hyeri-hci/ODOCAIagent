import React from "react";
import {
  TrendingUp,
  CheckCircle,
  AlertTriangle,
  Loader2,
  Star,
  GitFork,
  Users,
  Shield,
  Code,
  Activity,
} from "lucide-react";

// 분석 요약 카드 컴포넌트 - 2단 레이어(Overview Score + Repository Statistics) + 3가지 상태 지원 (Demo/Loading/Completed)
export const AnalysisSummaryCard = ({
  repoName = "Repository",
  score = 92,
  statusLabel = "Excellent",
  metrics = {
    security: 85,
    quality: 92,
    activity: 78,
  },
  stats = {
    stars: 182000,
    forks: 12000,
    contributors: 4200,
  },
  isLoading = false,
  isCompleted = false,
  badgeLabel = null,
  onPrimaryAction,
  primaryActionText = "기여 작업 추천받기",
  className = "",
}) => {
  const getStatusConfig = (score) => {
    if (score >= 80)
      return {
        label: "Excellent",
        color: "from-green-400 to-emerald-500",
        textColor: "text-green-600",
        bgColor: "bg-green-50",
        borderColor: "border-green-200",
        icon: CheckCircle,
      };
    if (score >= 60)
      return {
        label: "Good",
        color: "from-yellow-400 to-orange-500",
        textColor: "text-yellow-600",
        bgColor: "bg-yellow-50",
        borderColor: "border-yellow-200",
        icon: AlertTriangle,
      };
    return {
      label: "Needs Attention",
      color: "from-red-400 to-rose-500",
      textColor: "text-red-600",
      bgColor: "bg-red-50",
      borderColor: "border-red-200",
      icon: AlertTriangle,
    };
  };

  const statusConfig = getStatusConfig(score);
  const StatusIcon = statusConfig.icon;

  return (
    <div
      className={`bg-white/40 backdrop-blur-sm rounded-3xl shadow-2xl p-8 border border-white/60 ${className}`}
    >
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* LEFT: SCORE CARD */}
        <div className="lg:col-span-4">
          <div className="bg-gradient-to-br from-[#4F46E5] to-[#6366F1] rounded-2xl p-8 h-full shadow-xl">
            <div className="flex items-center gap-3 mb-6">
              <div className="w-12 h-12 bg-white/20 rounded-xl flex items-center justify-center">
                {isLoading ? (
                  <Loader2 className="w-6 h-6 text-white animate-spin" />
                ) : (
                  <TrendingUp className="w-6 h-6 text-white" />
                )}
              </div>
              <div>
                <h3 className="text-white font-bold text-lg">
                  {repoName} 프로젝트 분석
                </h3>
                <p className="text-indigo-200 text-sm">Overview Score</p>
              </div>
            </div>

            {/* 점수 표시 영역 */}
            <div className="bg-white rounded-2xl p-6 text-center mb-6">
              {isLoading ? (
                <div className="h-24 flex items-center justify-center">
                  <Loader2 className="w-12 h-12 text-indigo-600 animate-spin" />
                </div>
              ) : (
                <>
                  <div className="text-7xl font-black text-indigo-600 mb-3">
                    {score}
                  </div>
                  <div className="text-gray-600 text-sm font-semibold mb-4">
                    Score
                  </div>
                  <div className="h-3 bg-gray-100 rounded-full overflow-hidden">
                    {/* 점수별 색상 80+ Excellent / 60-79 Good / 0-59 Needs Attention */}
                    <div
                      className={`h-full bg-gradient-to-r ${statusConfig.color} rounded-full transition-all duration-1000`}
                      style={{ width: `${score}%` }}
                    ></div>
                  </div>
                </>
              )}
            </div>

            {/* 상태 뱃지 영역 */}
            {isCompleted && (
              <div
                className={`${statusConfig.bgColor} ${statusConfig.borderColor} border-2 px-4 py-3 rounded-xl flex items-center gap-2 justify-center`}
              >
                <StatusIcon className={`w-5 h-5 ${statusConfig.textColor}`} />
                <span className={`${statusConfig.textColor} font-bold`}>
                  {statusConfig.label}
                </span>
              </div>
            )}

            {badgeLabel && !isCompleted && (
              <div className="bg-green-50 border-2 border-green-200 px-4 py-3 rounded-xl flex items-center gap-2 justify-center">
                <span className="text-green-700 font-bold text-sm">
                  {badgeLabel}
                </span>
              </div>
            )}
          </div>
        </div>

        {/* RIGHT: REPOSITORY STATISTICS */}
        <div className="lg:col-span-8">
          <h2 className="text-2xl font-black text-gray-900 mb-6">
            {repoName} Repository Statistics
          </h2>

          {/* Stats Grid */}
          <div className="grid grid-cols-3 gap-4 mb-8">
            <StatCard
              icon={Star}
              value={formatNumber(stats.stars)}
              label="GitHub Stars"
              gradient="from-yellow-50 to-orange-50"
              border="border-yellow-200"
              iconColor="text-yellow-500"
              isLoading={isLoading}
            />
            <StatCard
              icon={GitFork}
              value={formatNumber(stats.forks)}
              label="Forks"
              gradient="from-cyan-50 to-blue-50"
              border="border-cyan-200"
              iconColor="text-cyan-600"
              isLoading={isLoading}
            />
            <StatCard
              icon={Users}
              value={formatNumber(stats.contributors)}
              label="Contributors"
              gradient="from-purple-50 to-pink-50"
              border="border-purple-200"
              iconColor="text-purple-600"
              isLoading={isLoading}
            />
          </div>

          {/* Metric Bars */}
          {/* 보안 - 초록 / 코드 품질 - 파랑 / 커뮤니티 활성도 - 보라 */}
          <div className="space-y-5">
            <MetricBar
              icon={Shield}
              label="보안 점수"
              value={metrics.security}
              color="from-green-400 to-emerald-500"
              textColor="text-green-600"
              isLoading={isLoading}
            />
            <MetricBar
              icon={Code}
              label="코드 품질"
              value={metrics.quality}
              color="from-blue-400 to-indigo-500"
              textColor="text-blue-600"
              isLoading={isLoading}
            />
            <MetricBar
              icon={Activity}
              label="커뮤니티 활성도"
              value={metrics.activity}
              color="from-purple-400 to-pink-500"
              textColor="text-purple-600"
              isLoading={isLoading}
            />
          </div>
        </div>
      </div>
    </div>
  );
};

// 개별 통계 카드 컴포넌트
const StatCard = ({
  icon: Icon,
  value,
  label,
  gradient,
  border,
  iconColor,
  isLoading,
}) => (
  <div
    className={`bg-gradient-to-br ${gradient} rounded-2xl p-5 border ${border}`}
  >
    {isLoading ? (
      <div className="h-20 flex items-center justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
      </div>
    ) : (
      <>
        <Icon className={`w-6 h-6 ${iconColor} mb-2`} />
        <div className="text-3xl font-bold text-gray-900 mb-1">{value}</div>
        <div className="text-sm text-gray-600">{label}</div>
      </>
    )}
  </div>
);

// 개별 메트릭 바 컴포넌트
const MetricBar = ({
  icon: Icon,
  label,
  value,
  color,
  textColor,
  isLoading,
}) => (
  <div>
    <div className="flex items-center justify-between mb-2">
      <div className="flex items-center gap-2">
        <Icon className={`w-5 h-5 ${textColor}`} />
        <span className="font-bold text-gray-900">{label}</span>
      </div>
      {!isLoading && (
        <span className={`text-lg font-bold ${textColor}`}>{value}%</span>
      )}
    </div>
    <div className="h-3 bg-gray-100 rounded-full overflow-hidden">
      {isLoading ? (
        <div className="h-full bg-gray-300 animate-pulse rounded-full"></div>
      ) : (
        <div
          className={`h-full bg-gradient-to-r ${color} rounded-full transition-all duration-1000`}
          style={{ width: `${value}%` }}
        ></div>
      )}
    </div>
  </div>
);

// 숫자 포맷팅 함수 (예: 182000 -> 182K)
const formatNumber = (num) => {
  if (num >= 1000000) return (num / 1000000).toFixed(1) + "M";
  if (num >= 1000) return (num / 1000).toFixed(1) + "k";
  return num;
};

export default AnalysisSummaryCard;
