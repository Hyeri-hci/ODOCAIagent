import { useState, useRef } from "react";
import { sendChatMessageStreamV2 } from "../lib/api";

/**
 * SSE 스트리밍 관리 Hook
 *
 * @param {Object} params - 설정 파라미터
 * @returns {Object} 스트리밍 상태 및 관리 함수
 */
export const useAnalysisStream = ({
  parseGitHubUrl,
  transformApiResponse,
  setSessionId,
  setSuggestions,
  setAnalysisResult,
  setIsGeneratingPlan,
  onAnalysisUpdate,
}) => {
  const [streamingMessage, setStreamingMessage] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const streamCancelRef = useRef(null);

  const startStream = (
    userMessage,
    sessionId,
    analysisResult,
    addMessage,
    setIsTyping
  ) => {
    const repoUrl = analysisResult?.repositoryUrl;
    const { owner, repo } = parseGitHubUrl(repoUrl);

    if (!owner || !repo) {
      console.warn("저장소 정보가 없습니다. 일반 대화 모드로 진행합니다.");
    }

    setStreamingMessage("");
    setIsStreaming(true);

    streamCancelRef.current = sendChatMessageStreamV2(
      userMessage,
      sessionId,
      owner,
      repo,
      (eventType, data) => {
        switch (eventType) {
          case "start":
            console.log("스트리밍 시작:", data);
            if (data.session_id) {
              setSessionId(data.session_id);
            }
            break;

          case "processing":
            console.log("처리 중:", data.agent || data.step);
            break;

          case "answer": {
            setIsStreaming(false);
            setStreamingMessage("");

            if (data.session_id) {
              setSessionId(data.session_id);
            }

            const aiResponse = {
              id: `ai_${Date.now()}`,
              role: "assistant",
              content: data.answer || "응답을 받지 못했습니다.",
              timestamp: new Date(),
            };
            addMessage(aiResponse);
            setIsTyping(false);

            if (data.suggestions && data.suggestions.length > 0) {
              setSuggestions(data.suggestions);
            }

            if (data.context) {
              const { agent_result, target_agent } = data.context;

              if (target_agent === "diagnosis" && agent_result) {
                console.log("진단 결과 받음 (스트리밍):", agent_result);
                const { owner: resultOwner, repo: resultRepo } = parseGitHubUrl(
                  analysisResult?.repositoryUrl
                );
                const repoUrl =
                  analysisResult?.repositoryUrl ||
                  `https://github.com/${owner || resultOwner}/${
                    repo || resultRepo
                  }`;
                const updatedResult = transformApiResponse(
                  { analysis: agent_result },
                  repoUrl
                );

                setAnalysisResult((prev) => ({
                  ...prev,
                  ...updatedResult,
                  repositoryUrl: repoUrl,
                }));

                if (onAnalysisUpdate) {
                  onAnalysisUpdate(updatedResult);
                }
              }

              if (target_agent === "onboarding" && agent_result) {
                console.log("온보딩 플랜 생성됨 (스트리밍):", agent_result);
                setAnalysisResult((prev) => ({
                  ...prev,
                  onboardingPlan: agent_result,
                }));
                setIsGeneratingPlan(false);
              }

              if (data.context.agent_result_summary?.similar_projects) {
                setAnalysisResult((prev) => ({
                  ...prev,
                  similarProjects:
                    data.context.agent_result_summary.similar_projects,
                }));
              }
            }
            break;
          }

          case "done": {
            setIsStreaming(false);
            setStreamingMessage("");
            setIsTyping(false);
            break;
          }

          case "error": {
            setIsStreaming(false);
            setStreamingMessage("");

            const errorResponse = {
              id: `ai_${Date.now()}`,
              role: "assistant",
              content:
                "죄송합니다. 응답을 생성하는 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
              timestamp: new Date(),
            };
            addMessage(errorResponse);
            setIsTyping(false);
            console.error("Streaming error:", data.error);
            break;
          }

          default:
            console.log("알 수 없는 이벤트:", eventType, data);
        }
      }
    );
  };

  const cancelStream = () => {
    if (streamCancelRef.current) {
      streamCancelRef.current();
      streamCancelRef.current = null;
    }
  };

  return {
    streamingMessage,
    isStreaming,
    startStream,
    cancelStream,
    streamCancelRef,
  };
};
