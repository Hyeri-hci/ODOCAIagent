import React, { useState, useEffect } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { AnalysisSummaryCard } from "./analysis/AnalysisSummaryCard";
import { DetectedRisksList } from "./analysis/DetectedRisksList";
import { RecommendedContributionsList } from "./analysis/RecommendedContributionsList";
import { ReadmeSummary } from "./analysis/ReadmeSummary";
import { useScrollAnimation } from "../hooks/useScrollAnimation";

const HighlightsSection = () => {
  const [currentSlide, setCurrentSlide] = useState(0);
  const [isAutoPlaying, setIsAutoPlaying] = useState(true);
  const [ref, isVisible] = useScrollAnimation();

  // 데모 데이터
  const demoData = {
    summary: {
      score: 92,
      metrics: {
        security: 85,
        quality: 92,
        activity: 78,
      },
      stats: {
        stars: 1200,
        forks: 234,
        contributors: 89,
      },
    },
    risks: [
      {
        id: 1,
        severity: "high",
        type: "dependency",
        description: "취약한 의존성: lodash@4.17.20 버전 업데이트 필요",
        updatedAt: "2 days ago",
      },
      {
        id: 2,
        severity: "medium",
        type: "license",
        description: "라이선스 불일치: GPL-3.0에서 MIT로 변경 권장",
        updatedAt: "5 days ago",
      },
      {
        id: 3,
        severity: "low",
        type: "documentation",
        description: "보안 정책 미설정: SECURITY.md 파일 추가 권장",
        updatedAt: "1 week ago",
      },
    ],
    contributions: [
      {
        id: 1,
        title: "README 개선하기",
        description: "설치 가이드 및 사용 예제 추가",
        priority: "high",
        duration: "2시간",
      },
      {
        id: 2,
        title: "버그 수정",
        description: "#42: 페이지네이션 오류 수정",
        priority: "medium",
        duration: "4시간",
      },
      {
        id: 3,
        title: "UI 개선",
        description: "다크 모드 지원 추가",
        priority: "low",
        duration: "8시간",
      },
    ],
    readme:
      "ODOC는 오픈소스 프로젝트 분석 및 기여 추천 플랫폼입니다. AI 기반 분석을 통해 프로젝트의 건강도를 평가하고, 보안 취약점을 발견하며, 당신에게 적합한 기여 작업을 추천합니다. 초보 개발자부터 숙련된 오픈소스 기여자까지 모두를 위한 솔루션입니다.",
  };

  // 슬라이드 설정
  const slides = [
    {
      title: "프로젝트 건강도",
      subtitle: "한눈에 보는 종합 분석",
      component: (
        <AnalysisSummaryCard
          score={demoData.summary.score}
          metrics={demoData.summary.metrics}
          stats={demoData.summary.stats}
          isCompleted={true}
        />
      ),
    },
    {
      title: "README 요약",
      subtitle: "프로젝트 핵심 정보",
      component: <ReadmeSummary content={demoData.readme} />,
    },
    {
      title: "보안 취약점",
      subtitle: "발견된 위험 요소",
      component: <DetectedRisksList risks={demoData.risks} />,
    },
    {
      title: "추천 기여 작업",
      subtitle: "AI가 추천하는 작업",
      component: (
        <RecommendedContributionsList actions={demoData.contributions} />
      ),
    },
  ];

  // 자동 슬라이드
  useEffect(() => {
    if (!isAutoPlaying) return;

    const interval = setInterval(() => {
      setCurrentSlide((prev) => (prev + 1) % slides.length);
    }, 5000); // 5초마다

    return () => clearInterval(interval);
  }, [isAutoPlaying, slides.length]);

  const nextSlide = () => {
    setIsAutoPlaying(false);
    setCurrentSlide((prev) => (prev + 1) % slides.length);
  };

  const prevSlide = () => {
    setIsAutoPlaying(false);
    setCurrentSlide((prev) => (prev - 1 + slides.length) % slides.length);
  };

  const goToSlide = (index) => {
    setIsAutoPlaying(false);
    setCurrentSlide(index);
  };

  return (
    <section className="py-32 bg-gradient-to-b from-white to-gray-50">
      <div
        ref={ref}
        className={`container mx-auto px-6 transition-all duration-1000 ${
          isVisible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-10"
        }`}
      >
        {/* Section Header */}
        <div className="text-center mb-12">
          <h2 className="text-5xl md:text-6xl font-black text-gray-900 mb-4">
            분석 결과 미리보기
          </h2>
          <p className="text-xl text-gray-600 max-w-2xl mx-auto">
            AI가 제공하는 상세한 분석 리포트를 확인하세요
          </p>
        </div>

        {/* Carousel Container */}
        <div className="max-w-6xl mx-auto">
          {/* Current Slide Title */}
          <div className="text-center mb-6">
            <h3 className="text-3xl font-black text-gray-900 mb-2">
              {slides[currentSlide].title}
            </h3>
            <p className="text-lg text-gray-600">
              {slides[currentSlide].subtitle}
            </p>
          </div>

          {/* Carousel Viewport */}
          <div className="relative">
            {/* Slide Container with Overflow */}
            <div className="overflow-hidden rounded-3xl">
              <div
                className="flex transition-transform duration-700 ease-in-out"
                style={{
                  transform: `translateX(-${currentSlide * 100}%)`,
                }}
              >
                {slides.map((slide, index) => (
                  <div key={index} className="w-full flex-shrink-0 px-4">
                    {slide.component}
                  </div>
                ))}
              </div>
            </div>

            {/* Navigation Buttons */}
            <button
              onClick={prevSlide}
              className="absolute left-0 top-1/2 -translate-y-1/2 -translate-x-4 w-14 h-14 bg-white rounded-full shadow-2xl flex items-center justify-center hover:bg-gray-50 transition-all hover:scale-110 z-10"
              aria-label="Previous slide"
            >
              <ChevronLeft className="w-6 h-6 text-gray-900" />
            </button>

            <button
              onClick={nextSlide}
              className="absolute right-0 top-1/2 -translate-y-1/2 translate-x-4 w-14 h-14 bg-white rounded-full shadow-2xl flex items-center justify-center hover:bg-gray-50 transition-all hover:scale-110 z-10"
              aria-label="Next slide"
            >
              <ChevronRight className="w-6 h-6 text-gray-900" />
            </button>
          </div>

          {/* Indicators */}
          <div className="flex justify-center gap-3 mt-14">
            {slides.map((_, index) => (
              <button
                key={index}
                onClick={() => goToSlide(index)}
                className={`transition-all duration-300 rounded-full ${
                  index === currentSlide
                    ? "w-12 h-3 bg-indigo-600"
                    : "w-3 h-3 bg-gray-300 hover:bg-gray-400"
                }`}
                aria-label={`Go to slide ${index + 1}`}
              />
            ))}
          </div>

          {/* Auto-play Control */}
          <div className="text-center mt-8">
            <button
              onClick={() => setIsAutoPlaying(!isAutoPlaying)}
              className={`inline-flex items-center gap-2 px-6 py-2.5 rounded-full text-sm font-semibold transition-all ${
                isAutoPlaying
                  ? "bg-gray-100 text-gray-700 hover:bg-gray-200"
                  : "bg-indigo-100 text-indigo-700 hover:bg-indigo-200"
              }`}
            >
              {isAutoPlaying ? (
                <>
                  <span className="w-2 h-2 bg-red-500 rounded-full animate-pulse"></span>
                  자동 재생 중지
                </>
              ) : (
                <>
                  <span className="w-2 h-2 bg-green-500 rounded-full"></span>
                  자동 재생 시작
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </section>
  );
};

export default HighlightsSection;
