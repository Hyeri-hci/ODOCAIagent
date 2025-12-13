import React from "react";
import { Star, TrendingUp, Shield, Zap } from "lucide-react";
import { useScrollAnimation } from "../hooks/useScrollAnimation";

const HighlightsSection = () => {
  const [ref, isVisible] = useScrollAnimation();

  const highlights = [
    {
      icon: Star,
      title: "스마트 분석",
      description:
        "AI가 GitHub 저장소를 깊이 있게 분석하여 핵심 인사이트를 제공합니다.",
      color: "text-yellow-500",
      bgColor: "bg-yellow-50",
    },
    {
      icon: TrendingUp,
      title: "성장 지표",
      description: "프로젝트의 활성도와 성장 가능성을 객관적으로 평가합니다.",
      color: "text-green-500",
      bgColor: "bg-green-50",
    },
    {
      icon: Shield,
      title: "보안 점검",
      description:
        "잠재적인 보안 취약점을 사전에 감지하고 개선점을 제안합니다.",
      color: "text-blue-500",
      bgColor: "bg-blue-50",
    },
    {
      icon: Zap,
      title: "빠른 온보딩",
      description:
        "새로운 기여자가 프로젝트에 빠르게 적응할 수 있도록 가이드합니다.",
      color: "text-purple-500",
      bgColor: "bg-purple-50",
    },
  ];

  return (
    <section className="py-24 bg-gray-50">
      <div
        ref={ref}
        className={`container mx-auto px-6 transition-all duration-1000 ${
          isVisible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-10"
        }`}
      >
        <div className="max-w-6xl mx-auto">
          {/* Section Header */}
          <div className="text-center mb-16">
            <h2 className="text-4xl md:text-5xl font-bold text-gray-900 mb-4">
              왜 <span className="text-[#2563EB]">ODOC</span>인가요?
            </h2>
            <p className="text-lg text-gray-600 max-w-2xl mx-auto">
              오픈소스 프로젝트를 더 쉽고 빠르게 이해할 수 있도록 도와드립니다.
            </p>
          </div>

          {/* Highlights Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {highlights.map((item, index) => (
              <div
                key={index}
                className="bg-white rounded-2xl p-6 shadow-sm hover:shadow-lg transition-all duration-300 border border-gray-100 group"
              >
                <div
                  className={`w-12 h-12 ${item.bgColor} rounded-xl flex items-center justify-center mb-4 group-hover:scale-110 transition-transform duration-300`}
                >
                  <item.icon className={`w-6 h-6 ${item.color}`} />
                </div>
                <h3 className="text-xl font-semibold text-gray-900 mb-2">
                  {item.title}
                </h3>
                <p className="text-gray-600 text-sm leading-relaxed">
                  {item.description}
                </p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
};

export default HighlightsSection;
