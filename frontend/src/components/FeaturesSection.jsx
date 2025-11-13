import React from "react";
import {
  Shield,
  Zap,
  Target,
  TrendingUp,
  Users,
  GitBranch,
} from "lucide-react";
import { useScrollAnimation } from "../hooks/useScrollAnimation";

const FeaturesSection = ({ onAnalyzeClick }) => {
  const [ref1, isVisible1] = useScrollAnimation();
  const [ref2, isVisible2] = useScrollAnimation();
  const [ref3, isVisible3] = useScrollAnimation();

  return (
    <div className="bg-white">
      {/* Main Features Hero */}
      <section className="py-32 bg-gradient-to-b from-gray-50 to-white">
        <div
          ref={ref1}
          className={`container mx-auto px-6 transition-all duration-1000 ${
            isVisible1
              ? "opacity-100 translate-y-0"
              : "opacity-0 translate-y-10"
          }`}
        >
          <div className="max-w-6xl mx-auto">
            {/* Section Title */}
            <div className="text-center mb-24">
              <h2 className="text-5xl md:text-7xl font-black text-gray-900 mb-6 tracking-tight">
                AI 기반
                <br />
                <span className="text-[#2563EB] font-extrabold">
                  실시간 분석
                </span>
              </h2>
              <p className="text-xl md:text-2xl text-gray-600 max-w-3xl mx-auto">
                저장소의 모든 측면을 분석하여 실행 가능한 인사이트를 제공합니다.
              </p>
            </div>

            {/* Feature Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
              {/* Feature 1 - Security */}
              <div
                className="group relative bg-gradient-to-br from-blue-50/20 to-indigo-50/20 rounded-3xl p-10 hover:shadow-xl transition-all duration-500 overflow-hidden border border-gray-100"
                style={{ boxShadow: "0 8px 16px rgba(0,0,0,0.05)" }}
              >
                <div className="absolute top-0 right-0 w-64 h-64 bg-blue-200/20 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2 group-hover:scale-150 transition-transform duration-700"></div>
                <div className="relative z-10">
                  <div className="w-16 h-16 bg-blue-600 rounded-2xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                    <Shield className="w-8 h-8 text-white" />
                  </div>
                  <h3 className="text-3xl font-black text-gray-900 mb-3">
                    보안 우선
                  </h3>
                  <p className="text-lg text-gray-700 leading-relaxed">
                    CVE 데이터베이스와 연동하여 취약점, 오래된 의존성, 보안
                    리스크를 감지합니다.
                  </p>
                </div>
              </div>

              {/* Feature 2 - Speed */}
              <div
                className="group relative bg-gradient-to-br from-purple-50/20 to-pink-50/20 rounded-3xl p-10 hover:shadow-xl transition-all duration-500 overflow-hidden border border-gray-100"
                style={{ boxShadow: "0 8px 16px rgba(0,0,0,0.05)" }}
              >
                <div className="absolute top-0 right-0 w-64 h-64 bg-purple-200/20 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2 group-hover:scale-150 transition-transform duration-700"></div>
                <div className="relative z-10">
                  <div className="w-16 h-16 bg-blue-600 rounded-2xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                    <Zap className="w-8 h-8 text-white" />
                  </div>
                  <h3 className="text-3xl font-black text-gray-900 mb-3">
                    빠른 속도
                  </h3>
                  <p className="text-lg text-gray-700 leading-relaxed">
                    몇 시간이 아닌 단 몇 초 만에 종합 분석 결과를 얻으세요.
                  </p>
                </div>
              </div>

              {/* Feature 3 - Precision */}
              <div
                className="group relative bg-gradient-to-br from-green-50/20 to-emerald-50/20 rounded-3xl p-10 hover:shadow-xl transition-all duration-500 overflow-hidden border border-gray-100"
                style={{ boxShadow: "0 8px 16px rgba(0,0,0,0.05)" }}
              >
                <div className="absolute top-0 right-0 w-64 h-64 bg-green-200/20 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2 group-hover:scale-150 transition-transform duration-700"></div>
                <div className="relative z-10">
                  <div className="w-16 h-16 bg-blue-600 rounded-2xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                    <Target className="w-8 h-8 text-white" />
                  </div>
                  <h3 className="text-3xl font-black text-gray-900 mb-3">
                    스마트 매칭
                  </h3>
                  <p className="text-lg text-gray-700 leading-relaxed">
                    AI가 당신의 실력과 관심사에 완벽히 맞는 기여 작업을
                    추천합니다.
                  </p>
                </div>
              </div>

              {/* Feature 4 - Growth */}
              <div
                className="group relative bg-gradient-to-br from-indigo-50/20 to-blue-50/20 rounded-3xl p-10 hover:shadow-xl transition-all duration-500 overflow-hidden border border-gray-100"
                style={{ boxShadow: "0 8px 16px rgba(0,0,0,0.05)" }}
              >
                <div className="absolute top-0 right-0 w-64 h-64 bg-indigo-200/20 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2 group-hover:scale-150 transition-transform duration-700"></div>
                <div className="relative z-10">
                  <div className="w-16 h-16 bg-blue-600 rounded-2xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                    <TrendingUp className="w-8 h-8 text-white" />
                  </div>
                  <h3 className="text-3xl font-black text-gray-900 mb-3">
                    진행 추적
                  </h3>
                  <p className="text-lg text-gray-700 leading-relaxed">
                    카카오 캘린더와 연동하고 마일스톤을 설정하여 기여 성장을
                    확인하세요.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* How It Works - Simplified Apple Style */}
      <section className="py-24 bg-gradient-to-b from-[#0B1220] to-[#1a2742] text-white">
        <div
          ref={ref2}
          className={`container mx-auto px-6 transition-all duration-1000 ${
            isVisible2
              ? "opacity-100 translate-y-0"
              : "opacity-0 translate-y-10"
          }`}
        >
          <div className="max-w-4xl mx-auto text-center">
            <h2 className="text-5xl md:text-6xl font-black mb-4 tracking-tight">
              단 세 단계.
            </h2>
            <p className="text-lg md:text-xl text-gray-300 mb-16">
              분석부터 기여까지 단 몇 분이면 충분합니다.
            </p>

            {/* Steps */}
            <div className="space-y-16">
              {/* Step 1 */}
              <div className="text-left">
                <div className="inline-block mb-4">
                  <div
                    className="text-7xl font-black"
                    style={{ color: "#3B82F6" }}
                  >
                    01
                  </div>
                </div>
                <h3 className="text-3xl md:text-4xl font-black mb-3">분석</h3>
                <p className="text-lg text-gray-300 max-w-xl">
                  URL 입력하면 AI가 분석합니다.
                </p>
              </div>

              {/* Step 2 */}
              <div
                className="text-right"
                style={{ transform: "translateY(10px)" }}
              >
                <div className="inline-block mb-4">
                  <div
                    className="text-7xl font-black"
                    style={{ color: "#7C3AED" }}
                  >
                    02
                  </div>
                </div>
                <h3 className="text-3xl md:text-4xl font-black mb-3">선택</h3>
                <p className="text-lg text-gray-300 max-w-xl ml-auto">
                  원하는 기여 기회를 선택합니다.
                </p>
              </div>

              {/* Step 3 */}
              <div className="text-left">
                <div className="inline-block mb-4">
                  <div
                    className="text-7xl font-black"
                    style={{ color: "#22C55E" }}
                  >
                    03
                  </div>
                </div>
                <h3 className="text-3xl md:text-4xl font-black mb-3">기여</h3>
                <p className="text-lg text-gray-300 max-w-xl">
                  가이드를 따라 실제 PR을 보냅니다.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Final CTA */}
      <section className="pt-32 pb-32 bg-white">
        <div
          ref={ref3}
          className={`container mx-auto px-6 transition-all duration-1000 ${
            isVisible3
              ? "opacity-100 translate-y-0"
              : "opacity-0 translate-y-10"
          }`}
        >
          <div className="max-w-4xl mx-auto text-center">
            <h2 className="text-5xl md:text-7xl font-black text-gray-900 mb-8 tracking-tight leading-tight">
              이제 직접
              <br />
              <span className="text-[#2563EB]">분석</span>을 시작해 보세요.
            </h2>

            <p className="text-xl md:text-2xl text-gray-600 mb-12 font-medium">
              몇 초면 충분합니다.
            </p>

            <button
              onClick={onAnalyzeClick}
              className="inline-flex items-center gap-3 text-white px-12 py-6 rounded-full text-xl font-bold hover:shadow-2xl hover:scale-105 transition-all cursor-pointer"
              style={{ backgroundColor: "#1E40AF" }}
            >
              무료로 시작하기
              <svg
                className="w-6 h-6"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M13 7l5 5m0 0l-5 5m5-5H6"
                />
              </svg>
            </button>
          </div>
        </div>
      </section>
    </div>
  );
};

export default FeaturesSection;
