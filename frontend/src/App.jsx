import React, { useState, useEffect } from "react";
import { AppLayout } from "./components/layout";
import HeroSection from "./components/HeroSection";
import AnalyzeForm from "./components/AnalyzeForm";
import HighlightsSection from "./components/HighlightsSection";
import FeaturesSection from "./components/FeaturesSection";
import ResultCards from "./components/ResultCards";
import {
  ConfirmSendModal,
  KakaoLoginModal,
  LoadingOverlay,
} from "./components/modals";
import {
  analyzeRepository,
  createMilestone,
  sendReport,
  checkKakaoAuth,
  getKakaoAuthUrl,
  sendReportPDF,
} from "./lib/api";

function App() {
  // 분석 관련 상태
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisResult, setAnalysisResult] = useState(null);
  const [isCreatingMilestone, setIsCreatingMilestone] = useState(false);
  const [isSendingReport, setIsSendingReport] = useState(false);

  // 알림 상태
  const [notification, setNotification] = useState(null);

  // 카카오 로그인 상태
  const [kakaoUser, setKakaoUser] = useState(null);
  const [isKakaoChecking, setIsKakaoChecking] = useState(false);

  // 모달 상태
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [showKakaoLoginModal, setShowKakaoLoginModal] = useState(false);

  // 알림 표시 헬퍼
  const showNotification = (type, message) => {
    setNotification({ type, message });
    setTimeout(() => setNotification(null), 5000);
  };

  // 카카오 로그인 상태 확인
  useEffect(() => {
    const checkAuth = async () => {
      try {
        const result = await checkKakaoAuth();
        if (result.authenticated) {
          setKakaoUser(result.user);
        }
      } catch (error) {
        console.error("카카오 인증 확인 오류:", error);
      }
    };
    checkAuth();
  }, []);

  // 분석 시작 핸들러
  const handleAnalyze = async (repoUrl) => {
    setIsAnalyzing(true);
    setAnalysisResult(null);

    try {
      const result = await analyzeRepository(repoUrl);
      setAnalysisResult(result);
      showNotification("success", "분석이 완료되었습니다!");

      // 결과 섹션으로 스크롤
      setTimeout(() => {
        document
          .getElementById("results")
          ?.scrollIntoView({ behavior: "smooth" });
      }, 100);
    } catch (error) {
      showNotification(
        "error",
        "분석 중 오류가 발생했습니다. 다시 시도해주세요."
      );
      console.error("분석 오류:", error);
    } finally {
      setIsAnalyzing(false);
    }
  };

  // 마일스톤 생성 핸들러
  const handleCreateMilestone = async (selectedActions, analysis) => {
    setIsCreatingMilestone(true);

    try {
      const result = await createMilestone(selectedActions, analysis);
      showNotification("success", "마일스톤이 생성되고 일정이 등록되었습니다!");
      console.log("마일스톤 생성 결과:", result);
    } catch (error) {
      showNotification("error", "마일스톤 생성 중 오류가 발생했습니다.");
      console.error("마일스톤 생성 오류:", error);
    } finally {
      setIsCreatingMilestone(false);
    }
  };

  // 리포트 전송 핸들러
  const handleSendReport = async (analysisData) => {
    setIsSendingReport(true);

    try {
      const reportSummary = `
ODOC AI Agent 분석 리포트
종합 점수: ${analysisData.score}/100
발견된 위험 요소: ${analysisData.risks.length}개
추천 작업: ${analysisData.actions.length}개
`;

      const result = await sendReport(
        reportSummary,
        analysisData.actions.map((a) => a.id)
      );
      showNotification("success", "카카오톡으로 리포트가 전송되었습니다!");
      console.log("리포트 전송 결과:", result);
    } catch (error) {
      showNotification("error", "리포트 전송 중 오류가 발생했습니다.");
      console.error("리포트 전송 오류:", error);
    } finally {
      setIsSendingReport(false);
    }
  };

  // View Full Report 클릭 핸들러
  const handleViewFullReport = () => {
    setShowConfirmModal(true);
  };

  // 확인 모달에서 '예' 선택 시
  const handleConfirmSendReport = async () => {
    setShowConfirmModal(false);
    setIsKakaoChecking(true);

    try {
      const authResult = await checkKakaoAuth();

      if (authResult.authenticated) {
        // 로그인되어 있으면 바로 PDF 전송
        await sendPDFReport(authResult.user.email);
      } else {
        // 로그인 안 되어 있으면 로그인 유도
        setShowKakaoLoginModal(true);
      }
    } catch (error) {
      showNotification("error", "인증 확인 중 오류가 발생했습니다.");
      console.error("인증 확인 오류:", error);
    } finally {
      setIsKakaoChecking(false);
    }
  };

  // PDF 리포트 전송
  const sendPDFReport = async (email) => {
    setIsSendingReport(true);

    try {
      const result = await sendReportPDF(analysisResult, email);
      showNotification(
        "success",
        `${email}로 분석 리포트 PDF가 전송되었습니다!`
      );
      console.log("PDF 전송 결과:", result);
    } catch (error) {
      showNotification("error", "PDF 리포트 전송 중 오류가 발생했습니다.");
      console.error("PDF 전송 오류:", error);
    } finally {
      setIsSendingReport(false);
    }
  };

  // 카카오 로그인 시작
  const handleKakaoLogin = () => {
    const kakaoAuthUrl = getKakaoAuthUrl();
    window.location.href = kakaoAuthUrl;
  };

  // 분석 섹션으로 스크롤 + Input 포커스
  const scrollToAnalyze = () => {
    // Input 요소를 직접 찾아서 스크롤
    const input = document.querySelector('#analyze input[type="text"]');

    if (input) {
      // 1. Input 요소로 직접 스크롤 (부드럽게)
      input.scrollIntoView({
        behavior: "smooth",
        block: "center", // 화면 중앙에 위치
      });

      // 2. 스크롤 완료 후 포커스
      setTimeout(() => {
        input.focus();
      }, 800); // 스크롤 애니메이션 완료 대기
    } else {
      // Input을 찾지 못한 경우 섹션으로 이동
      const analyzeSection = document.getElementById("analyze");
      if (analyzeSection) {
        analyzeSection.scrollIntoView({
          behavior: "smooth",
          block: "start",
        });
      }
    }
  };

  return (
    <AppLayout notification={notification} hasResult={!!analysisResult}>
      {/* Hero Section - Apple Style */}
      <HeroSection onAnalyzeClick={scrollToAnalyze} />

      {/* Analyze Form - Minimal & Clean */}
      <AnalyzeForm
        onAnalyze={handleAnalyze}
        isAnalyzing={isAnalyzing}
        hasResult={!!analysisResult}
      />

      {/* Result Cards (keep original - user requested) */}
      {analysisResult && (
        <div id="results">
          <ResultCards
            analysisResult={analysisResult}
            onCreateMilestone={handleCreateMilestone}
            onSendReport={handleSendReport}
            onViewReport={handleViewFullReport}
            isCreatingMilestone={isCreatingMilestone}
            isSendingReport={isSendingReport}
          />
        </div>
      )}

      {/* Highlights & Features Section - Only show when no result */}
      {!analysisResult && (
        <>
          <HighlightsSection />
          <FeaturesSection onAnalyzeClick={scrollToAnalyze} />
        </>
      )}

      {/* Modals */}
      <ConfirmSendModal
        isOpen={showConfirmModal}
        onClose={() => setShowConfirmModal(false)}
        onConfirm={handleConfirmSendReport}
        isLoading={isKakaoChecking}
      />

      <KakaoLoginModal
        isOpen={showKakaoLoginModal}
        onClose={() => setShowKakaoLoginModal(false)}
        onLogin={handleKakaoLogin}
      />

      <LoadingOverlay isOpen={isAnalyzing} />
    </AppLayout>
  );
}

export default App;
