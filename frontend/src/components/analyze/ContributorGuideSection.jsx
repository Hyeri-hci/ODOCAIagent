import React, { useState } from "react";
import {
    BookOpen,
    CheckSquare,
    Users,
    GitPullRequest,
    FolderTree,
    ChevronDown,
    ChevronUp,
    ExternalLink,
    Clock,
    Target,
    Award,
    Heart,
} from "lucide-react";

/**
 * 기여자 가이드 섹션 컴포넌트
 * 첫 기여 가이드, 체크리스트, 커뮤니티 분석 등을 표시
 */
const ContributorGuideSection = ({
    contributorGuide,
    firstContributionGuide,
    contributionChecklist,
    communityAnalysis,
    issueMatching,
    structureVisualization,
}) => {
    const [expandedSections, setExpandedSections] = useState({
        guide: true,
        checklist: false,
        community: false,
        issues: false,
        structure: false,
    });

    const toggleSection = (section) => {
        setExpandedSections((prev) => ({ ...prev, [section]: !prev[section] }));
    };

    // 데이터가 없으면 렌더링하지 않음
    if (
        !contributorGuide &&
        !firstContributionGuide &&
        !contributionChecklist &&
        !communityAnalysis
    ) {
        return null;
    }

    return (
        <div className="space-y-4">
            {/* 첫 기여 가이드 */}
            {firstContributionGuide && (
                <CollapsibleCard
                    title="첫 기여 가이드"
                    icon={<BookOpen className="w-5 h-5 text-blue-500" />}
                    subtitle={`${firstContributionGuide.steps?.length || 12}단계 가이드`}
                    isExpanded={expandedSections.guide}
                    onToggle={() => toggleSection("guide")}
                >
                    <FirstContributionGuide guide={firstContributionGuide} />
                </CollapsibleCard>
            )}

            {/* 기여 체크리스트 */}
            {contributionChecklist && (
                <CollapsibleCard
                    title="기여 체크리스트"
                    icon={<CheckSquare className="w-5 h-5 text-green-500" />}
                    subtitle={`${contributionChecklist.items?.length || 0}개 항목`}
                    isExpanded={expandedSections.checklist}
                    onToggle={() => toggleSection("checklist")}
                >
                    <ContributionChecklist checklist={contributionChecklist} />
                </CollapsibleCard>
            )}

            {/* 커뮤니티 활동 분석 */}
            {communityAnalysis && (
                <CollapsibleCard
                    title="커뮤니티 활동 분석"
                    icon={<Users className="w-5 h-5 text-purple-500" />}
                    subtitle={`친화도 ${communityAnalysis.friendliness_score || 0}점`}
                    isExpanded={expandedSections.community}
                    onToggle={() => toggleSection("community")}
                >
                    <CommunityAnalysis analysis={communityAnalysis} />
                </CollapsibleCard>
            )}

            {/* 이슈 매칭 */}
            {issueMatching && issueMatching.length > 0 && (
                <CollapsibleCard
                    title="추천 이슈"
                    icon={<Target className="w-5 h-5 text-orange-500" />}
                    subtitle={`${issueMatching.length}개 매칭`}
                    isExpanded={expandedSections.issues}
                    onToggle={() => toggleSection("issues")}
                >
                    <IssueMatchingList issues={issueMatching} />
                </CollapsibleCard>
            )}

            {/* 코드 구조 시각화 */}
            {structureVisualization && (
                <CollapsibleCard
                    title="코드 구조"
                    icon={<FolderTree className="w-5 h-5 text-cyan-500" />}
                    isExpanded={expandedSections.structure}
                    onToggle={() => toggleSection("structure")}
                >
                    <StructureVisualization visualization={structureVisualization} />
                </CollapsibleCard>
            )}
        </div>
    );
};

// 접을 수 있는 카드 컴포넌트
const CollapsibleCard = ({
    title,
    icon,
    subtitle,
    isExpanded,
    onToggle,
    children,
}) => (
    <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
        <button
            onClick={onToggle}
            className="w-full px-6 py-4 flex items-center justify-between hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
        >
            <div className="flex items-center gap-3">
                {icon}
                <div className="text-left">
                    <h3 className="font-semibold text-gray-900 dark:text-white">
                        {title}
                    </h3>
                    {subtitle && (
                        <p className="text-sm text-gray-500 dark:text-gray-400">
                            {subtitle}
                        </p>
                    )}
                </div>
            </div>
            {isExpanded ? (
                <ChevronUp className="w-5 h-5 text-gray-400" />
            ) : (
                <ChevronDown className="w-5 h-5 text-gray-400" />
            )}
        </button>
        {isExpanded && (
            <div className="px-6 pb-6 border-t border-gray-100 dark:border-gray-700">
                <div className="pt-4">{children}</div>
            </div>
        )}
    </div>
);

// 첫 기여 가이드 컴포넌트
const FirstContributionGuide = ({ guide }) => {
    const steps = guide.steps || [];

    return (
        <div className="space-y-4">
            <ol className="relative border-l border-gray-200 dark:border-gray-700 ml-3">
                {steps.map((step, index) => (
                    <li key={index} className="mb-6 ml-6">
                        <span className="absolute flex items-center justify-center w-8 h-8 bg-blue-100 rounded-full -left-4 ring-4 ring-white dark:ring-gray-800 dark:bg-blue-900">
                            <span className="text-sm font-bold text-blue-800 dark:text-blue-200">
                                {index + 1}
                            </span>
                        </span>
                        <h4 className="font-semibold text-gray-900 dark:text-white">
                            {step.title}
                        </h4>
                        <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                            {step.description}
                        </p>
                        {step.command && (
                            <code className="block mt-2 px-3 py-2 bg-gray-100 dark:bg-gray-700 rounded text-sm font-mono">
                                {step.command}
                            </code>
                        )}
                        {/* tip(단일 문자열) 또는 tips(배열) 처리 */}
                        {step.tip && (
                            <p className="mt-2 text-xs text-gray-500 dark:text-gray-400 flex items-start gap-1">
                                <span className="text-blue-500">TIP:</span>
                                {step.tip}
                            </p>
                        )}
                        {step.tips && step.tips.length > 0 && (
                            <ul className="mt-2 space-y-1">
                                {step.tips.map((tip, tipIdx) => (
                                    <li
                                        key={tipIdx}
                                        className="text-xs text-gray-500 dark:text-gray-400 flex items-start gap-1"
                                    >
                                        <span className="text-blue-500">•</span>
                                        {tip}
                                    </li>
                                ))}
                            </ul>
                        )}
                    </li>
                ))}
            </ol>
        </div>
    );
};

// 기여 체크리스트 컴포넌트
const ContributionChecklist = ({ checklist }) => {
    const [checked, setChecked] = useState({});

    const handleCheck = (itemId) => {
        setChecked((prev) => ({ ...prev, [itemId]: !prev[itemId] }));
    };

    const items = checklist.items || [];
    const completedCount = Object.values(checked).filter(Boolean).length;

    return (
        <div className="space-y-4">
            {/* 진행률 바 */}
            <div className="flex items-center gap-3">
                <div className="flex-1 h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                    <div
                        className="h-full bg-green-500 transition-all duration-300"
                        style={{
                            width: `${items.length > 0 ? (completedCount / items.length) * 100 : 0}%`,
                        }}
                    />
                </div>
                <span className="text-sm font-medium text-gray-600 dark:text-gray-400">
                    {completedCount}/{items.length}
                </span>
            </div>

            {/* 체크리스트 항목 */}
            <div className="space-y-2">
                {items.map((item) => (
                    <label
                        key={item.id}
                        className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${checked[item.id]
                            ? "bg-green-50 border-green-200 dark:bg-green-900/20 dark:border-green-800"
                            : "bg-gray-50 border-gray-200 dark:bg-gray-700/50 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-700"
                            }`}
                    >
                        <input
                            type="checkbox"
                            checked={checked[item.id] || false}
                            onChange={() => handleCheck(item.id)}
                            className="mt-1 w-4 h-4 text-green-600 rounded border-gray-300 focus:ring-green-500"
                        />
                        <div className="flex-1">
                            <div className="flex items-center gap-2">
                                <span
                                    className={`font-medium ${checked[item.id]
                                        ? "text-green-700 dark:text-green-300 line-through"
                                        : "text-gray-900 dark:text-white"
                                        }`}
                                >
                                    {item.title}
                                </span>
                                <PriorityBadge priority={item.priority} />
                            </div>
                            <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
                                {item.description}
                            </p>
                        </div>
                    </label>
                ))}
            </div>
        </div>
    );
};

// 우선순위 배지
const PriorityBadge = ({ priority }) => {
    const colors = {
        high: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
        medium:
            "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400",
        low: "bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400",
    };

    return (
        <span
            className={`text-xs px-2 py-0.5 rounded-full ${colors[priority] || colors.low}`}
        >
            {priority === "high" ? "필수" : priority === "medium" ? "권장" : "선택"}
        </span>
    );
};

// 커뮤니티 분석 컴포넌트
const CommunityAnalysis = ({ analysis }) => {
    const friendlinessScore = analysis.friendliness_score || 0;
    const factors = analysis.friendliness_factors || [];
    const recommendations = analysis.recommendations || [];

    const getScoreColor = (score) => {
        if (score >= 70) return "text-green-600";
        if (score >= 50) return "text-yellow-600";
        return "text-red-600";
    };

    const getLevelText = (level) => {
        const levels = {
            very_friendly: "매우 친화적",
            friendly: "친화적",
            moderate: "보통",
            challenging: "도전적",
        };
        return levels[level] || "알 수 없음";
    };

    return (
        <div className="space-y-6">
            {/* 친화도 점수 */}
            <div className="flex items-center gap-4">
                <div className="w-20 h-20 relative">
                    <svg className="w-20 h-20 transform -rotate-90">
                        <circle
                            cx="40"
                            cy="40"
                            r="36"
                            stroke="currentColor"
                            strokeWidth="8"
                            fill="transparent"
                            className="text-gray-200 dark:text-gray-700"
                        />
                        <circle
                            cx="40"
                            cy="40"
                            r="36"
                            stroke="currentColor"
                            strokeWidth="8"
                            fill="transparent"
                            strokeDasharray={`${(friendlinessScore / 100) * 226.2} 226.2`}
                            className={getScoreColor(friendlinessScore)}
                        />
                    </svg>
                    <div className="absolute inset-0 flex items-center justify-center">
                        <span
                            className={`text-xl font-bold ${getScoreColor(friendlinessScore)}`}
                        >
                            {friendlinessScore}
                        </span>
                    </div>
                </div>
                <div>
                    <h4 className="font-semibold text-gray-900 dark:text-white">
                        기여 친화도
                    </h4>
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                        {getLevelText(analysis.friendliness_level)}
                    </p>
                </div>
            </div>

            {/* 세부 요소 */}
            {factors.length > 0 && (
                <div className="space-y-2">
                    <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">
                        평가 요소
                    </h4>
                    <div className="grid grid-cols-2 gap-2">
                        {factors.map((factor, idx) => (
                            <div
                                key={idx}
                                className="p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg"
                            >
                                <div className="text-xs text-gray-500 dark:text-gray-400">
                                    {factor.name}
                                </div>
                                <div className="font-medium text-gray-900 dark:text-white">
                                    {factor.value}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* 권장사항 */}
            {recommendations.length > 0 && (
                <div className="space-y-2">
                    <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">
                        권장사항
                    </h4>
                    <ul className="space-y-1">
                        {recommendations.map((rec, idx) => (
                            <li
                                key={idx}
                                className="flex items-start gap-2 text-sm text-gray-600 dark:text-gray-400"
                            >
                                <Heart className="w-4 h-4 text-pink-500 mt-0.5 flex-shrink-0" />
                                {rec}
                            </li>
                        ))}
                    </ul>
                </div>
            )}
        </div>
    );
};

// 이슈 매칭 리스트 컴포넌트
const IssueMatchingList = ({ issues }) => {
    return (
        <div className="space-y-3">
            {issues.slice(0, 5).map((issue, idx) => (
                <a
                    key={issue.number || idx}
                    href={issue.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="block p-4 bg-gray-50 dark:bg-gray-700/50 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                >
                    <div className="flex items-start justify-between gap-2">
                        <div className="flex-1">
                            <div className="flex items-center gap-2">
                                <span className="text-sm font-medium text-gray-900 dark:text-white">
                                    #{issue.number}
                                </span>
                                <span className="text-sm text-gray-600 dark:text-gray-300 line-clamp-1">
                                    {issue.title}
                                </span>
                            </div>
                            <div className="flex items-center gap-3 mt-1">
                                <DifficultyBadge level={issue.difficulty?.level} />
                                <span className="text-xs text-gray-500 dark:text-gray-400">
                                    <Clock className="w-3 h-3 inline mr-1" />
                                    {issue.difficulty?.estimated_time?.text || "예상 시간 없음"}
                                </span>
                            </div>
                            {issue.match_reasons && issue.match_reasons.length > 0 && (
                                <div className="mt-2 flex flex-wrap gap-1">
                                    {issue.match_reasons.slice(0, 2).map((reason, rIdx) => (
                                        <span
                                            key={rIdx}
                                            className="text-xs px-2 py-0.5 bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400 rounded-full"
                                        >
                                            {reason}
                                        </span>
                                    ))}
                                </div>
                            )}
                        </div>
                        <div className="flex items-center gap-2">
                            <span className="text-lg font-bold text-blue-600 dark:text-blue-400">
                                {issue.match_score || 0}
                            </span>
                            <ExternalLink className="w-4 h-4 text-gray-400" />
                        </div>
                    </div>
                </a>
            ))}
        </div>
    );
};

// 난이도 배지
const DifficultyBadge = ({ level }) => {
    const config = {
        easy: {
            text: "쉬움",
            color: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
        },
        medium: {
            text: "보통",
            color:
                "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400",
        },
        hard: {
            text: "어려움",
            color: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
        },
    };

    const { text, color } = config[level] || config.medium;

    return (
        <span className={`text-xs px-2 py-0.5 rounded-full ${color}`}>{text}</span>
    );
};

// 코드 구조 시각화 컴포넌트
const StructureVisualization = ({ visualization }) => {
    const { ascii_tree, analysis } = visualization || {};
    const techStack = analysis?.detected_tech_stack || [];
    const keyFolders = analysis?.key_folders || [];

    return (
        <div className="space-y-4">
            {/* 기술 스택 */}
            {techStack.length > 0 && (
                <div className="flex flex-wrap gap-2">
                    {techStack.map((tech, idx) => (
                        <span
                            key={idx}
                            className="px-3 py-1 bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400 rounded-full text-sm font-medium"
                        >
                            {tech}
                        </span>
                    ))}
                </div>
            )}

            {/* 주요 폴더 */}
            {keyFolders.length > 0 && (
                <div className="grid grid-cols-2 gap-2">
                    {keyFolders.slice(0, 6).map((folder, idx) => (
                        <div
                            key={idx}
                            className="p-2 bg-gray-50 dark:bg-gray-700/50 rounded flex items-center gap-2"
                        >
                            <FolderTree className="w-4 h-4 text-cyan-500" />
                            <div>
                                <code className="text-sm font-mono text-gray-900 dark:text-white">
                                    {folder.name}
                                </code>
                                <span className="text-xs text-gray-500 dark:text-gray-400 ml-1">
                                    {folder.description}
                                </span>
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {/* ASCII 트리 */}
            {ascii_tree && (
                <pre className="p-4 bg-gray-900 text-green-400 rounded-lg overflow-x-auto text-xs font-mono max-h-64">
                    {ascii_tree}
                </pre>
            )}
        </div>
    );
};

export default ContributorGuideSection;
