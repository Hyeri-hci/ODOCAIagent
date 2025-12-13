/**
 * useAnalysisWebSocket - WebSocket 기반 분석 훅
 */

import { useState, useCallback, useRef } from "react";
import useWebSocket from "./useWebSocket";
import { transformApiResponse } from "../utils/apiResponseTransformer";

export const useAnalysisWebSocket = ({
    messages,
    setMessages,
    addMessage,
    setSuggestions,
    setSessionId,
    sessionId: externalSessionId,
    sessionRepo,
    setSessionRepo,
    onAnalysisUpdate,
}) => {
    // 분석 상태
    const [analysisResult, setAnalysisResult] = useState(null);
    const [isTyping, setIsTyping] = useState(false);
    const [isStreaming, setIsStreaming] = useState(false);
    const [streamingMessage, setStreamingMessage] = useState("");
    const [isGeneratingPlan, setIsGeneratingPlan] = useState(false);

    // 진행 상태
    const [nodeProgress, setNodeProgress] = useState(0);
    const [currentNode, setCurrentNode] = useState("");
    const [progressMessage, setProgressMessage] = useState("");

    // 에이전트별 진행 상태
    const [agentStates, setAgentStates] = useState({
        diagnosis: { status: "idle", result: null },
        security: { status: "idle", result: null },
        onboarding: { status: "idle", result: null },
        recommend: { status: "idle", result: null },
        contributor: { status: "idle", result: null },
        comparison: { status: "idle", result: null },
    });

    const pendingMessageRef = useRef(null);

    // 에이전트 완료 핸들러
    const handleAgentComplete = useCallback(
        (agentName, result) => {
            console.log(`[AnalysisWS] Agent complete: ${agentName}`, result);

            // 에이전트 상태 업데이트
            setAgentStates((prev) => ({
                ...prev,
                [agentName]: { status: "complete", result },
            }));

            // 에이전트별 결과 처리
            switch (agentName) {
                case "diagnosis": {
                    const repoUrl =
                        result.owner && result.repo
                            ? `https://github.com/${result.owner}/${result.repo}`
                            : analysisResult?.repositoryUrl || "";

                    const updatedResult = transformApiResponse(
                        { analysis: result },
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
                    break;
                }

                case "security": {
                    const securityResults = result.results || result;
                    const vulnerabilities = securityResults.vulnerabilities || {};

                    const securityData = {
                        score: securityResults.security_score ?? result.security_score,
                        grade: securityResults.security_grade ?? result.security_grade,
                        risk_level: securityResults.risk_level ?? result.risk_level ?? "unknown",
                        vulnerability_count: vulnerabilities.total ?? result.vulnerability_count ?? 0,
                        critical: vulnerabilities.critical ?? result.critical_count ?? 0,
                        high: vulnerabilities.high ?? result.high_count ?? 0,
                        medium: vulnerabilities.medium ?? result.medium_count ?? 0,
                        low: vulnerabilities.low ?? result.low_count ?? 0,
                        summary: result.report || "",
                        vulnerabilities: vulnerabilities.details || [],
                        recommendations: result.recommendations || [],
                    };

                    console.log("[AnalysisWS] Security data:", securityData);

                    setAnalysisResult((prev) => ({
                        ...prev,
                        security: securityData,
                        securityRequested: true,
                    }));
                    break;
                }

                case "onboarding": {
                    const onboardingPlanArray = Array.isArray(result)
                        ? result
                        : result.plan || [];
                    const similarProjects = result.similar_projects || [];

                    setAnalysisResult((prev) => ({
                        ...prev,
                        onboardingPlan: onboardingPlanArray,
                        onboardingSummary: result.summary || "",
                        onboardingAgentAnalysis: result.agent_analysis || null,
                        ...(similarProjects.length > 0 && { similarProjects }),
                    }));
                    setIsGeneratingPlan(false);
                    break;
                }

                case "recommend": {
                    const recProjects =
                        result.recommendations || result.similar_projects || [];

                    setAnalysisResult((prev) => ({
                        ...prev,
                        similarProjects: recProjects,
                    }));
                    break;
                }

                case "contributor": {
                    const features = result.features || {};

                    setAnalysisResult((prev) => ({
                        ...prev,
                        contributorGuide: result.guidelines,
                        firstContributorChecklist: features.first_contributor_checklist || null,
                        issueMatching: features.issue_matching || null,
                        structureVisualization: features.structure_visualization || null,
                    }));
                    break;
                }

                case "comparison": {
                    setAnalysisResult((prev) => ({
                        ...prev,
                        comparisonResult: result,
                    }));
                    break;
                }

                default:
                    console.log(`[AnalysisWS] Unknown agent: ${agentName}`);
            }
        },
        [analysisResult, onAnalysisUpdate]
    );

    // 메시지 핸들러
    const handleMessage = useCallback((data) => {
        console.log("[AnalysisWS] Message:", data.type);

        switch (data.type) {
            case "processing":
                setIsTyping(true);
                setIsStreaming(true);
                setProgressMessage(data.message);
                setCurrentNode(data.agent);

                // 에이전트 상태를 running으로 변경
                if (data.agent) {
                    setAgentStates((prev) => ({
                        ...prev,
                        [data.agent]: { ...prev[data.agent], status: "running" },
                    }));
                }
                break;

            case "clarification":
                setIsStreaming(false);
                setIsTyping(false);
                addMessage({
                    id: `ai_${Date.now()}`,
                    role: "assistant",
                    content: data.message,
                    timestamp: new Date(),
                    isClarification: true,
                });
                break;

            case "warning":
                addMessage({
                    id: `warning_${Date.now()}`,
                    role: "system",
                    content: data.message,
                    timestamp: new Date(),
                    isWarning: true,
                });
                break;

            case "done":
                setIsStreaming(false);
                setIsTyping(false);
                setNodeProgress(100);
                setProgressMessage("완료");
                setCurrentNode("complete");
                break;

            case "cancelled":
                setIsStreaming(false);
                setIsTyping(false);
                setProgressMessage("취소됨");
                break;

            default:
                break;
        }
    }, [addMessage]);

    // 답변 핸들러
    const handleAnswer = useCallback(
        (data) => {
            console.log("[AnalysisWS] Answer received");

            setIsStreaming(false);
            setIsTyping(false);
            setNodeProgress(100);
            setProgressMessage("완료");
            setCurrentNode("complete");

            // 세션 ID 저장
            if (data.session_id) {
                setSessionId(data.session_id);
                localStorage.setItem("odoc_session_id", data.session_id);
            }

            // 저장소 정보 업데이트
            if (data.repo_info?.owner && data.repo_info?.repo) {
                const repoInfo = {
                    owner: data.repo_info.owner,
                    repo: data.repo_info.repo,
                    full_name: `${data.repo_info.owner}/${data.repo_info.repo}`,
                };
                setSessionRepo?.(repoInfo);
                localStorage.setItem("odoc_session_repo", JSON.stringify(repoInfo));
            }

            // AI 응답 메시지 추가
            addMessage({
                id: `ai_${Date.now()}`,
                role: "assistant",
                content: data.content || "응답을 받지 못했습니다.",
                timestamp: new Date(),
            });

            // 추천 질문 설정
            if (data.suggestions?.length > 0) {
                setSuggestions(data.suggestions);
            }
        },
        [setSessionId, setSessionRepo, addMessage, setSuggestions]
    );

    // 에러 핸들러
    const handleError = useCallback(
        (message) => {
            console.error("[AnalysisWS] Error:", message);
            setIsStreaming(false);
            setIsTyping(false);

            addMessage({
                id: `error_${Date.now()}`,
                role: "system",
                content: `오류가 발생했습니다: ${message}`,
                timestamp: new Date(),
                isError: true,
            });
        },
        [addMessage]
    );

    // 연결 핸들러
    const handleConnected = useCallback(
        (wsSessionId) => {
            console.log("[AnalysisWS] Connected, session:", wsSessionId);
            setSessionId(wsSessionId);

            // 대기 중인 메시지가 있으면 전송
            if (pendingMessageRef.current) {
                const { message, owner, repo } = pendingMessageRef.current;
                pendingMessageRef.current = null;
                // sendMessage 직접 호출 불가 - connect 후 자동 전송 필요
            }
        },
        [setSessionId]
    );

    // WebSocket 훅 사용
    const {
        isConnected,
        sessionId: wsSessionId,
        connect,
        disconnect,
        sendMessage: wsSendMessage,
        cancelTask,
    } = useWebSocket({
        onMessage: handleMessage,
        onAgentComplete: handleAgentComplete,
        onAnswer: handleAnswer,
        onError: handleError,
        onConnected: handleConnected,
        onDisconnected: () => {
            console.log("[AnalysisWS] Disconnected");
        },
        autoConnect: false,
    });

    // 분석 요청 전송
    const sendAnalysisRequest = useCallback(
        (userMessage) => {
            // 상태 초기화
            setIsTyping(true);
            setIsStreaming(true);
            setNodeProgress(0);
            setCurrentNode("parse_intent");
            setProgressMessage("요청 분석 중...");
            setAgentStates({
                diagnosis: { status: "idle", result: null },
                security: { status: "idle", result: null },
                onboarding: { status: "idle", result: null },
                recommend: { status: "idle", result: null },
                contributor: { status: "idle", result: null },
                comparison: { status: "idle", result: null },
            });

            // 저장소 정보 가져오기
            let owner = sessionRepo?.owner || null;
            let repo = sessionRepo?.repo || null;

            // 추천 요청에서는 sessionRepo 사용 안 함
            const isRecommendRequest =
                /(?:찾아줘|찾고|추천|프로젝트.*찾|유사.*프로젝트|similar|recommend)/i.test(
                    userMessage
                );
            if (isRecommendRequest) {
                owner = null;
                repo = null;
            }

            if (!isConnected) {
                // 연결 안 되어 있으면 연결 후 전송
                pendingMessageRef.current = { message: userMessage, owner, repo };
                connect(externalSessionId);

                // 연결 후 메시지 전송 (1초 대기)
                setTimeout(() => {
                    if (pendingMessageRef.current) {
                        wsSendMessage(
                            pendingMessageRef.current.message,
                            pendingMessageRef.current.owner,
                            pendingMessageRef.current.repo
                        );
                        pendingMessageRef.current = null;
                    }
                }, 1000);
            } else {
                wsSendMessage(userMessage, owner, repo);
            }
        },
        [
            isConnected,
            sessionRepo,
            externalSessionId,
            connect,
            wsSendMessage,
        ]
    );

    // 분석 취소
    const cancelAnalysis = useCallback(() => {
        cancelTask();
        setIsStreaming(false);
        setIsTyping(false);
        setProgressMessage("취소됨");
    }, [cancelTask]);

    // 분석 결과 초기화
    const resetAnalysisResult = useCallback(() => {
        setAnalysisResult(null);
        setAgentStates({
            diagnosis: { status: "idle", result: null },
            security: { status: "idle", result: null },
            onboarding: { status: "idle", result: null },
            recommend: { status: "idle", result: null },
            contributor: { status: "idle", result: null },
        });
    }, []);

    return {
        // 상태
        analysisResult,
        setAnalysisResult,
        isTyping,
        isStreaming,
        streamingMessage,
        isGeneratingPlan,
        nodeProgress,
        currentNode,
        progressMessage,
        agentStates,

        // WebSocket 상태
        isConnected,

        // 함수
        sendAnalysisRequest,
        sendMessage: wsSendMessage, // Export wsSendMessage as sendMessage
        cancelAnalysis,
        resetAnalysisResult,
        connect,
        disconnect,
    };
};

export default useAnalysisWebSocket;
