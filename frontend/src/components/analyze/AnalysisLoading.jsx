import React, { useEffect, useState } from "react";
import { Loader2, Sparkles, Search, FileText, Activity, Code, BookOpen, CheckCircle, XCircle } from "lucide-react";

const ANALYSIS_STEPS = [
  { id: "intent", label: "AI가 요청 의도 분석 중", icon: Sparkles, progress: 5 },
  { id: "github", label: "저장소 정보 수집 중", icon: Search, progress: 15 },
  { id: "docs", label: "문서 품질 분석 중", icon: FileText, progress: 35 },
  { id: "activity", label: "활동성 분석 중", icon: Activity, progress: 55 },
  { id: "structure", label: "구조 분석 중", icon: Code, progress: 70 },
  { id: "scoring", label: "건강도 점수 계산 중", icon: BookOpen, progress: 85 },
  { id: "quality", label: "AI가 결과 품질 검사 중", icon: Sparkles, progress: 92 },
  { id: "llm", label: "AI 요약 생성 중", icon: Sparkles, progress: 97 },
  { id: "complete", label: "분석 완료", icon: CheckCircle, progress: 100 },
];

/**
 * SSE 기반 분석 진행률 표시 컴포넌트.
 * 
 * @param {Object} props
 * @param {Object} props.userProfile - 사용자 프로필 (repositoryUrl 포함)
 * @param {Function} props.onComplete - 분석 완료 시 호출 (결과 데이터 전달)
 * @param {Function} props.onError - 에러 발생 시 호출
 * @param {boolean} props.useStream - SSE 스트리밍 사용 여부 (기본: true)
 */
const AnalysisLoading = ({ userProfile, onComplete, onError, useStream = true }) => {
  const [currentStep, setCurrentStep] = useState("github");
  const [progress, setProgress] = useState(0);
  const [statusMessage, setStatusMessage] = useState("분석 준비 중...");
  const [isError, setIsError] = useState(false);

  useEffect(() => {
    if (!userProfile?.repositoryUrl || !useStream) return;

    const apiBaseUrl = import.meta.env.VITE_API_URL || "http://localhost:8000";
    const encodedUrl = encodeURIComponent(userProfile.repositoryUrl);
    let eventSourceUrl = `${apiBaseUrl}/api/analyze/stream?repo_url=${encodedUrl}`;
    
    // 메시지가 있으면 쿼리 파라미터로 추가
    if (userProfile.message) {
      eventSourceUrl += `&message=${encodeURIComponent(userProfile.message)}`;
    }

    console.log("[SSE] Connecting to:", eventSourceUrl);
    const eventSource = new EventSource(eventSourceUrl);

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        console.log("[SSE] Event received:", data);
        
        // 백엔드에서 보내는 형식: { step, progress, message, data? }
        setCurrentStep(data.step);
        setProgress(data.progress);
        setStatusMessage(data.message);

        // 분석 완료
        if (data.step === "complete" && data.data?.result) {
          console.log("[SSE] Analysis complete, result:", data.data.result);
          eventSource.close();
          if (onComplete) {
            onComplete(data.data.result);
          }
        }

        // 에러 발생
        if (data.step === "error") {
          console.error("[SSE] Error:", data.data?.error || data.message);
          eventSource.close();
          setIsError(true);
          if (onError) {
            onError(data.data?.error || data.message);
          }
        }
      } catch (e) {
        console.error("[SSE] Parse error:", e, "Raw data:", event.data);
      }
    };

    eventSource.onerror = (error) => {
      console.error("[SSE] Connection error:", error);
      eventSource.close();
      setIsError(true);
      if (onError) {
        onError("서버 연결이 끊어졌습니다. 다시 시도해주세요.");
      }
    };

    eventSource.onopen = () => {
      console.log("[SSE] Connection opened");
    };

    return () => {
      console.log("[SSE] Closing connection");
      eventSource.close();
    };
  }, [userProfile?.repositoryUrl, userProfile?.message, useStream, onComplete, onError]);

  const getStepStatus = (step) => {
    const stepIndex = ANALYSIS_STEPS.findIndex(s => s.id === step.id);
    const currentIndex = ANALYSIS_STEPS.findIndex(s => s.id === currentStep);

    if (isError) return "error";
    if (stepIndex < currentIndex) return "done";
    if (stepIndex === currentIndex) return "active";
    return "pending";
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="w-full max-w-2xl text-center">
        {/* 메인 로딩 애니메이션 */}
        <div className="relative mb-8">
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="w-32 h-32 bg-gradient-to-br from-blue-500/20 to-purple-500/20 rounded-full blur-2xl animate-pulse"></div>
          </div>
          <div className="relative">
            {isError ? (
              <XCircle className="w-20 h-20 mx-auto text-red-500" />
            ) : currentStep === "complete" ? (
              <CheckCircle className="w-20 h-20 mx-auto text-green-500" />
            ) : (
              <>
                <Loader2 className="w-20 h-20 mx-auto text-blue-600 animate-spin" />
                <Sparkles className="w-10 h-10 absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 text-purple-500 animate-pulse" />
              </>
            )}
          </div>
        </div>

        {/* 제목 */}
        <h2 className="text-3xl md:text-4xl font-black text-gray-900 mb-4">
          {isError ? "분석 중 오류 발생" : currentStep === "complete" ? "분석 완료!" : "AI가 분석 중입니다"}
        </h2>

        {/* 상태 메시지 */}
        <p className="text-lg text-gray-600 mb-8">
          {statusMessage}
        </p>

        {/* 진행률 바 */}
        <div className="w-full bg-gray-200 rounded-full h-3 mb-8 overflow-hidden">
          <div
            className={`h-3 rounded-full transition-all duration-500 ease-out ${
              isError ? "bg-red-500" : "bg-gradient-to-r from-blue-500 to-purple-600"
            }`}
            style={{ width: `${progress}%` }}
          ></div>
        </div>

        {/* 진행률 텍스트 */}
        <p className="text-sm text-gray-500 mb-8">
          {progress}% 완료
        </p>

        {/* 진행 단계 표시 */}
        <div className="bg-white rounded-3xl p-6 shadow-xl border border-gray-100">
          <div className="space-y-4">
            {ANALYSIS_STEPS.slice(0, -1).map((step) => (
              <AnalysisStep
                key={step.id}
                icon={<step.icon className="w-5 h-5" />}
                label={step.label}
                status={getStepStatus(step)}
              />
            ))}
          </div>
        </div>

        {/* 선택된 프로필 정보 미리보기 */}
        {userProfile && (
          <div className="mt-6 bg-gradient-to-r from-blue-50 to-purple-50 rounded-2xl p-4 border border-blue-100">
            <p className="text-sm text-gray-600 mb-1">분석 대상</p>
            <p className="text-base font-bold text-gray-900 break-all">
              {userProfile.repositoryUrl}
            </p>
          </div>
        )}
      </div>
    </div>
  );
};

const AnalysisStep = ({ icon, label, status }) => {
  const getStatusStyles = () => {
    switch (status) {
      case "done":
        return {
          container: "bg-green-500 text-white",
          text: "text-green-600",
        };
      case "active":
        return {
          container: "bg-blue-600 text-white animate-pulse",
          text: "text-gray-900",
        };
      case "error":
        return {
          container: "bg-red-500 text-white",
          text: "text-red-600",
        };
      default:
        return {
          container: "bg-gray-200 text-gray-400",
          text: "text-gray-400",
        };
    }
  };

  const styles = getStatusStyles();

  return (
    <div className="flex items-center gap-3">
      <div
        className={`flex items-center justify-center w-10 h-10 rounded-full transition-all ${styles.container}`}
      >
        {status === "done" ? <CheckCircle className="w-5 h-5" /> : icon}
      </div>
      <span className={`text-base font-semibold ${styles.text}`}>
        {label}
      </span>
      {status === "active" && (
        <div className="ml-auto">
          <div className="flex gap-1">
            <div className="w-2 h-2 bg-blue-600 rounded-full animate-bounce"></div>
            <div className="w-2 h-2 bg-blue-600 rounded-full animate-bounce" style={{ animationDelay: "0.1s" }}></div>
            <div className="w-2 h-2 bg-blue-600 rounded-full animate-bounce" style={{ animationDelay: "0.2s" }}></div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AnalysisLoading;
