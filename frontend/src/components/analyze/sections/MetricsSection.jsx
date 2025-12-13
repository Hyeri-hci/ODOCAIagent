import React from "react";
import {
  Clock,
  GitPullRequest,
  AlertCircle,
  MessageSquare,
  Activity,
  GitMerge,
} from "lucide-react";
import { CollapsibleCard } from "./ReportWidgets";
import { formatNumber } from "../../../utils/formatNumber";

const MetricsSection = ({
  analysisResult,
  expanded,
  onToggle,
  onOpenGuide,
}) => {
  const { technicalDetails } = analysisResult || {};

  const hasValidMetricsData =
    technicalDetails?.daysSinceLastCommit !== undefined ||
    technicalDetails?.commits30d > 0 ||
    technicalDetails?.issueCloseRate > 0 ||
    technicalDetails?.prMergeSpeed !== undefined ||
    technicalDetails?.openIssues > 0 ||
    technicalDetails?.openPRs > 0;

  if (!hasValidMetricsData) return null;

  return (
    <CollapsibleCard
      title="상세 지표 분석"
      isExpanded={expanded}
      onToggle={onToggle}
      guideKey="metrics"
      onOpenGuide={onOpenGuide}
    >
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        {/* 1. 마지막 커밋 */}
        <MetricItem
          icon={Clock}
          label="마지막 커밋"
          value={`${technicalDetails?.daysSinceLastCommit || 0}일 전`}
          subValue="오늘"
          color="text-blue-500"
          bgColor="bg-blue-50 dark:bg-blue-900/20"
        />

        {/* 2. 최근 30일 커밋 (New) */}
        <MetricItem
          icon={Activity} // Need to import Activity if not present, checking imports...
          label="최근 30일 커밋"
          value={technicalDetails?.commits30d || 0}
          subValue="commits"
          color="text-green-500"
          bgColor="bg-green-50 dark:bg-green-900/20"
        />

        {/* 3. 이슈 해결률 */}
        <MetricItem
          icon={MessageSquare}
          label="이슈 해결률"
          value={`${Math.round(technicalDetails?.issueCloseRate || 0)}%`}
          subValue="Closed"
          color="text-purple-500"
          bgColor="bg-purple-50 dark:bg-purple-900/20"
        />

        {/* 4. PR 병합 속도 */}
        <MetricItem
          icon={GitPullRequest}
          label="PR 병합 속도"
          value={technicalDetails?.prMergeSpeed || "0"}
          subValue="중앙값"
          color="text-cyan-500"
          bgColor="bg-cyan-50 dark:bg-cyan-900/20"
        />

        {/* 5. 열린 이슈 (Split from previous) */}
        <MetricItem
          icon={AlertCircle}
          label="열린 이슈"
          value={formatNumber(technicalDetails?.openIssues || 0)}
          subValue="Issues"
          color="text-orange-500"
          bgColor="bg-orange-50 dark:bg-orange-900/20"
        />

        {/* 6. 열린 PR (Split from previous) */}
        <MetricItem
          icon={GitMerge}
          label="열린 PR"
          value={formatNumber(technicalDetails?.openPRs || 0)}
          subValue="pull requests"
          color="text-pink-500"
          bgColor="bg-pink-50 dark:bg-pink-900/20"
        />
      </div>
    </CollapsibleCard>
  );
};

const MetricItem = ({ icon: Icon, label, value, subValue, color, bgColor }) => (
  <div
    className={`p-4 rounded-xl border border-gray-100 dark:border-gray-700 flex flex-col items-center text-center hover:shadow-md transition-shadow ${bgColor}`}
  >
    <div
      className={`p-3 rounded-full bg-white dark:bg-gray-800 shadow-sm mb-3 ${color}`}
    >
      <Icon className="w-6 h-6" />
    </div>
    <div className="text-sm text-gray-500 dark:text-gray-400 font-medium mb-1">
      {label}
    </div>
    <div className="text-lg font-bold text-gray-900 dark:text-white mb-1">
      {value}
    </div>
    <div className="text-xs text-gray-400 dark:text-gray-500">{subValue}</div>
  </div>
);

export default MetricsSection;
