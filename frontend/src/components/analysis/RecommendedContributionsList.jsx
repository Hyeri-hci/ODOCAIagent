import React, { useState } from "react";
import { CheckCircle, Clock } from "lucide-react";

// 기여 작업 추천 목록 컴포넌트
export const RecommendedContributionsList = ({
  actions = [],
  onSelectionChange,
  className = "",
}) => {
  const [selectedActions, setSelectedActions] = useState([]);

  const toggleAction = (actionId) => {
    const newSelection = selectedActions.includes(actionId)
      ? selectedActions.filter((id) => id !== actionId)
      : [...selectedActions, actionId];

    setSelectedActions(newSelection);
    onSelectionChange?.(newSelection);
  };

  if (!actions || actions.length === 0) {
    return (
      <div
        className={`bg-white/40 backdrop-blur-sm rounded-2xl shadow-lg overflow-hidden border border-white/60 ${className}`}
      >
        <div className="bg-gradient-to-r from-green-50 to-emerald-50 px-6 py-4 border-b border-green-100">
          <h3 className="text-xl font-black text-gray-900 flex items-center gap-2">
            <CheckCircle className="w-5 h-5 text-[#10B981]" />
            Recommended Contributions
          </h3>
          <p className="text-sm text-gray-600 mt-1">0 tasks available</p>
        </div>
        <div className="p-6">
          <p className="text-center text-gray-500 py-8">
            No recommendations available
          </p>
        </div>
      </div>
    );
  }

  return (
    <div
      className={`bg-white/40 backdrop-blur-sm rounded-2xl shadow-lg overflow-hidden border border-white/60 ${className}`}
    >
      <div className="bg-gradient-to-r from-green-50 to-emerald-50 px-6 py-4 border-b border-green-100">
        <h3 className="text-xl font-black text-gray-900 flex items-center gap-2">
          <CheckCircle className="w-5 h-5 text-[#10B981]" />
          Recommended Contributions
        </h3>
        <p className="text-sm text-gray-600 mt-1">
          {actions.length} task{actions.length > 1 ? "s" : ""} available
        </p>
      </div>

      <div className="p-6 space-y-3 max-h-96 overflow-y-auto">
        {actions.map((action) => (
          <ContributionItem
            key={action.id}
            action={action}
            isSelected={selectedActions.includes(action.id)}
            onToggle={() => toggleAction(action.id)}
          />
        ))}
      </div>

      {selectedActions.length > 0 && (
        <div className="bg-[#2563EB] px-6 py-3 text-center">
          <p className="text-white font-bold text-sm">
            ✓ {selectedActions.length} task
            {selectedActions.length > 1 ? "s" : ""} selected
          </p>
        </div>
      )}
    </div>
  );
};

const ContributionItem = ({ action, isSelected, onToggle }) => {
  const priorityConfig = getPriorityConfig(action.priority);

  return (
    <div
      className={`
        rounded-xl p-4 border-l-4 transition-all cursor-pointer
        ${priorityConfig.containerClass}
        ${isSelected ? "ring-2 ring-[#2563EB]" : ""}
      `}
      onClick={onToggle}
    >
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={isSelected}
            onChange={onToggle}
            onClick={(e) => e.stopPropagation()}
            className="w-4 h-4 rounded text-[#2563EB] focus:ring-[#2563EB]"
          />
          <span
            className={`text-xs px-3 py-1 rounded-full font-bold ${priorityConfig.badgeClass}`}
          >
            {action.priority.toUpperCase()}
          </span>
        </div>
        <span className="text-xs text-gray-500 flex items-center gap-1">
          <Clock className="w-3 h-3" />
          {action.duration || "1-2 hours"}
        </span>
      </div>
      <h4 className="text-sm font-bold text-gray-900 mb-1">{action.title}</h4>
      <p className="text-xs text-gray-600">{action.description}</p>
    </div>
  );
};

const getPriorityConfig = (priority) => {
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
      containerClass: "border-green-500 bg-green-50",
      badgeClass: "bg-green-500 text-white",
    },
  };

  return configs[priority] || configs.medium;
};

export default RecommendedContributionsList;
