
import React from "react";
import { CheckCircle, Target, ExternalLink } from "lucide-react";
import { CollapsibleCard } from "./ReportWidgets";

const RecommendedTasksSection = ({
    analysisResult,
    expanded,
    onToggle,
    onOpenGuide,
}) => {
    // recommendedIssues, recommendations 둘 다 확인
    const issues = analysisResult?.recommendedIssues || [];
    const recommendationsList = analysisResult?.recommendations || [];

    // 데이터 유효성
    const hasIssues = issues.length > 0;
    const hasRecommendations = recommendationsList.length > 0;

    if (!hasIssues && !hasRecommendations) return null;

    return (
        <CollapsibleCard
            title="추천 기여 활동"
            isExpanded={expanded}
            onToggle={onToggle}
            guideKey="recommendedTasks"
            onOpenGuide={onOpenGuide}
        >
            <div className="space-y-6">
                {/* 1. 구체적인 Issue 추천 */}
                {hasIssues && (
                    <div className="space-y-3">
                        <h4 className="font-semibold text-gray-800 dark:text-gray-200 flex items-center gap-2">
                            <Target className="w-4 h-4 text-blue-500" />
                            추천 이슈
                        </h4>
                        <div className="grid gap-3">
                            {issues.map((issue, idx) => (
                                <div key={idx} className="p-3 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg group hover:border-blue-300 dark:hover:border-blue-700 transition-colors">
                                    <div className="flex justify-between items-start gap-3">
                                        <div className="flex-1">
                                            <div className="flex items-center gap-2 mb-1">
                                                <span className="font-medium text-gray-900 dark:text-white">#{issue.number} {issue.title}</span>
                                                {issue.labels && issue.labels.map((label, lIdx) => (
                                                    <span key={lIdx} className="text-xs px-1.5 py-0.5 bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 rounded">
                                                        {label}
                                                    </span>
                                                ))}
                                            </div>
                                            <p className="text-sm text-gray-600 dark:text-gray-400 line-clamp-1">{issue.body || "No description provided."}</p>
                                        </div>
                                        <a href={issue.url} target="_blank" rel="noopener noreferrer" className="p-2 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors">
                                            <ExternalLink className="w-4 h-4" />
                                        </a>
                                    </div>
                                    {issue.reason && (
                                        <div className="mt-2 text-xs text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/20 p-2 rounded">
                                            💡 {issue.reason}
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {/* 2. 일반적인 추천 사항 */}
                {hasRecommendations && (
                    <div className="space-y-3">
                        <h4 className="font-semibold text-gray-800 dark:text-gray-200 flex items-center gap-2">
                            <CheckCircle className="w-4 h-4 text-green-500" />
                            일반 제안
                        </h4>
                        <ul className="space-y-2">
                            {recommendationsList.map((rec, idx) => (
                                <li key={idx} className="flex gap-3 text-sm text-gray-700 dark:text-gray-300 p-2 bg-gray-50 dark:bg-gray-800/50 rounded-lg">
                                    <span className="mt-1 w-1.5 h-1.5 rounded-full bg-green-500 shrink-0"></span>
                                    <span>{rec}</span>
                                </li>
                            ))}
                        </ul>
                    </div>
                )}
            </div>
        </CollapsibleCard>
    );
};

export default RecommendedTasksSection;
