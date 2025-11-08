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
      </div>
    </div>
  );
};

export default AnalysisSummaryCard;
