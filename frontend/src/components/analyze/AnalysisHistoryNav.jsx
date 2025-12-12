import React from "react";
import { History, ChevronLeft, ChevronRight } from "lucide-react";

/**
 * 분석 히스토리 네비게이션 바 컴포넌트
 */
const AnalysisHistoryNav = ({
  analysisHistory,
  currentHistoryIndex,
  canGoBack,
  canGoForward,
  onGoBack,
  onGoForward,
  showCompareSelector,
  setShowCompareSelector,
  isComparing,
  selectedForCompare,
  onToggleCompareSelection,
  onCompareAnalysis,
  setSelectedForCompare,
  getUniqueRepositories,
  showSessionHistory,
  onToggleSessionHistory,
  sessionList,
  sessionId,
  onSwitchToSession,
}) => {
  if (analysisHistory.length <= 1) return null;

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-3 flex items-center justify-between">
      <div className="flex items-center gap-2 text-sm text-gray-600">
        <History className="w-4 h-4" />
        <span>분석 기록</span>
        <span className="bg-gray-100 px-2 py-0.5 rounded-full text-xs font-medium">
          {currentHistoryIndex + 1} / {analysisHistory.length}
        </span>
      </div>

      <div className="flex items-center gap-2">
        {/* 비교 분석 버튼 */}
        <div className="relative">
          <button
            onClick={() => setShowCompareSelector(!showCompareSelector)}
            disabled={isComparing || getUniqueRepositories().length < 2}
            className={`flex items-center gap-1 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              isComparing
                ? "bg-purple-100 text-purple-600"
                : getUniqueRepositories().length < 2
                ? "bg-gray-300 text-gray-500 cursor-not-allowed"
                : showCompareSelector
                ? "bg-purple-700 text-white"
                : "bg-purple-600 hover:bg-purple-700 text-white"
            }`}
            title="저장소 비교 분석"
          >
            {isComparing ? (
              <>
                <div className="w-3 h-3 border-2 border-purple-600 border-t-transparent rounded-full animate-spin"></div>
                비교 중...
              </>
            ) : (
              <>1:1 비교</>
            )}
          </button>

          {/* 비교 선택 패널 */}
          {showCompareSelector && (
            <div className="absolute right-0 top-full mt-2 w-72 bg-white rounded-xl shadow-xl border border-gray-200 z-50 overflow-hidden">
              <div className="p-3 bg-purple-50 border-b border-purple-100">
                <h4 className="font-semibold text-purple-800 text-sm">
                  비교할 저장소 선택
                </h4>
                <p className="text-xs text-purple-600 mt-0.5">
                  2개를 선택하세요 ({selectedForCompare.size}/2)
                </p>
              </div>
              <div className="max-h-48 overflow-y-auto">
                {getUniqueRepositories().map((item) => (
                  <label
                    key={item.key}
                    className={`flex items-center gap-3 px-3 py-2.5 cursor-pointer hover:bg-gray-50 transition-colors ${
                      selectedForCompare.has(item.key) ? "bg-purple-50" : ""
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={selectedForCompare.has(item.key)}
                      onChange={() => onToggleCompareSelection(item.key)}
                      disabled={
                        !selectedForCompare.has(item.key) &&
                        selectedForCompare.size >= 2
                      }
                      className="w-4 h-4 text-purple-600 rounded border-gray-300 focus:ring-purple-500"
                    />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-800 truncate">
                        {item.repo}
                      </p>
                      <p className="text-xs text-gray-500">{item.owner}</p>
                    </div>
                    <span
                      className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
                        item.healthScore >= 70
                          ? "bg-green-100 text-green-700"
                          : item.healthScore >= 40
                          ? "bg-yellow-100 text-yellow-700"
                          : "bg-red-100 text-red-700"
                      }`}
                    >
                      {item.healthScore}점
                    </span>
                  </label>
                ))}
              </div>
              <div className="p-2 bg-gray-50 border-t border-gray-200 flex gap-2">
                <button
                  onClick={() => {
                    setShowCompareSelector(false);
                    setSelectedForCompare(new Set());
                  }}
                  className="flex-1 px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-200 rounded-lg transition-colors"
                >
                  취소
                </button>
                <button
                  onClick={onCompareAnalysis}
                  disabled={selectedForCompare.size !== 2}
                  className={`flex-1 px-3 py-1.5 text-sm rounded-lg transition-colors ${
                    selectedForCompare.size === 2
                      ? "bg-purple-600 text-white hover:bg-purple-700"
                      : "bg-gray-300 text-gray-500 cursor-not-allowed"
                  }`}
                >
                  비교 시작
                </button>
              </div>
            </div>
          )}
        </div>

        <button
          onClick={onGoBack}
          disabled={!canGoBack}
          className={`flex items-center gap-1 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
            canGoBack
              ? "bg-gray-100 hover:bg-gray-200 text-gray-700"
              : "bg-gray-50 text-gray-300 cursor-not-allowed"
          }`}
        >
          <ChevronLeft className="w-4 h-4" />
          이전
        </button>

        <button
          onClick={onGoForward}
          disabled={!canGoForward}
          className={`flex items-center gap-1 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
            canGoForward
              ? "bg-gray-100 hover:bg-gray-200 text-gray-700"
              : "bg-gray-50 text-gray-300 cursor-not-allowed"
          }`}
        >
          다음
          <ChevronRight className="w-4 h-4" />
        </button>

        {/* 대화 기록 버튼 */}
        <div className="relative">
          <button
            onClick={onToggleSessionHistory}
            className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-sm font-medium bg-gray-100 hover:bg-gray-200 text-gray-700 transition-colors"
          >
            <History className="w-4 h-4" />
            대화 기록
          </button>
          {showSessionHistory && (
            <div className="absolute right-0 mt-2 w-80 bg-white rounded-xl shadow-2xl border border-gray-200 z-50 max-h-96 overflow-y-auto">
              <div className="p-3 border-b border-gray-200 bg-gradient-to-r from-purple-50 to-pink-50">
                <h3 className="text-sm font-semibold text-gray-800">
                  활성 세션 목록
                </h3>
                <p className="text-xs text-gray-600 mt-0.5">
                  현재 세션: {sessionId || "없음"}
                </p>
              </div>
              <div className="p-2">
                {sessionList.length === 0 ? (
                  <div className="text-center py-8 text-gray-500 text-sm">
                    활성 세션이 없습니다.
                  </div>
                ) : (
                  sessionList.map((session) => (
                    <button
                      key={session.session_id}
                      onClick={() => onSwitchToSession(session.session_id)}
                      className={`w-full text-left p-3 rounded-lg mb-2 transition-colors ${
                        session.session_id === sessionId
                          ? "bg-purple-100 border-2 border-purple-400"
                          : "bg-gray-50 hover:bg-gray-100 border-2 border-transparent"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-gray-800 truncate">
                            {session.repo_owner}/{session.repo_name}
                          </p>
                          <p className="text-xs text-gray-500 mt-0.5">
                            {session.turn_count}턴 대화
                          </p>
                          <p className="text-xs text-gray-400 mt-1">
                            {new Date(session.created_at).toLocaleString(
                              "ko-KR",
                              {
                                month: "short",
                                day: "numeric",
                                hour: "2-digit",
                                minute: "2-digit",
                              }
                            )}
                          </p>
                        </div>
                        {session.session_id === sessionId && (
                          <span className="text-xs font-semibold px-2 py-1 rounded-full bg-purple-600 text-white">
                            현재
                          </span>
                        )}
                      </div>
                    </button>
                  ))
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default AnalysisHistoryNav;
