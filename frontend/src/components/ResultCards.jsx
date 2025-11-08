import React, { useState } from "react";
import {
  CheckCircle,
  ExternalLink,
  Calendar,
  ArrowUp,
  Star,
  GitFork,
  Users,
  TrendingUp,
  Shield,
  Code,
  Activity,
} from "lucide-react";
import {
  ReadmeSummary,
  DetectedRisksList,
  RecommendedContributionsList,
  RelatedProjectsSection,
} from "./analysis";

// 분석 결과 카드 컴포넌트
const ResultCards = ({
  analysisResult,
  onCreateMilestone,
  onViewReport,
  isCreatingMilestone,
}) => {
  const [selectedActions, setSelectedActions] = useState([]);

  if (!analysisResult) return null;

  let { score, risks, actions, similar, readme_summary, analysis } =
    analysisResult;

  // risks가 문자열 배열인 경우 객체 배열로 변환
  if (risks && risks.length > 0 && typeof risks[0] === "string") {
    risks = risks.map((riskStr, index) => ({
      id: index + 1,
      type: "general",
      severity: "medium",
      description: riskStr,
    }));
  }

  const handleSelectionChange = (newSelection) => {
    setSelectedActions(newSelection);
  };

  const handleCreateMilestone = () => {
    if (selectedActions.length > 0) {
      onCreateMilestone(selectedActions, analysis);
    }
  };

  // Status badge configuration
  const getStatusConfig = (score) => {
    if (score >= 80)
      return {
        label: "Excellent",
        color: "bg-green-500",
        textColor: "text-green-700",
        bgColor: "bg-green-50",
        borderColor: "border-green-200",
        icon: CheckCircle,
      };
    if (score >= 60)
      return {
        label: "Good",
        color: "bg-yellow-500",
        textColor: "text-yellow-700",
        bgColor: "bg-yellow-50",
        borderColor: "border-yellow-200",
      };
    return {
      label: "Needs Attention",
      color: "bg-red-500",
      textColor: "text-red-700",
      bgColor: "bg-red-50",
      borderColor: "border-red-200",
    };
  };

  const statusConfig = getStatusConfig(score);
  const StatusIcon = statusConfig.icon || CheckCircle;

  return (
    <section className="py-16 bg-[#F9FAFB] animate-fadeIn">
      <div className="container mx-auto px-4">
        <div className="max-w-7xl mx-auto animate-slideUp">
          {/* Section Title */}
          <div className="text-center mb-12">
            <div className="inline-flex items-center gap-3 bg-gradient-to-r from-[#2563EB] to-[#1E3A8A] px-6 py-3 rounded-2xl shadow-lg mb-4">
              <CheckCircle className="w-6 h-6 text-white" />
              <span className="text-white font-bold text-lg">분석 완료</span>
            </div>
            <h2 className="text-4xl md:text-5xl font-black text-[#1E3A8A] mb-4">
              분석 결과 리포트
            </h2>
            <p className="text-lg text-slate-600">
              AI가 프로젝트를 종합적으로 분석한 결과입니다
            </p>
          </div>

          {/* ========== MAIN ANALYSIS CARD ========== */}
          <div className="bg-white/40 backdrop-blur-sm rounded-3xl shadow-2xl p-8 border border-white/60">
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
              {/* LEFT: Score Card */}
              <div className="lg:col-span-4">
                <div className="bg-gradient-to-br from-[#4F46E5] to-[#6366F1] rounded-2xl p-8 h-full shadow-xl">
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
                      {score}
                    </div>
                    <div className="text-gray-600 text-sm font-semibold mb-4">
                      종합 점수
                    </div>
                    <div className="h-3 bg-gray-100 rounded-full overflow-hidden">
                      <div
                        className={`h-full bg-gradient-to-r ${statusConfig.color} rounded-full transition-all duration-1000`}
                        style={{ width: `${score}%` }}
                      ></div>
                    </div>
                  </div>

                  <div
                    className={`${statusConfig.bgColor} ${statusConfig.borderColor} border-2 px-4 py-3 rounded-xl flex items-center gap-2 justify-center`}
                  >
                    <StatusIcon
                      className={`w-5 h-5 ${statusConfig.textColor}`}
                    />
                    <span className={`${statusConfig.textColor} font-bold`}>
                      {statusConfig.label}
                    </span>
                  </div>
                </div>
              </div>

              {/* RIGHT: Repository Statistics */}
              <div className="lg:col-span-8">
                <h2 className="text-2xl font-black text-gray-900 mb-6">
                  Repository Statistics
                </h2>

                {/* Stats Grid */}
                <div className="grid grid-cols-3 gap-4 mb-8">
                  <div className="bg-gradient-to-br from-yellow-50 to-orange-50 rounded-2xl p-5 border border-yellow-200">
                    <Star className="w-6 h-6 text-yellow-500 mb-2" />
                    <div className="text-3xl font-bold text-gray-900 mb-1">
                      {analysis?.stars || 0}
                    </div>
                    <div className="text-sm text-gray-600">GitHub Stars</div>
                  </div>
                  <div className="bg-gradient-to-br from-cyan-50 to-blue-50 rounded-2xl p-5 border border-cyan-200">
                    <GitFork className="w-6 h-6 text-cyan-600 mb-2" />
                    <div className="text-3xl font-bold text-gray-900 mb-1">
                      {analysis?.forks || 0}
                    </div>
                    <div className="text-sm text-gray-600">Forks</div>
                  </div>
                  <div className="bg-gradient-to-br from-purple-50 to-pink-50 rounded-2xl p-5 border border-purple-200">
                    <Users className="w-6 h-6 text-purple-600 mb-2" />
                    <div className="text-3xl font-bold text-gray-900 mb-1">
                      {analysis?.contributors || 0}
                    </div>
                    <div className="text-sm text-gray-600">Contributors</div>
                  </div>
                </div>

                {/* Metric Bars */}
                <div className="space-y-5">
                  <MetricBar
                    icon={Shield}
                    label="보안 점수"
                    value={85}
                    color="green"
                  />
                  <MetricBar
                    icon={Code}
                    label="코드 품질"
                    value={92}
                    color="blue"
                  />
                  <MetricBar
                    icon={Activity}
                    label="커뮤니티 활성도"
                    value={78}
                    color="purple"
                  />
                </div>
              </div>
            </div>
          </div>

          {/* README Summary */}
          {readme_summary && (
            <ReadmeSummary content={readme_summary} className="mt-6" />
          )}

          {/* Action Area: Risks & Contributions */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
            <DetectedRisksList risks={risks} />
            <RecommendedContributionsList
              actions={actions}
              onSelectionChange={handleSelectionChange}
            />
          </div>

          {/* CTA Buttons */}
          <div className="flex flex-col sm:flex-row gap-4 justify-center pt-4 mt-6">
            <button
              onClick={onViewReport}
              className="inline-flex items-center justify-center gap-2 bg-white/60 backdrop-blur-sm text-indigo-600 border-2 border-indigo-300 px-8 py-4 rounded-xl font-bold text-base hover:bg-indigo-600 hover:text-white transition-all shadow-lg"
            >
              <ExternalLink className="w-5 h-5" />
              View Full Report
            </button>
            <button
              onClick={handleCreateMilestone}
              disabled={selectedActions.length === 0 || isCreatingMilestone}
              className="inline-flex items-center justify-center gap-2 bg-gradient-to-r from-green-500 to-emerald-500 text-white px-8 py-4 rounded-xl font-bold text-base hover:from-green-600 hover:to-emerald-600 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-lg"
            >
              <Calendar className="w-5 h-5" />
              {isCreatingMilestone
                ? "Creating..."
                : "Contribute Now with Kakao"}
            </button>
          </div>

          {/* Related Projects */}
          <RelatedProjectsSection projects={similar} />

          {/* Back to Top / New Analysis Button */}
          <div className="mt-12 text-center">
            <button
              onClick={() => {
                document
                  .getElementById("analyze")
                  ?.scrollIntoView({ behavior: "smooth" });
              }}
              className="inline-flex items-center gap-3 bg-gradient-to-r from-[#2563EB] to-[#1E3A8A] text-white px-10 py-4 rounded-2xl font-bold text-lg hover:shadow-2xl hover:scale-105 transition-all duration-300"
            >
              <ArrowUp className="w-6 h-6" />
              <span>새로운 프로젝트 분석하기</span>
            </button>
            <p className="text-sm text-gray-500 mt-4">
              다른 오픈소스 프로젝트를 분석하고 싶으신가요?
            </p>
          </div>
        </div>
      </div>
    </section>
  );
};

// 개별 메트릭 바 컴포넌트 (보안 점수, 코드 품질, 활성도)
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
        <span className={`text-lg font-bold ${config.text}`}>{value}%</span>
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

export default ResultCards;
