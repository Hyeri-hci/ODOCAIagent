
import React from "react";
import ReactMarkdown from "react-markdown";
import { CollapsibleCard } from "./ReportWidgets";

const ProjectSummarySection = ({
    analysisResult,
    expanded,
    onToggle,
    onOpenGuide,
}) => {
    const { projectSummary } = analysisResult || {};

    if (!projectSummary || !projectSummary.trim()) return null;

    return (
        <CollapsibleCard
            title="프로젝트 요약"
            isExpanded={expanded}
            onToggle={onToggle}
            guideKey="projectSummary"
            onOpenGuide={onOpenGuide}
        >
            <div className="prose prose-sm max-w-none dark:prose-invert">
                <ReactMarkdown>{projectSummary}</ReactMarkdown>
            </div>
            {/* 태그 목록 (있는 경우) */}
            {analysisResult.topics && analysisResult.topics.length > 0 && (
                <div className="mt-4 flex flex-wrap gap-2">
                    {analysisResult.topics.map((topic, idx) => (
                        <span key={idx} className="px-2 py-1 bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 text-xs rounded-full">
                            #{topic}
                        </span>
                    ))}
                </div>
            )}
        </CollapsibleCard>
    );
};

export default ProjectSummarySection;
