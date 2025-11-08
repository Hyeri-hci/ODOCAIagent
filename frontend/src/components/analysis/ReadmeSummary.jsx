import React, { useState } from "react";
import { FileText, ChevronDown, ChevronUp } from "lucide-react";

// README 요약을 표시하는 컴포넌트
export const ReadmeSummary = ({ content, maxLength = 300, className = "" }) => {
  const [isExpanded, setIsExpanded] = useState(false);

  if (!content) return null;

  const shouldTruncate = content.length > maxLength;
  const displayContent =
    !shouldTruncate || isExpanded
      ? content
      : content.slice(0, maxLength) + "...";

  return (
    <div
      className={`bg-white/40 backdrop-blur-sm rounded-2xl shadow-lg p-6 border border-white/60 ${className}`}
    >
      <h3 className="font-bold text-gray-900 mb-3 flex items-center gap-2 text-lg">
        <FileText className="w-5 h-5 text-indigo-600" />
        README Summary
      </h3>

      <div className="text-sm text-gray-700 leading-relaxed mb-4">
        {displayContent}
      </div>

      {shouldTruncate && (
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="inline-flex items-center gap-2 text-indigo-600 hover:text-indigo-800 font-semibold text-sm transition-colors"
        >
          {isExpanded ? (
            <>
              <ChevronUp className="w-4 h-4" />
              간략히 보기
            </>
          ) : (
            <>
              <ChevronDown className="w-4 h-4" />
              더보기
            </>
          )}
        </button>
      )}
    </div>
  );
};

export default ReadmeSummary;
