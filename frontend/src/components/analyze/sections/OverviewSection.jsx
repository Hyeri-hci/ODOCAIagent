import React from "react";
import { Star, GitFork, Users } from "lucide-react";
import {
  CollapsibleCard,
  ScoreCard,
  StatCard,
  MetricBar,
} from "./ReportWidgets";
import { formatNumber } from "../../../utils/formatNumber";

const OverviewSection = ({
  analysisResult,
  expanded,
  onToggle,
  onOpenGuide,
  statusConfig,
}) => {
  const { summary, technicalDetails, rawAnalysis } = analysisResult || {};

  // 데이터 유효성 검사
  const hasValidOverviewData =
    summary?.score > 0 ||
    technicalDetails?.stars > 0 ||
    technicalDetails?.forks > 0 ||
    technicalDetails?.contributors > 0 ||
    technicalDetails?.documentationQuality > 0 ||
    technicalDetails?.activityMaintainability > 0;

  if (!hasValidOverviewData) return null;

  return (
    <CollapsibleCard
      title="분석 결과 리포트"
      isExpanded={expanded}
      onToggle={onToggle}
      guideKey="overview"
      onOpenGuide={onOpenGuide}
    >
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        <div className="lg:col-span-4">
          <ScoreCard score={summary?.score || 0} statusConfig={statusConfig} />
        </div>
        <div className="lg:col-span-8">
          <h2 className="text-2xl font-black text-gray-900 dark:text-gray-100 mb-6">
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
              label="Active Contributors (90일)"
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
  );
};

export default OverviewSection;
