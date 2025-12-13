
import React from "react";
import { ExternalLink, Star, GitFork, GitBranch } from "lucide-react";
import { CollapsibleCard } from "./ReportWidgets";
import { formatNumber } from "../../../utils/formatNumber";

const SimilarProjectsSection = ({
    analysisResult,
    expanded,
    onToggle,
    onOpenGuide,
}) => {
    const { similarProjects } = analysisResult || {};

    if (!similarProjects || similarProjects.length === 0) return null;

    return (
        <CollapsibleCard
            title="유사 프로젝트 비교"
            isExpanded={expanded}
            onToggle={onToggle}
            guideKey="similarProjects"
            onOpenGuide={onOpenGuide}
        >
            <div className="space-y-4">
                {similarProjects.map((project, idx) => (
                    <div key={idx} className="p-4 border border-gray-200 dark:border-gray-700 rounded-xl hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors">
                        <div className="flex justify-between items-start mb-2">
                            <div>
                                <h4 className="font-bold text-gray-900 dark:text-white flex items-center gap-2">
                                    {project.name}
                                    <a href={project.url} target="_blank" rel="noopener noreferrer" className="text-gray-400 hover:text-blue-500">
                                        <ExternalLink className="w-4 h-4" />
                                    </a>
                                </h4>
                                <p className="text-sm text-gray-500 dark:text-gray-400 mt-1 line-clamp-2">
                                    {project.description}
                                </p>
                            </div>
                            <div className="flex items-center gap-3 text-sm">
                                <div className="flex items-center gap-1 text-yellow-600 dark:text-yellow-500">
                                    <Star className="w-4 h-4 fill-current" />
                                    <span>{formatNumber(project.stars)}</span>
                                </div>
                                <div className="flex items-center gap-1 text-gray-500 dark:text-gray-400">
                                    <GitFork className="w-4 h-4" />
                                    <span>{formatNumber(project.forks)}</span>
                                </div>
                            </div>
                        </div>

                        {/* Comparison Tags */}
                        {project.comparison && (
                            <div className="mt-3 flex flex-wrap gap-2">
                                {project.comparison.map((point, i) => (
                                    <span key={i} className="px-2 py-1 bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300 text-xs rounded-full font-medium">
                                        {point}
                                    </span>
                                ))}
                            </div>
                        )}

                        {/* Topics */}
                        {project.topics && project.topics.length > 0 && (
                            <div className="mt-2 flex flex-wrap gap-1">
                                {project.topics.slice(0, 5).map((topic, i) => (
                                    <span key={i} className="text-xs text-gray-500 dark:text-gray-400 bg-gray-100 dark:bg-gray-800 px-1.5 py-0.5 rounded">
                                        #{topic}
                                    </span>
                                ))}
                            </div>
                        )}
                    </div>
                ))}
            </div>
        </CollapsibleCard>
    );
};

export default SimilarProjectsSection;
