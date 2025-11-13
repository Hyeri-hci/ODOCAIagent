import React, { useState, useEffect } from "react";
import UserProfileForm from "../components/analyze/UserProfileForm";
import AnalysisChat from "../components/analyze/AnalysisChat";
import AnalysisLoading from "../components/analyze/AnalysisLoading";

const AnalyzePage = () => {
  const [step, setStep] = useState("profile"); // profile, loading, chat
  const [userProfile, setUserProfile] = useState(null);
  const [analysisResult, setAnalysisResult] = useState(null);

  // 분석 완료 후 페이지 상단으로 스크롤 (Header 높이 고려)
  useEffect(() => {
    if (step === "chat") {
      // Header 높이(약 72px)를 고려하여 스크롤
      setTimeout(() => {
        window.scrollTo({ top: 0, behavior: "smooth" });
      }, 100);
    }
  }, [step]);

  const handleProfileSubmit = async (profileData) => {
    setUserProfile(profileData);
    setStep("loading");

    // Mock: AI 분석 시뮬레이션 (3초 후 결과 표시)
    setTimeout(() => {
      // Mock 분석 결과 데이터
      const mockResult = {
        repositoryUrl: profileData.repositoryUrl,
        analysisId: `analysis_${Date.now()}`,
        summary: {
          score: 85,
          healthStatus: "excellent",
          contributionOpportunities: 12,
          estimatedImpact: "high",
        },
        projectSummary: `이 저장소는 React 프레임워크를 사용하며, JavaScript, Python, TypeScript 언어로 개발되었습니다. 현재 12명의 기여자가 활동 중이며, 테스트 커버리지는 68%입니다. 전반적으로 Excellent 상태의 프로젝트입니다.`,
        recommendations: [
          {
            id: "rec_1",
            title: "문서화 개선",
            description: "README.md 파일에 설치 가이드와 사용 예제를 추가하면 사용자 경험이 크게 향상됩니다.",
            difficulty: "easy",
            estimatedTime: "2-3시간",
            impact: "high",
            tags: ["documentation", "beginner-friendly"],
          },
          {
            id: "rec_2",
            title: "타입스크립트 마이그레이션",
            description: "주요 컴포넌트들을 TypeScript로 전환하여 타입 안정성을 높일 수 있습니다.",
            difficulty: "medium",
            estimatedTime: "1-2주",
            impact: "medium",
            tags: ["typescript", "refactoring"],
          },
          {
            id: "rec_3",
            title: "보안 취약점 수정",
            description: "의존성 패키지에서 발견된 2개의 중간 수준 보안 취약점을 업데이트해야 합니다.",
            difficulty: "easy",
            estimatedTime: "1시간",
            impact: "critical",
            tags: ["security", "urgent"],
          },
        ],
        risks: [
          {
            id: "risk_1",
            type: "security",
            severity: "medium",
            description: "오래된 의존성 패키지가 있어 보안 취약점 위험이 있습니다.",
          },
          {
            id: "risk_2",
            type: "general",
            severity: "medium",
            description: "단순 자바스크립트가 50% 이상 있어 타입 안정성이 떨어집니다.",
          },
          {
            id: "risk_3",
            type: "general",
            severity: "medium",
            description: "최근 3개월 간 커밋이 감소하는 추세입니다.",
          },
          {
            id: "risk_4",
            type: "security",
            severity: "medium",
            description: "package.json 파일의 의존성 버전이 일부 고정되지 않았습니다.",
          },
        ],
        technicalDetails: {
          languages: ["JavaScript", "Python", "TypeScript"],
          framework: "React",
          testCoverage: 68,
          dependencies: 45,
          lastCommit: "2일 전",
          openIssues: 8,
          contributors: 12,
          stars: 0,
          forks: 0,
        },
        relatedProjects: [
          {
            name: "facebook/react",
            description: "사용자 인터페이스를 구축하기 위한 자바스크립트 라이브러리",
            score: 85,
            stars: 220000,
            match: 85,
            recommendationReason: "동일한 React 프레임워크를 사용하고 있으며, 컴포넌트 구조와 상태 관리 패턴이 유사합니다. React의 Best Practice를 배우기에 최적의 프로젝트입니다.",
          },
          {
            name: "vercel/next.js",
            description: "프로덕션을 위한 React 프레임워크",
            score: 78,
            stars: 120000,
            match: 72,
            recommendationReason: "React 기반 프로젝트의 서버사이드 렌더링과 라우팅 개선에 관심이 있다면 적합합니다. TypeScript 지원이 우수하여 마이그레이션 참고에 유용합니다.",
          },
          {
            name: "microsoft/vscode",
            description: "Visual Studio Code - 오픈소스 코드 에디터",
            score: 72,
            stars: 150000,
            match: 68,
            recommendationReason: "TypeScript로 작성된 대규모 프로젝트로, 타입 시스템 설계와 모듈화 아키텍처를 학습하기 좋습니다. 문서화도 잘 되어 있어 기여하기 쉽습니다.",
          },
          {
            name: "tensorflow/tensorflow",
            description: "기계 학습을 위한 오픈소스 라이브러리",
            score: 68,
            stars: 180000,
            match: 68,
            recommendationReason: "AI/ML 분야에 관심이 있다면 추천합니다. Python과 TypeScript를 모두 사용하며, 보안 및 성능 최적화 사례를 배울 수 있습니다.",
          },
        ],
      };

      setAnalysisResult(mockResult);
      setStep("chat");
    }, 3000);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 via-white to-gray-50">
      {step === "profile" && (
        <UserProfileForm onSubmit={handleProfileSubmit} />
      )}
      
      {step === "loading" && (
        <AnalysisLoading userProfile={userProfile} />
      )}
      
      {step === "chat" && (
        <AnalysisChat 
          userProfile={userProfile}
          analysisResult={analysisResult}
        />
      )}
    </div>
  );
};

export default AnalyzePage;

