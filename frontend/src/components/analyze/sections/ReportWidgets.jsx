
import React from "react";
import { ChevronDown, ChevronUp, Info, HelpCircle, Activity, CheckCircle } from "lucide-react";

// === 공통 UI 컴포넌트 ===

export const CollapsibleCard = ({
    title,
    children,
    isExpanded,
    onToggle,
    guideKey,
    onOpenGuide,
}) => (
    <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700 overflow-hidden mb-4 transition-all duration-300">
        <div
            className="px-6 py-4 flex items-center justify-between cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
            onClick={onToggle}
        >
            <div className="flex items-center gap-2">
                <h3 className="tex-lg font-bold text-gray-900 dark:text-gray-100">
                    {title}
                </h3>
                {guideKey && (
                    <button
                        onClick={(e) => {
                            e.stopPropagation();
                            onOpenGuide(guideKey);
                        }}
                        className="text-gray-400 hover:text-blue-500 transition-colors p-1 rounded-full hover:bg-blue-50 dark:hover:bg-blue-900/30"
                        title="가이드 보기"
                    >
                        <HelpCircle className="w-4 h-4" />
                    </button>
                )}
            </div>
            {isExpanded ? (
                <ChevronUp className="w-5 h-5 text-gray-400" />
            ) : (
                <ChevronDown className="w-5 h-5 text-gray-400" />
            )}
        </div>
        {isExpanded && (
            <div className="px-6 pb-6 pt-2 border-t border-gray-100 dark:border-gray-700 animate-fadeIn">
                {children}
            </div>
        )}
    </div>
);

export const ScoreCard = ({ score, statusConfig }) => {
    return (
        <div className="bg-gray-900 dark:bg-black rounded-2xl p-6 text-white shadow-xl relative overflow-hidden h-full flex flex-col justify-between">
            {/* Background Effects */}
            <div className="absolute top-0 right-0 w-32 h-32 bg-white/5 rounded-full -mr-16 -mt-16 blur-3xl"></div>
            <div className="absolute bottom-0 left-0 w-24 h-24 bg-blue-500/10 rounded-full -ml-12 -mb-12 blur-2xl"></div>

            {/* Header */}
            <div className="relative z-10 flex items-start justify-between mb-6">
                <div>
                    <div className="flex items-center gap-2 mb-1">
                        <div className="p-1.5 bg-white/10 rounded-lg">
                            <Activity className="w-4 h-4 text-white" />
                        </div>
                        <h3 className="text-lg font-bold text-white">Health Score</h3>
                    </div>
                    <p className="text-xs text-gray-400 font-medium ml-1">프로젝트 분석</p>
                </div>
            </div>

            {/* Score Display (Center) */}
            <div className="relative z-10 text-center py-4">
                <div className="flex items-end justify-center gap-2 mb-2">
                    <span className="text-6xl font-black tracking-tighter text-white">
                        {score}
                    </span>
                    <span className="text-xl text-gray-400 font-bold mb-2">
                        / 100
                    </span>
                </div>
                <div className="text-sm text-gray-400 font-medium">
                    종합 점수
                </div>

                {/* Progress Bar under score */}
                <div className="mt-4 w-full bg-gray-800 rounded-full h-1.5 overflow-hidden">
                    <div
                        className="h-full bg-gradient-to-r from-yellow-400 to-orange-500 rounded-full"
                        style={{ width: `${score}%` }}
                    />
                </div>
            </div>

            {/* Status Badge (Bottom) */}
            <div className="relative z-10 mt-6">
                <div className={`w-full py-3 rounded-xl flex items-center justify-center gap-2 font-bold text-sm bg-yellow-100/10 text-yellow-400 border border-yellow-400/30`}>
                    {statusConfig?.icon || <CheckCircle className="w-4 h-4" />}
                    <span>{statusConfig?.label || "Good"}</span>
                </div>
            </div>
        </div>
    );
};

export const StatCard = ({
    icon: Icon,
    value,
    label,
    borderColor = "border-gray-200",
    iconColor = "text-gray-500",
}) => (
    <div
        className={`bg-white dark:bg-gray-800 p-4 rounded-xl border-2 ${borderColor} shadow-sm hover:shadow-md transition-all duration-300 group`}
    >
        <div className="flex flex-col items-center text-center">
            <div
                className={`mb-2 p-2 rounded-lg bg-gray-50 dark:bg-gray-700 group-hover:scale-110 transition-transform ${iconColor}`}
            >
                <Icon className="w-5 h-5" />
            </div>
            <div className="text-xl font-bold text-gray-900 dark:text-white mb-1">
                {value}
            </div>
            <div className="text-xs text-gray-500 font-medium uppercase tracking-wide">
                {label}
            </div>
        </div>
    </div>
);

export const MetricBar = ({ label, value, color = "blue" }) => {
    const getColorClass = (c) => {
        const colors = {
            blue: "bg-blue-500",
            green: "bg-green-500",
            purple: "bg-purple-500",
            yellow: "bg-yellow-500",
            red: "bg-red-500",
        };
        return colors[c] || colors.blue;
    };

    return (
        <div className="group">
            <div className="flex justify-between text-sm mb-1.5 font-medium">
                <span className="text-gray-600 dark:text-gray-300">{label}</span>
                <span className="text-gray-900 dark:text-white font-bold">{value}%</span>
            </div>
            <div className="w-full bg-gray-100 dark:bg-gray-700 rounded-full h-2.5 overflow-hidden">
                <div
                    className={`${getColorClass(
                        color
                    )} h-2.5 rounded-full transition-all duration-1000 ease-out group-hover:scale-x-[1.02] origin-left`}
                    style={{ width: `${value}%` }}
                ></div>
            </div>
        </div>
    );
};

export const RiskItem = ({ risk }) => {
    let colorClass = "bg-gray-50 border-gray-200 text-gray-600";
    let Icon = Info;

    if (risk.severity === "high" || risk.severity === "critical") {
        colorClass = "bg-red-50 border-red-200 text-red-700 dark:bg-red-900/20 dark:border-red-800 dark:text-red-300";
    } else if (risk.severity === "medium") {
        colorClass = "bg-yellow-50 border-yellow-200 text-yellow-700 dark:bg-yellow-900/20 dark:border-yellow-800 dark:text-yellow-300";
    }

    return (
        <div className={`p-4 rounded-lg border ${colorClass} flex items-start gap-3`}>
            <Icon className="w-5 h-5 mt-0.5 shrink-0" />
            <div>
                <h4 className="font-bold text-sm mb-1">{risk.category} Risk</h4>
                <p className="text-sm opacity-90">{risk.description}</p>
                {risk.mitigation && (
                    <div className="mt-2 text-xs font-medium bg-white/50 dark:bg-black/20 p-2 rounded">
                        💡 {risk.mitigation}
                    </div>
                )}
            </div>
        </div>
    )
}
