import React from "react";
import { AlertTriangle, Shield, Clock } from "lucide-react";

// 보안 감지 목록 표시 컴포넌트
export const DetectedRisksList = ({ risks = [], className = "" }) => {
  if (!risks || risks.length === 0) {
    return (
      <div
        className={`bg-white/40 backdrop-blur-sm rounded-2xl shadow-lg overflow-hidden border border-white/60 ${className}`}
      >
        <div className="bg-gradient-to-r from-yellow-50 to-orange-50 px-6 py-4 border-b border-yellow-100">
          <h3 className="text-xl font-black text-gray-900 flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-[#F59E0B]" />
            Detected Risks
          </h3>
          <p className="text-sm text-gray-600 mt-1">0 issues found</p>
        </div>
        <div className="p-6">
          <p className="text-center text-gray-500 py-8">No risks detected</p>
        </div>
      </div>
    );
  }

  return (
    <div
      className={`bg-white/40 backdrop-blur-sm rounded-2xl shadow-lg overflow-hidden border border-white/60 ${className}`}
    >
      <div className="bg-gradient-to-r from-yellow-50 to-orange-50 px-6 py-4 border-b border-yellow-100">
        <h3 className="text-xl font-black text-gray-900 flex items-center gap-2">
          <AlertTriangle className="w-5 h-5 text-[#F59E0B]" />
          Detected Risks
        </h3>
        <p className="text-sm text-gray-600 mt-1">
          {risks.length} issue{risks.length > 1 ? "s" : ""} found
        </p>
      </div>

      <div className="p-6 space-y-3 max-h-96 overflow-y-auto">
        {risks.map((risk) => (
          <RiskItem key={risk.id} risk={risk} />
        ))}
      </div>
    </div>
  );
};

const RiskItem = ({ risk }) => {
  const severityConfig = getSeverityConfig(risk.severity);

  return (
    <div
      className={`rounded-xl p-4 border-l-4 ${severityConfig.containerClass}`}
    >
      <div className="flex items-start justify-between mb-2">
        <span
          className={`text-xs px-3 py-1 rounded-full font-bold ${severityConfig.badgeClass}`}
        >
          {risk.severity.toUpperCase()}
        </span>
        <span className="text-xs text-gray-500 flex items-center gap-1">
          <Clock className="w-3 h-3" />
          {risk.updatedAt || "2 days ago"}
        </span>
      </div>
      <p className="text-sm font-medium text-gray-900 mb-2">
        {risk.description}
      </p>
      <div className="text-xs text-gray-500">Type: {risk.type}</div>
    </div>
  );
};

const getSeverityConfig = (severity) => {
  const configs = {
    high: {
      containerClass: "border-red-500 bg-red-50",
      badgeClass: "bg-red-500 text-white",
    },
    medium: {
      containerClass: "border-yellow-500 bg-yellow-50",
      badgeClass: "bg-yellow-500 text-white",
    },
    low: {
      containerClass: "border-blue-500 bg-blue-50",
      badgeClass: "bg-blue-500 text-white",
    },
  };

  return configs[severity] || configs.medium;
};

export default DetectedRisksList;
