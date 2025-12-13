
import React from "react";
import { Shield, Lock, AlertTriangle, CheckCircle, AlertCircle } from "lucide-react";
import { CollapsibleCard } from "./ReportWidgets";

const SecuritySection = ({
    analysisResult,
    expanded,
    onToggle,
    onOpenGuide,
}) => {
    const { security, securityRequested } = analysisResult || {};

    // 데이터 유효성
    if (!security && !securityRequested) return null;

    // 로딩 상태 처리 등은 부모에서 처리하거나 여기서 처리 가능
    // security가 없으면(로딩 전) null 리턴 (analysisResult가 있을 때만 렌더링되므로)

    const vulnerabilities = security?.vulnerabilities || [];
    const hasVulnerabilities = vulnerabilities.length > 0;

    return (
        <CollapsibleCard
            title="보안 분석"
            isExpanded={expanded}
            onToggle={onToggle}
            guideKey="security"
            onOpenGuide={onOpenGuide}
        >
            <div className="space-y-4">
                {/* 1. Main Stats Grid (Score, Grade, Total Vulns) */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {/* Security Score */}
                    <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-5 flex flex-col items-center justify-center shadow-sm">
                        <div className="text-4xl font-black text-gray-900 dark:text-white mb-1">
                            {security?.score || security?.security_score || "0"}
                        </div>
                        <div className="text-sm text-gray-500 font-medium">Security Score</div>
                    </div>

                    {/* Grade */}
                    <div className="bg-green-50 dark:bg-green-900/20 border border-green-100 dark:border-green-800 rounded-xl p-5 flex flex-col items-center justify-center shadow-sm">
                        <div className="text-4xl font-black text-green-600 dark:text-green-400 mb-1">
                            {security?.grade || "N/A"}
                        </div>
                        <div className="text-sm text-gray-600 dark:text-gray-400 font-medium">Grade</div>
                    </div>

                    {/* Total Vulnerabilities */}
                    <div className="bg-red-50 dark:bg-red-900/20 border border-red-100 dark:border-red-800 rounded-xl p-5 flex flex-col items-center justify-center shadow-sm">
                        <div className="text-4xl font-black text-red-600 dark:text-red-400 mb-1">
                            {vulnerabilities.length || security?.vulnerability_count || 0}
                        </div>
                        <div className="text-sm text-gray-600 dark:text-gray-400 font-medium">취약점</div>
                    </div>
                </div>

                {/* 2. Severity Breakdown Grid */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    <SeverityCard
                        label="Critical"
                        count={vulnerabilities.filter(v => v.severity?.toLowerCase() === 'critical').length}
                        color="text-red-600"
                        bgColor="bg-red-50 border-red-100 dark:bg-red-900/10 dark:border-red-900/30"
                    />
                    <SeverityCard
                        label="High"
                        count={vulnerabilities.filter(v => v.severity?.toLowerCase() === 'high').length}
                        color="text-orange-600"
                        bgColor="bg-orange-50 border-orange-100 dark:bg-orange-900/10 dark:border-orange-900/30"
                    />
                    <SeverityCard
                        label="Medium"
                        count={vulnerabilities.filter(v => v.severity?.toLowerCase() === 'medium').length}
                        color="text-yellow-600"
                        bgColor="bg-yellow-50 border-yellow-100 dark:bg-yellow-900/10 dark:border-yellow-900/30"
                    />
                    <SeverityCard
                        label="Low"
                        count={vulnerabilities.filter(v => v.severity?.toLowerCase() === 'low').length}
                        color="text-blue-600"
                        bgColor="bg-blue-50 border-blue-100 dark:bg-blue-900/10 dark:border-blue-900/30"
                    />
                </div>

                {/* 3. Status Banner */}
                <div className={`p-4 rounded-lg flex items-center justify-center text-center font-bold ${hasVulnerabilities
                    ? "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300"
                    : "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300"
                    }`}>
                    {hasVulnerabilities ? "취약점이 발견되었습니다. 조치가 필요합니다." : "취약점이 발견되지 않았습니다!"}
                </div>

                {/* 4. Detailed List (only if vulns exist) */}
                {hasVulnerabilities && (
                    <div className="mt-4 space-y-3">
                        {vulnerabilities.map((vuln, idx) => (
                            <div key={idx} className="p-4 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl hover:shadow-md transition-all">
                                <div className="flex items-center gap-2 mb-2">
                                    <span className={`px-2 py-0.5 rounded text-xs font-bold uppercase ${vuln.severity === 'critical' ? 'bg-red-100 text-red-700' :
                                        vuln.severity === 'high' ? 'bg-orange-100 text-orange-700' :
                                            vuln.severity === 'medium' ? 'bg-yellow-100 text-yellow-700' :
                                                'bg-blue-100 text-blue-700'
                                        }`}>
                                        {vuln.severity}
                                    </span>
                                    <h4 className="font-bold text-gray-900 dark:text-white">{vuln.name || "Unknown Vulnerability"}</h4>
                                </div>
                                <p className="text-sm text-gray-600 dark:text-gray-300 mb-3">{vuln.description}</p>
                                {vuln.remediation && (
                                    <div className="bg-gray-50 dark:bg-gray-700/50 p-3 rounded-lg text-sm">
                                        <span className="font-bold text-gray-700 dark:text-gray-300 mr-2">💡 해결 방법:</span>
                                        <span className="text-gray-600 dark:text-gray-400">{vuln.remediation}</span>
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </CollapsibleCard>
    );
};

const SeverityCard = ({ label, count, color, bgColor }) => (
    <div className={`${bgColor} border rounded-xl p-4 flex flex-col items-center justify-center`}>
        <div className={`text-2xl font-bold mb-1 ${color}`}>
            {count}
        </div>
        <div className="text-xs text-gray-500 font-medium">
            {label}
        </div>
    </div>
);

export default SecuritySection;
