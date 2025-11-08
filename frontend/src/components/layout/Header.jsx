import React from "react";
import { GitBranch } from "lucide-react";

export const Header = ({ hasResult = false }) => {
  // 로고 클릭 시 상단으로 이동
  const handleLogoClick = (e) => {
    e.preventDefault();
    window.scrollTo({
      top: 0,
      behavior: "smooth",
    });
  };

  // 분석 시작 클릭 시 analyze 섹션으로 스크롤 + Input에 포커스
  const handleAnalyzeClick = (e) => {
    e.preventDefault();

    // 1. AnalyzeForm 섹션으로 스크롤
    const analyzeSection = document.getElementById("analyze");
    if (analyzeSection) {
      analyzeSection.scrollIntoView({ behavior: "smooth" });
    }

    // 2. Input 필드에 포커스 (스크롤 후 약간 딜레이)
    setTimeout(() => {
      const input = document.querySelector('#analyze input[type="text"]');
      if (input) {
        input.focus();
      }
    }, 500);
  };

  return (
    <header className="fixed top-0 left-0 right-0 bg-white/80 backdrop-blur-md shadow-sm z-50 border-b border-slate-100">
      <div className="container mx-auto px-4 py-4">
        <div className="flex items-center justify-between">
          {/* Logo - 클릭 가능 */}
          <a
            href="#"
            onClick={handleLogoClick}
            className="flex items-center gap-3 cursor-pointer hover:opacity-80 transition-opacity"
          >
            <div className="w-10 h-10 bg-gradient-to-br from-[#2563EB] to-[#1E3A8A] rounded-xl flex items-center justify-center shadow-lg">
              <GitBranch className="w-5 h-5 text-white" />
            </div>
            <span className="text-xl font-bold bg-gradient-to-r from-[#2563EB] to-[#1E3A8A] bg-clip-text text-transparent">
              ODOC AI Agent
            </span>
          </a>

          {/* Navigation */}
          <nav className="hidden md:flex items-center gap-2">
            <a
              href="#analyze"
              onClick={handleAnalyzeClick}
              className="px-5 py-2.5 text-slate-600 hover:text-[#2563EB] hover:bg-blue-50 rounded-xl transition-all font-semibold cursor-pointer"
            >
              분석 시작
            </a>
            {hasResult && (
              <a
                href="#results"
                className="px-5 py-2.5 text-white bg-[#2563EB] hover:bg-[#1E3A8A] rounded-xl transition-all font-semibold shadow-lg hover:shadow-xl"
              >
                결과 보기
              </a>
            )}
          </nav>
        </div>
      </div>
    </header>
  );
};

export default Header;
