import { useState } from "react";

/**
 * 분석 히스토리 관리 Hook
 *
 * @param {Object} initialAnalysisResult - 초기 분석 결과
 * @returns {Object} 히스토리 상태 및 관리 함수
 */
export const useAnalysisHistory = (initialAnalysisResult) => {
  const [analysisHistory, setAnalysisHistory] = useState(() => {
    return initialAnalysisResult ? [initialAnalysisResult] : [];
  });
  const [currentHistoryIndex, setCurrentHistoryIndex] = useState(0);

  const canGoBack = currentHistoryIndex > 0;
  const canGoForward = currentHistoryIndex < analysisHistory.length - 1;

  const goToPreviousAnalysis = () => {
    if (canGoBack) {
      const newIndex = currentHistoryIndex - 1;
      setCurrentHistoryIndex(newIndex);
      return analysisHistory[newIndex];
    }
    return null;
  };

  const goToNextAnalysis = () => {
    if (canGoForward) {
      const newIndex = currentHistoryIndex + 1;
      setCurrentHistoryIndex(newIndex);
      return analysisHistory[newIndex];
    }
    return null;
  };

  const addToHistory = (newResult) => {
    setAnalysisHistory((prev) => {
      const newHistory = [...prev.slice(0, currentHistoryIndex + 1), newResult];
      return newHistory;
    });
    setCurrentHistoryIndex((prev) => prev + 1);
  };

  return {
    analysisHistory,
    currentHistoryIndex,
    canGoBack,
    canGoForward,
    goToPreviousAnalysis,
    goToNextAnalysis,
    addToHistory,
  };
};
