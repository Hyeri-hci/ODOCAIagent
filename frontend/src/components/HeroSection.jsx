import React from "react";
import { ArrowRight } from "lucide-react";

const HeroSection = ({ onAnalyzeClick }) => {
  return (
    <section className="relative min-h-[90vh] flex items-center justify-center overflow-hidden bg-gradient-to-br from-[#000000] via-[#1a1a2e] to-[#16213e]">
      {/* Animated gradient orbs */}
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute top-1/4 left-1/4 w-[600px] h-[600px] bg-blue-500/20 rounded-full blur-3xl animate-pulse"></div>
        <div
          className="absolute bottom-1/4 right-1/4 w-[500px] h-[500px] bg-purple-500/20 rounded-full blur-3xl animate-pulse"
          style={{ animationDelay: "1s" }}
        ></div>
      </div>

      <div className="relative z-10 container mx-auto px-6 text-center">
        {/* Badge */}
        <div className="inline-flex items-center gap-2 bg-white/10 backdrop-blur-md px-4 py-2 rounded-full border border-white/20 mb-8">
          <span className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></span>
          <span className="text-sm font-medium text-white/90">
            AI 기반 분석
          </span>
        </div>

        {/* Main headline - Apple style big typography */}
        <h1 className="text-6xl md:text-8xl lg:text-9xl font-black text-white mb-6 tracking-tight leading-none">
          오픈소스.
          <br />
          <span className="bg-gradient-to-r from-blue-400 via-cyan-300 to-purple-400 bg-clip-text text-transparent">
            이제 쉽게.
          </span>
        </h1>

        {/* Subheadline */}
        <p className="text-xl md:text-2xl text-gray-300 max-w-3xl mx-auto mb-12 leading-relaxed">
          AI가 몇 초 만에 저장소를 분석합니다.
          <br className="hidden md:block" />
          당신에게 딱 맞는 기여를 찾아보세요.
        </p>

        {/* CTA */}
        <button
          onClick={onAnalyzeClick}
          className="group inline-flex items-center gap-3 bg-white text-black px-10 py-5 rounded-full text-lg font-semibold hover:bg-gray-100 transition-all duration-300 shadow-2xl hover:shadow-blue-500/50 hover:scale-105"
        >
          지금 시작하기
          <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
        </button>
      </div>
    </section>
  );
};

export default HeroSection;
