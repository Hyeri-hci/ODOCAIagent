import { useState, useCallback } from "react";
import { analyzeRepository, createMilestone, sendReport } from "../lib/api";

// 분석 플로우 상태 관리 훅
export const useAnalysisFlow = () => {
  // 플로우 상태
  const [currentState, setCurrentState] = useState("idle"); // 'idle' | 'loading' | 'completed' | 'error'
  const [currentRepo, setCurrentRepo] = useState(null);
  const [analysisResult, setAnalysisResult] = useState(null);
  const [error, setError] = useState(null);
  const [isCreatingMilestone, setIsCreatingMilestone] = useState(false);
  const [isSendingReport, setIsSendingReport] = useState(false);
  const [notification, setNotification] = useState(null);

  // 알림 설정 함수
  const showNotification = useCallback((type, message) => {
    setNotification({ type, message });
    setTimeout(() => setNotification(null), 5000); // 5초 후 알림 제거
  }, []);

  // 리포지토리 분석 함수
  const startAnalysis = useCallback(
    async (repoUrl) => {
      setCurrentState("loading");
      setCurrentRepo(repoUrl);
      setAnalysisResult(null);
      setError(null);

      try {
        const result = await analyzeRepository(repoUrl);
        setAnalysisResult(result);
        setCurrentState("completed");
        showNotification("success", "리포지토리 분석이 완료되었습니다.");

        // 결과 섹션으로 스크롤 이동
        setTimeout(() => {
          document
            .getElementById("results")
            ?.scrollIntoView({ behavior: "smooth" });
        }, 100);

        return result;
      } catch (err) {
        console.error("Analysis error:", err);
        setError(err.message || "Unknown error");
        setCurrentState("error");
        showNotification("error", "리포지토리 분석 중 오류가 발생했습니다.");
        throw err;
      }
    },
    [showNotification]
  );

  // 마일스톤 생성 함수
  const createMilestoneForActions = useCallback(
    async (selectedActions, analysis) => {
      setIsCreatingMilestone(true);
      try {
        const result = await createMilestone(selectedActions, analysis);
        showNotification("success", "마일스톤이 성공적으로 생성되었습니다.");
        return result;
      } catch (err) {
        console.error("Milestone creation error:", err);
        showNotification("error", "마일스톤 생성 중 오류가 발생했습니다.");
        throw err;
      } finally {
        setIsCreatingMilestone(false);
      }
    },
    [showNotification]
  );

  // 리포트 전송 함수
  const sendAnalysisReport = useCallback(
    async (analysisData) => {
      setIsSendingReport(true);
      try {
        const reportSummary = `
        리포지토리 분석 리포트:
        - 분석 대상: ${currentRepo}
        - 종합 점수: ${analysisData.overall_score}
        - 발견된 위험: ${analysisData.risks?.length || 0}건
        - 권장 작업: ${analysisData.actions?.length || 0}건
      `;

        const actionIds = analysisData.actions.map((action) => action.id) || [];
        const result = await sendReport(reportSummary, actionIds);
        showNotification(
          "success",
          "카카오톡으로 리포트가 성공적으로 전송되었습니다."
        );
        return result;
      } catch (err) {
        console.error("Report sending error:", err);
        showNotification("error", "리포트 전송 중 오류가 발생했습니다.");
        throw err;
      } finally {
        setIsSendingReport(false);
      }
    },
    [currentRepo, showNotification]
  );

  // 상태 초기화
  const resetAnalysis = useCallback(() => {
    setCurrentState("idle");
    setCurrentRepo(null);
    setAnalysisResult(null);
    setError(null);
  }, []);

  return {
    // 상태
    currentState,
    currentRepo,
    analysisResult,
    error,
    isCreatingMilestone,
    isSendingReport,
    notification,

    // 계산된 값
    isLoading: currentState === "loading",
    isCompleted: currentState === "completed",
    hasResult: !!analysisResult,

    // 액션
    startAnalysis,
    createMilestoneForActions,
    sendAnalysisReport,
    resetAnalysis,
    showNotification,
  };
};

export default useAnalysisFlow;
