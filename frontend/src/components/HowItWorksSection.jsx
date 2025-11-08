import React from "react";

const HowItWorksSection = () => {
  return (
    <section className="py-20 bg-[#F9FAFB]">
      <div className="container mx-auto px-4">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-4xl md:text-5xl font-black text-[#1E3A8A] mb-4">
              How It Works
            </h2>
            <p className="text-xl text-slate-600">
              간단한 3단계로 오픈소스 기여를 시작하세요
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {/* Step 1 */}
            <div className="group bg-white rounded-2xl p-8 shadow-soft hover:shadow-2xl transition-all duration-300 border border-slate-100 hover:border-[#2563EB] hover:scale-105">
              <div className="w-20 h-20 bg-gradient-to-br from-[#2563EB] to-[#1E3A8A] rounded-2xl flex items-center justify-center text-white text-3xl font-black mb-6 shadow-lg group-hover:shadow-xl transition-shadow">
                1
              </div>
              <div className="mb-4">
                <svg
                  className="w-12 h-12 text-[#2563EB] mb-3"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"
                  />
                </svg>
              </div>
              <h3 className="text-2xl font-bold text-slate-800 mb-4">
                프로젝트 분석
              </h3>
              <p className="text-slate-600 leading-relaxed mb-4">
                GitHub URL을 입력하면 AI가 프로젝트의 건강도, 활동성, 보안
                상태를 종합적으로 분석합니다.
              </p>
              <div className="text-sm text-[#2563EB] font-semibold">
                ✓ CVE 보안 검출
                <br />
                ✓ 코드 품질 분석
                <br />✓ 커뮤니티 활성도
              </div>
            </div>

            {/* Step 2 */}
            <div className="group bg-white rounded-2xl p-8 shadow-soft hover:shadow-2xl transition-all duration-300 border border-slate-100 hover:border-[#2563EB] hover:scale-105">
              <div className="w-20 h-20 bg-gradient-to-br from-purple-500 to-purple-700 rounded-2xl flex items-center justify-center text-white text-3xl font-black mb-6 shadow-lg group-hover:shadow-xl transition-shadow">
                2
              </div>
              <div className="mb-4">
                <svg
                  className="w-12 h-12 text-purple-600 mb-3"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z"
                  />
                </svg>
              </div>
              <h3 className="text-2xl font-bold text-slate-800 mb-4">
                맞춤 추천
              </h3>
              <p className="text-slate-600 leading-relaxed mb-4">
                당신의 실력과 관심사에 맞는 기여 작업을 AI가 추천하고,
                우선순위와 예상 소요시간을 알려드립니다.
              </p>
              <div className="text-sm text-purple-600 font-semibold">
                ✓ 난이도별 작업 분류
                <br />
                ✓ 소요시간 예측
                <br />✓ 우선순위 설정
              </div>
            </div>

            {/* Step 3 */}
            <div className="group bg-white rounded-2xl p-8 shadow-soft hover:shadow-2xl transition-all duration-300 border border-slate-100 hover:border-[#2563EB] hover:scale-105">
              <div className="w-20 h-20 bg-gradient-to-br from-emerald-500 to-emerald-700 rounded-2xl flex items-center justify-center text-white text-3xl font-black mb-6 shadow-lg group-hover:shadow-xl transition-shadow">
                3
              </div>
              <div className="mb-4">
                <svg
                  className="w-12 h-12 text-emerald-600 mb-3"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
                  />
                </svg>
              </div>
              <h3 className="text-2xl font-bold text-slate-800 mb-4">
                일정 관리
              </h3>
              <p className="text-slate-600 leading-relaxed mb-4">
                선택한 작업을 마일스톤으로 생성하고 카카오톡 캘린더에 자동으로
                등록하여 체계적으로 관리하세요.
              </p>
              <div className="text-sm text-emerald-600 font-semibold">
                ✓ 카카오톡 자동 연동
                <br />
                ✓ 마일스톤 생성
                <br />✓ 진행상황 추적
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};

export default HowItWorksSection;
