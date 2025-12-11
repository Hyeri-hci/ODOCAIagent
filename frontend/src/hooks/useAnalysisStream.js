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
  // LangGraph 노드 진행률 상태
  const [nodeProgress, setNodeProgress] = useState(0);
  const [progressMessage, setProgressMessage] = useState("");
  const [currentNode, setCurrentNode] = useState("");
  const streamCancelRef = useRef(null);

  const startStream = (
    userMessage,
    sessionId,
    analysisResult,
    addMessage,
    setIsTyping,
    sessionRepo = null // 세션에 저장된 저장소 정보 (fallback용)
  ) => {
    const repoUrl = analysisResult?.repositoryUrl;
    let { owner, repo } = parseGitHubUrl(repoUrl);

    // analysisResult에서 추출 실패 시, sessionRepo에서 복원 시도
    if ((!owner || !repo) && sessionRepo) {
      owner = sessionRepo.owner;
      repo = sessionRepo.repo;
      console.log("[Stream] Using sessionRepo fallback:", owner, repo);
    }

    // 그래도 없으면 메시지에서 추출 시도
    if (!owner || !repo) {
      const urlInMessage = userMessage.match(
        /(?:https?:\/\/)?(?:www\.)?github\.com\/([\w-]+)\/([\w.-]+)/i
      );
      if (urlInMessage) {
        owner = urlInMessage[1];
        repo = urlInMessage[2].replace(/\.git$/, "");
        console.log("[Stream] Extracted from message:", owner, repo);
      }
    }

    if (!owner || !repo) {
      console.warn(
        "저장소 정보가 없습니다. 백엔드에서 clarification 요청이 올 수 있습니다."
      );
    }

    setStreamingMessage("");
    setIsStreaming(true);
    // 진행률 초기화
    setNodeProgress(0);
    setProgressMessage("");
    setCurrentNode("");

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
            console.log("처리 중:", data.agent || data.step || data.node);
            // LangGraph 노드 진행률 처리
            if (data.progress !== undefined) {
              setNodeProgress(data.progress);
            }
            if (data.message) {
              setProgressMessage(data.message);
            }
            if (data.node) {
              setCurrentNode(data.node);
            }
            // 스텝 기반 진행률 (기존 호환)
            if (data.step && !data.progress) {
              const stepProgress = {
                load_session: 5,
                parse_intent: 15,
                run_diagnosis_agent: 40,
                run_onboarding_agent: 40,
                run_security_agent: 40,
                run_contributor_agent: 40,
                finalize_answer: 85,
                update_session: 95,
              };
              setNodeProgress(stepProgress[data.step] || 50);
              setProgressMessage(data.step);
            }
            break;

          case "answer": {
            setIsStreaming(false);
            setStreamingMessage("");
            // 진행률 완료
            setNodeProgress(100);
            setProgressMessage("완료");
            setCurrentNode("complete");

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

                // 온보딩 결과에서 similar_projects도 추출
                const similarProjects = agent_result.similar_projects || [];

                setAnalysisResult((prev) => ({
                  ...prev,
                  onboardingPlan: agent_result,
                  // 온보딩 결과에 포함된 유사 프로젝트도 함께 업데이트
                  ...(similarProjects.length > 0 && { similarProjects }),
                }));
                setIsGeneratingPlan(false);
              }

              // 보안 분석 결과 처리
              if (target_agent === "security" && agent_result) {
                console.log("보안 분석 결과 받음 (스트리밍):", agent_result);

                // 보안 결과를 프론트엔드 형식으로 변환
                const securityResults = agent_result.results || agent_result;
                const vulnerabilities = securityResults.vulnerabilities || {};

                const securityData = {
                  score:
                    securityResults.security_score ??
                    agent_result.security_score,
                  grade:
                    securityResults.security_grade ??
                    agent_result.security_grade,
                  risk_level:
                    securityResults.risk_level ??
                    agent_result.risk_level ??
                    "unknown",
                  vulnerability_count:
                    vulnerabilities.total ??
                    agent_result.vulnerability_count ??
                    0,
                  critical:
                    vulnerabilities.critical ??
                    agent_result.critical_count ??
                    0,
                  high: vulnerabilities.high ?? agent_result.high_count ?? 0,
                  medium:
                    vulnerabilities.medium ?? agent_result.medium_count ?? 0,
                  low: vulnerabilities.low ?? agent_result.low_count ?? 0,
                  summary: agent_result.report || "",
                  vulnerabilities: vulnerabilities.details || [],
                  recommendations: agent_result.recommendations || [],
                };

                console.log("변환된 보안 데이터:", securityData);

                setAnalysisResult((prev) => ({
                  ...prev,
                  security: securityData,
                }));
              }

              // 기여자 가이드 결과 처리
              if (target_agent === "contributor" && agent_result) {
                console.log(
                  "기여자 가이드 결과 받음 (스트리밍):",
                  agent_result
                );

                const features = agent_result.features || {};

                setAnalysisResult((prev) => ({
                  ...prev,
                  contributorGuide: agent_result,
                  firstContributionGuide:
                    features.first_contribution_guide || null,
                  contributionChecklist:
                    features.contribution_checklist || null,
                  communityAnalysis: features.community_analysis || null,
                  issueMatching: features.issue_matching || null,
                  structureVisualization:
                    features.structure_visualization || null,
                }));
              }

              // 추천 에이전트 결과 처리
              if (target_agent === "recommend" && agent_result) {
                console.log("추천 결과 받음 (스트리밍):", agent_result);
                setAnalysisResult((prev) => ({
                  ...prev,
                  similarProjects: agent_result.recommendations || [],
                }));
              }

              // 비교 분석 결과 처리
              if (target_agent === "compare" && agent_result) {
                console.log("비교 분석 결과 받음 (스트리밍):", agent_result);
                setAnalysisResult((prev) => ({
                  ...prev,
                  compareResults: agent_result.compare_results || agent_result,
                  compareSummary: agent_result.compare_summary || null,
                }));
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

          case "clarification": {
            // 명확화 요청 (저장소 선택, 경험 수준 등)
            console.log("명확화 요청:", data.message);
            setIsStreaming(false);
            setStreamingMessage("");

            const clarificationResponse = {
              id: `ai_${Date.now()}`,
              role: "assistant",
              content: data.message || "추가 정보가 필요합니다.",
              timestamp: new Date(),
              isClarification: true, // 명확화 요청 표시
            };
            addMessage(clarificationResponse);
            setIsTyping(false);
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

            const errorMessage =
              data?.error || data?.message || "알 수 없는 오류가 발생했습니다.";
            const errorResponse = {
              id: `ai_${Date.now()}`,
              role: "assistant",
              content: `죄송합니다. 응답을 생성하는 중 오류가 발생했습니다: ${errorMessage}`,
              timestamp: new Date(),
            };
            addMessage(errorResponse);
            setIsTyping(false);
            console.error("Streaming error:", errorMessage);
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
    // LangGraph 노드 진행률
    nodeProgress,
    progressMessage,
    currentNode,
  };
};
