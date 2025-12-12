import React, { useState, useEffect } from "react";
import UserProfileForm from "../components/analyze/UserProfileForm";
import AnalysisChat from "../components/analyze/AnalysisChat";
import AnalysisLoading from "../components/analyze/AnalysisLoading";
import { analyzeRepository, setCachedAnalysis } from "../lib/api";
import { transformApiResponse } from "../utils/apiResponseTransformer";
import {
  mockAnalysisResult,
  mockEmptyAnalysisResult,
} from "../utils/mockAnalysisData";
import { ChevronLeft, ChevronRight, Database, DatabaseZap } from "lucide-react";

// SSE 스트리밍 사용 여부 (true: SSE, false: 기존 REST API)
const USE_STREAM_MODE = true;

// Mock 데이터 사용 여부 (UI 테스트용) - true로 설정하면 바로 결과 화면으로 이동
const USE_MOCK_DATA = false;

// Mock 데이터 시나리오 목록
const MOCK_SCENARIOS = [
  {
    id: "full",
    label: "전체 데이터",
    description: "모든 섹션에 데이터가 있는 경우",
    data: mockAnalysisResult,
    icon: DatabaseZap,
  },
  {
    id: "empty",
    label: "최소 데이터",
    description: "일부 섹션만 데이터가 있는 경우",
    data: mockEmptyAnalysisResult,
    icon: Database,
  },
];

const AnalyzePage = () => {
  // Mock 시나리오 인덱스
  const [mockScenarioIndex, setMockScenarioIndex] = useState(0);
  const currentScenario = MOCK_SCENARIOS[mockScenarioIndex];

  // Mock 모드일 경우 바로 chat 화면으로
  const [step, setStep] = useState(USE_MOCK_DATA ? "chat" : "profile");
  const [userProfile, setUserProfile] = useState(
    USE_MOCK_DATA ? { repositoryUrl: currentScenario.data.repositoryUrl } : null
  );
  const [analysisResult, setAnalysisResult] = useState(
    USE_MOCK_DATA ? currentScenario.data : null
  );
  const [error, setError] = useState(null);

  // Mock 시나리오 변경 시 데이터 업데이트
  useEffect(() => {
    if (USE_MOCK_DATA) {
      const scenario = MOCK_SCENARIOS[mockScenarioIndex];
      setAnalysisResult(scenario.data);
      setUserProfile({ repositoryUrl: scenario.data.repositoryUrl });
    }
  }, [mockScenarioIndex]);

  // 이전 시나리오
  const handlePrevScenario = () => {
    setMockScenarioIndex((prev) =>
      prev > 0 ? prev - 1 : MOCK_SCENARIOS.length - 1
    );
  };

  // 다음 시나리오
  const handleNextScenario = () => {
    setMockScenarioIndex((prev) =>
      prev < MOCK_SCENARIOS.length - 1 ? prev + 1 : 0
    );
  };

  // 분석 완료 후 페이지 상단으로 스크롤 (Header 높이 고려)
  useEffect(() => {
    if (step === "chat") {
      // Header 높이(약 72px)를 고려하여 스크롤
      setTimeout(() => {
        window.scrollTo({ top: 0, behavior: "smooth" });
      }, 100);
    }
  }, [step]);

  // SSE 완료 핸들러
  const handleStreamComplete = (sseResult) => {
    console.log("SSE 분석 완료:", sseResult);

    const repoUrl = userProfile?.repositoryUrl || sseResult?.repo_id || "";

    // SSE 결과를 캐시에 저장 (채팅에서 같은 URL 입력시 재사용)
    setCachedAnalysis(repoUrl, sseResult);
    console.log("[SSE] Cached result for:", repoUrl);

    const transformed = transformApiResponse(sseResult, repoUrl);
    setAnalysisResult(transformed);
    setStep("chat");
  };

  // SSE 에러 핸들러
  const handleStreamError = (errorMessage) => {
    console.error("SSE 분석 실패:", errorMessage);
    setError(errorMessage);
    setStep("profile");
  };

  // REST API 방식 분석 (fallback)
  const handleProfileSubmit = async (profileData) => {
    setUserProfile(profileData);
    setError(null);

    // 모든 경우 바로 채팅 화면으로 이동
    // 채팅에서 SSE 요청을 시작하고 데이터 도착 시 보고서 패널 표시
    console.log("[AnalyzePage] Going to chat directly:", profileData);

    const hasUrl =
      profileData.repositoryUrl && !profileData.isNaturalLanguageQuery;

    setAnalysisResult({
      repositoryUrl: profileData.repositoryUrl || null,
      initialMessage: profileData.message || profileData.userMessage || null,
      // 사용자가 입력한 원본 메시지 (변환하지 않고 그대로 전달)
      originalMessage: profileData.message || profileData.userMessage || null,
      isNaturalLanguageQuery: !hasUrl,
      // 채팅에서 SSE 스트림을 시작할지 여부
      shouldStartAnalysis: hasUrl,
    });
    setStep("chat");
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 via-white to-gray-50">
      {/* Mock 모드 시나리오 전환 UI */}
      {USE_MOCK_DATA && step === "chat" && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50">
          <div className="bg-white/95 backdrop-blur-sm rounded-2xl shadow-2xl border border-gray-200 px-4 py-3 flex items-center gap-4">
            <button
              onClick={handlePrevScenario}
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
              title="이전 시나리오"
            >
              <ChevronLeft className="w-5 h-5 text-gray-600" />
            </button>

            <div className="flex items-center gap-3 min-w-[200px]">
              {(() => {
                const IconComponent = currentScenario.icon;
                return <IconComponent className="w-5 h-5 text-indigo-600" />;
              })()}
              <div className="text-center">
                <div className="text-sm font-bold text-gray-900">
                  {currentScenario.label}
                </div>
                <div className="text-xs text-gray-500">
                  {currentScenario.description}
                </div>
              </div>
            </div>

            <button
              onClick={handleNextScenario}
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
              title="다음 시나리오"
            >
              <ChevronRight className="w-5 h-5 text-gray-600" />
            </button>

            {/* 시나리오 인디케이터 */}
            <div className="flex gap-1.5 ml-2">
              {MOCK_SCENARIOS.map((_, idx) => (
                <button
                  key={idx}
                  onClick={() => setMockScenarioIndex(idx)}
                  className={`w-2.5 h-2.5 rounded-full transition-colors ${
                    idx === mockScenarioIndex
                      ? "bg-indigo-600"
                      : "bg-gray-300 hover:bg-gray-400"
                  }`}
                />
              ))}
            </div>
          </div>

          {/* Mock 모드 배지 */}
          <div className="absolute -top-2 -right-2 px-2 py-0.5 bg-amber-500 text-white text-xs font-bold rounded-full">
            MOCK
          </div>
        </div>
      )}

      {step === "profile" && (
        <UserProfileForm onSubmit={handleProfileSubmit} error={error} />
      )}

      {step === "loading" && (
        <AnalysisLoading
          userProfile={userProfile}
          useStream={USE_STREAM_MODE}
          onComplete={handleStreamComplete}
          onError={handleStreamError}
        />
      )}

      {step === "chat" && (
        <AnalysisChat
          key={mockScenarioIndex} // 시나리오 변경 시 컴포넌트 리렌더링
          userProfile={userProfile}
          analysisResult={analysisResult}
          onAnalysisUpdate={setAnalysisResult}
        />
      )}
    </div>
  );
};

export default AnalyzePage;
