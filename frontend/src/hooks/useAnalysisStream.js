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
  setSessionRepo, // 저장소 정보 동기화용
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
    // 단, 추천/검색 요청에서는 sessionRepo를 사용하지 않음 (이전 repo와 무관한 새 검색)
    const isRecommendRequest =
      /(?:찾아줘|찾고|추천|프로젝트.*찾|유사.*프로젝트|similar|recommend)/i.test(
        userMessage
      );
    if ((!owner || !repo) && sessionRepo && !isRecommendRequest) {
      owner = sessionRepo.owner;
      repo = sessionRepo.repo;
      console.log("[Stream] Using sessionRepo fallback:", owner, repo);
    } else if (isRecommendRequest && sessionRepo) {
      console.log(
        "[Stream] Recommend request detected, skipping sessionRepo fallback"
      );
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
            // 'new'는 유효한 세션 ID가 아니므로 저장하지 않음
            // 실제 세션 ID는 'answer' 이벤트에서 받음
            if (data.session_id && data.session_id !== "new") {
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

              // 에이전트 유형에 맞는 진행 메시지 설정
              const stepMessages = {
                load_session: "세션 로딩 중...",
                parse_intent: "의도 분석 중...",
                run_diagnosis_agent: "프로젝트 진단 중...",
                run_onboarding_agent: "온보딩 플랜 생성 중...",
                run_security_agent: "보안 취약점 분석 중...",
                run_contributor_agent: "기여 가이드 생성 중...",
                finalize_answer: "응답 생성 중...",
                update_session: "세션 업데이트 중...",
              };
              setProgressMessage(stepMessages[data.step] || data.step);
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

            // 다이어그램 데이터 추출 (여러 소스에서)
            let diagramData = null;

            // 1. 최상위 레벨에서 structure_visualization 확인 (finalize_handler_node에서 반환)
            if (data.structure_visualization) {
              diagramData = data.structure_visualization;
              console.log("[Stream] 다이어그램 데이터 (최상위):", diagramData);
            }
            // 2. context.agent_result에서 확인 (onboarding 결과)
            else if (data.context?.agent_result?.structure_visualization) {
              diagramData = data.context.agent_result.structure_visualization;
              console.log(
                "[Stream] 다이어그램 데이터 (agent_result):",
                diagramData
              );
            }
            // 3. contributor 에이전트 features에서 확인
            else if (
              data.context?.target_agent === "contributor" &&
              data.context?.agent_result?.features?.structure_visualization
            ) {
              diagramData =
                data.context.agent_result.features.structure_visualization;
              console.log(
                "[Stream] 다이어그램 데이터 (features):",
                diagramData
              );
            }

            const aiResponse = {
              id: `ai_${Date.now()}`,
              role: "assistant",
              content: data.answer || "응답을 받지 못했습니다.",
              timestamp: new Date(),
              // 다이어그램 데이터가 있으면 메시지에 첨부
              ...(diagramData && { structureVisualization: diagramData }),
            };
            addMessage(aiResponse);
            if (setIsTyping) setIsTyping(false);

            if (data.suggestions && data.suggestions.length > 0) {
              setSuggestions(data.suggestions);
            }

            // contributor_guide 데이터 처리 (finalize_handler_node에서 반환)
            if (data.contributor_guide) {
              console.log(
                "[Stream] contributor_guide 데이터 수신:",
                data.contributor_guide
              );

              // matched_issues가 있으면 recommendedIssues로 매핑
              const matchedIssues = data.contributor_guide.matched_issues || [];

              setAnalysisResult((prev) => ({
                ...prev,
                contributorGuide: data.contributor_guide,
                // matched_issues를 recommendedIssues로 변환
                recommendedIssues:
                  matchedIssues.length > 0
                    ? matchedIssues.map((issue) => ({
                        title: issue.title || issue.issue_title || "",
                        url: issue.url || issue.issue_url || "",
                        number: issue.number || issue.issue_number || 0,
                        labels: issue.labels || [],
                        reason: issue.reason || issue.match_reason || "",
                        score: issue.score || issue.match_score || 0,
                        difficulty: issue.difficulty || "medium",
                        estimated_time: issue.estimated_time || "",
                      }))
                    : prev.recommendedIssues,
                onboardingPlan: [], // 기존 플랜 렌더링 방지
              }));
            }

            // structure_visualization 데이터 처리 (finalize_handler_node에서 반환)
            if (diagramData) {
              console.log(
                "[Stream] structure_visualization 데이터 수신:",
                diagramData
              );
              setAnalysisResult((prev) => ({
                ...prev,
                structureVisualization: diagramData,
              }));
            }

            // 백엔드에서 저장소 정보가 업데이트되었으면 동기화
            if (data.repo_info && data.repo_info.owner && data.repo_info.repo) {
              console.log(
                "[Stream] 백엔드에서 저장소 정보 수신:",
                data.repo_info
              );
              if (setSessionRepo) {
                setSessionRepo({
                  owner: data.repo_info.owner,
                  repo: data.repo_info.repo,
                  full_name: `${data.repo_info.owner}/${data.repo_info.repo}`,
                });
              }
            }

            if (data.context) {
              const { agent_result, target_agent } = data.context;

              // repo_info에서 owner/repo 추출 (백엔드 동기화)
              const backendOwner = data.repo_info?.owner;
              const backendRepo = data.repo_info?.repo;

              if (target_agent === "diagnosis" && agent_result) {
                console.log("진단 결과 받음 (스트리밍):", agent_result);
                console.log(
                  "repo_info:",
                  data.repo_info,
                  "owner:",
                  owner,
                  "repo:",
                  repo
                );

                // repo_info > 로컬 변수 > analysisResult 순으로 fallback
                const effectiveOwner =
                  backendOwner || owner || agent_result.owner;
                const effectiveRepo = backendRepo || repo || agent_result.repo;

                const repoUrl =
                  effectiveOwner && effectiveRepo
                    ? `https://github.com/${effectiveOwner}/${effectiveRepo}`
                    : analysisResult?.repositoryUrl || "";

                console.log("생성된 repoUrl:", repoUrl);

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

              // 진단과 함께 온 보안 결과 처리 (context.security_result)
              const securityResultFromContext = data.context.security_result;
              if (securityResultFromContext) {
                console.log(
                  "보안 결과 받음 (context.security_result):",
                  securityResultFromContext
                );

                const securityResults =
                  securityResultFromContext.results ||
                  securityResultFromContext;
                const vulnerabilities = securityResults.vulnerabilities || {};

                const securityData = {
                  score:
                    securityResults.security_score ??
                    securityResultFromContext.security_score,
                  grade:
                    securityResults.security_grade ??
                    securityResultFromContext.security_grade,
                  risk_level:
                    securityResults.risk_level ??
                    securityResultFromContext.risk_level ??
                    "unknown",
                  vulnerability_count:
                    vulnerabilities.total ??
                    securityResultFromContext.vulnerability_count ??
                    0,
                  critical:
                    vulnerabilities.critical ??
                    securityResultFromContext.critical_count ??
                    0,
                  high:
                    vulnerabilities.high ??
                    securityResultFromContext.high_count ??
                    0,
                  medium:
                    vulnerabilities.medium ??
                    securityResultFromContext.medium_count ??
                    0,
                  low:
                    vulnerabilities.low ??
                    securityResultFromContext.low_count ??
                    0,
                  summary: securityResultFromContext.report || "",
                  vulnerabilities: vulnerabilities.details || [],
                  recommendations:
                    securityResultFromContext.recommendations || [],
                };

                console.log("변환된 보안 데이터 (from context):", securityData);

                setAnalysisResult((prev) => ({
                  ...prev,
                  security: securityData,
                  securityRequested: true,
                }));
              }

              if (target_agent === "onboarding" && agent_result) {
                console.log("온보딩 플랜 생성됨 (스트리밍):", agent_result);

                // structure 타입 처리 (코드 구조 시각화)
                if (
                  agent_result.type === "structure" &&
                  agent_result.structure_visualization
                ) {
                  console.log("코드 구조 시각화 결과 받음");
                  setAnalysisResult((prev) => ({
                    ...prev,
                    structureVisualization:
                      agent_result.structure_visualization,
                  }));
                  setIsGeneratingPlan(false);
                  return;
                }

                // contributor_guide 타입 처리 (마크다운이 직접 포함된 경우)
                if (
                  agent_result.type === "contributor_guide" &&
                  agent_result.markdown
                ) {
                  console.log("기여 가이드 마크다운 결과 받음");
                  setAnalysisResult((prev) => ({
                    ...prev,
                    contributorGuide: agent_result,
                    onboardingPlan: [], // 빈 배열로 설정 (기존 플랜 렌더링 방지)
                  }));
                  setIsGeneratingPlan(false);
                  return;
                }

                // 온보딩 결과에서 similar_projects도 추출
                const similarProjects = agent_result.similar_projects || [];

                // plan 배열 추출 (agent_result가 배열이면 그대로, 객체면 plan 필드에서 추출)
                const onboardingPlanArray = Array.isArray(agent_result)
                  ? agent_result
                  : agent_result.plan || [];

                setAnalysisResult((prev) => ({
                  ...prev,
                  // plan 배열만 저장 (OnboardingPlanSection이 배열을 기대)
                  onboardingPlan: onboardingPlanArray,
                  // 추가 정보도 별도 필드로 저장
                  onboardingSummary: agent_result.summary || "",
                  onboardingAgentAnalysis: agent_result.agent_analysis || null,
                  // 온보딩 결과에 포함된 유사 프로젝트도 함께 업데이트
                  ...(similarProjects.length > 0 && { similarProjects }),
                }));
                setIsGeneratingPlan(false);
              }

              // 보안 분석 결과 처리
              if (target_agent === "security") {
                console.log("보안 분석 결과 받음 (스트리밍):", agent_result);

                // 보안 에이전트가 호출되었음을 표시 (결과가 없어도)
                setAnalysisResult((prev) => ({
                  ...prev,
                  securityRequested: true,
                }));

                if (agent_result) {
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
                // recommendations 또는 similar_projects 키에서 데이터 추출
                const recProjects =
                  agent_result.recommendations ||
                  agent_result.similar_projects ||
                  [];
                setAnalysisResult((prev) => ({
                  ...prev,
                  similarProjects: recProjects,
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

              // 멀티 에이전트 결과 처리 (진단 + 보안 동시 실행 시)
              if (data.context?.multi_agent_results) {
                const multiResults = data.context.multi_agent_results;
                console.log("멀티 에이전트 결과:", multiResults);

                // 진단 결과가 multi_agent_results에 있고, 메인 agent_result에서 처리 안 된 경우
                if (multiResults.diagnosis && target_agent !== "diagnosis") {
                  console.log(
                    "멀티에이전트에서 진단 결과 추출:",
                    multiResults.diagnosis
                  );
                  const diagResult = multiResults.diagnosis;
                  const effectiveOwner = backendOwner || diagResult.owner;
                  const effectiveRepo = backendRepo || diagResult.repo;
                  const repoUrl =
                    effectiveOwner && effectiveRepo
                      ? `https://github.com/${effectiveOwner}/${effectiveRepo}`
                      : "";

                  if (repoUrl) {
                    const updatedResult = transformApiResponse(
                      { analysis: diagResult },
                      repoUrl
                    );
                    setAnalysisResult((prev) => ({
                      ...prev,
                      ...updatedResult,
                      repositoryUrl: repoUrl,
                    }));
                  }
                }

                // 보안 결과가 multi_agent_results에 있으면 처리 (메인 target_agent가 security가 아닌 경우)
                if (multiResults.security && target_agent !== "security") {
                  console.log(
                    "멀티에이전트에서 보안 결과 추출:",
                    multiResults.security
                  );
                  const secResult = multiResults.security;
                  const securityResults = secResult.results || secResult;
                  const vulnerabilities = securityResults.vulnerabilities || {};

                  const securityData = {
                    score:
                      securityResults.security_score ??
                      secResult.security_score,
                    grade:
                      securityResults.security_grade ??
                      secResult.security_grade,
                    risk_level:
                      securityResults.risk_level ??
                      secResult.risk_level ??
                      "unknown",
                    vulnerability_count: vulnerabilities.total ?? 0,
                    critical: vulnerabilities.critical ?? 0,
                    high: vulnerabilities.high ?? 0,
                    medium: vulnerabilities.medium ?? 0,
                    low: vulnerabilities.low ?? 0,
                    vulnerabilities: vulnerabilities.details || [],
                    recommendations: secResult.recommendations || [],
                  };

                  setAnalysisResult((prev) => ({
                    ...prev,
                    security: securityData,
                    securityRequested: true,
                  }));
                }
              }

              // security_result 직접 처리 (백엔드에서 별도 필드로 전달된 경우)
              if (data.context?.security_result) {
                console.log(
                  "보안 결과 직접 수신:",
                  data.context.security_result
                );
                const secResult = data.context.security_result;
                // 백엔드 구조: { results: { security_score, security_grade, vulnerabilities: {total, critical, high, medium, low, details} } }
                // results가 있으면 그 안에서, 없으면 직접 접근
                const results = secResult.results || secResult;
                const vulnerabilities = results.vulnerabilities || {};

                const securityData = {
                  score:
                    results.security_score ?? secResult.security_score ?? null,
                  grade:
                    results.security_grade ?? secResult.security_grade ?? "N/A",
                  risk_level:
                    results.risk_level ?? secResult.risk_level ?? "low",
                  vulnerability_count: vulnerabilities.total ?? 0,
                  critical: vulnerabilities.critical ?? 0,
                  high: vulnerabilities.high ?? 0,
                  medium: vulnerabilities.medium ?? 0,
                  low: vulnerabilities.low ?? 0,
                  vulnerabilities: vulnerabilities.details || [],
                  recommendations: secResult.recommendations || [],
                  summary: `취약점 ${
                    vulnerabilities.total || 0
                  }개 발견 (Critical: ${vulnerabilities.critical || 0}, High: ${
                    vulnerabilities.high || 0
                  })`,
                };

                console.log("보안 데이터 파싱 완료:", securityData);

                setAnalysisResult((prev) => ({
                  ...prev,
                  security: securityData,
                  securityRequested: true,
                }));
              }

              // structure_visualization 직접 처리 (context에서 전달된 경우)
              if (data.context?.structure_visualization) {
                console.log(
                  "구조 시각화 직접 수신:",
                  data.context.structure_visualization
                );
                setAnalysisResult((prev) => ({
                  ...prev,
                  structureVisualization: data.context.structure_visualization,
                }));
              }

              // onboarding_result 직접 처리 (온보딩 플랜)
              if (data.context?.onboarding_result) {
                console.log(
                  "온보딩 결과 직접 수신:",
                  data.context.onboarding_result
                );
                const onboardingResult = data.context.onboarding_result;

                // plan 배열만 저장 (OnboardingPlanSection이 배열을 기대)
                const onboardingPlan = onboardingResult.plan || [];

                setAnalysisResult((prev) => ({
                  ...prev,
                  onboardingPlan: onboardingPlan,
                  onboardingSummary: onboardingResult.summary || "",
                  onboardingResult: onboardingResult,
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

            // 세션 ID 저장 (clarification 후 세션 유지 필수!)
            if (data.session_id && data.session_id !== "new") {
              setSessionId(data.session_id);
              console.log("[Clarification] 세션 ID 저장:", data.session_id);
            }

            const clarificationResponse = {
              id: `ai_${Date.now()}`,
              role: "assistant",
              content: data.message || "추가 정보가 필요합니다.",
              timestamp: new Date(),
              isClarification: true, // 명확화 요청 표시
            };
            addMessage(clarificationResponse);
            if (setIsTyping) setIsTyping(false);
            break;
          }

          case "warning": {
            // 대용량 저장소 등 경고 메시지
            console.log("경고 메시지:", data.message);

            const warningResponse = {
              id: `warning_${Date.now()}`,
              role: "assistant",
              content: `⚠️ ${data.message}`,
              timestamp: new Date(),
              isWarning: true,
            };
            addMessage(warningResponse);
            break;
          }

          case "done": {
            setIsStreaming(false);
            setStreamingMessage("");
            if (setIsTyping) setIsTyping(false);
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
            if (setIsTyping) setIsTyping(false);
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
