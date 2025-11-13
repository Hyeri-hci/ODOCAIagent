import React, { useState } from "react";
import { Github, ArrowRight, AlertCircle } from "lucide-react";
import { useScrollAnimation } from "../hooks/useScrollAnimation";

const AnalyzeForm = ({ onAnalyze, isAnalyzing }) => {
  const [repoUrl, setRepoUrl] = useState("");
  const [error, setError] = useState("");
  const [ref, isVisible] = useScrollAnimation();

  const validateAndNormalizeGitHubUrl = (input) => {
    const trimmedInput = input.trim();
    const fullUrlPattern =
      /^https?:\/\/(www\.)?github\.com\/[\w-]+\/[\w.-]+\/?$/;
    if (fullUrlPattern.test(trimmedInput)) {
      return { valid: true, url: trimmedInput };
    }
    const shortPattern = /^[\w-]+\/[\w.-]+$/;
    if (shortPattern.test(trimmedInput)) {
      return { valid: true, url: `https://github.com/${trimmedInput}` };
    }
    return { valid: false, url: null };
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    setError("");

    if (!repoUrl.trim()) {
      setError("GitHub 저장소를 입력해주세요");
      return;
    }

    const result = validateAndNormalizeGitHubUrl(repoUrl);
    if (!result.valid) {
      setError("올바른 저장소 형식이 아닙니다");
      return;
    }

    onAnalyze(result.url);
  };

  return (
    <section id="analyze" className="py-40 bg-white">
      <div
        ref={ref}
        className={`container mx-auto px-6 transition-all duration-1000 ${
          isVisible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-10"
        }`}
      >
        <div className="max-w-4xl mx-auto text-center">
          {/* Title */}
          <h2 className="text-5xl md:text-7xl font-black text-gray-900 mb-6 tracking-tight">
            준비되셨나요?
          </h2>
          <p className="text-xl md:text-2xl text-gray-600 mb-16">
            분석하고 싶은 GitHub 저장소를 입력하세요.
          </p>

          {/* Input form */}
          <form onSubmit={handleSubmit} className="mb-16">
            <div className="flex flex-col md:flex-row gap-4 items-center justify-center">
              <div className="relative w-full md:w-auto md:min-w-[500px]">
                <Github className="absolute left-6 top-1/2 -translate-y-1/2 w-6 h-6 text-gray-400" />
                <input
                  type="text"
                  value={repoUrl}
                  onChange={(e) => setRepoUrl(e.target.value)}
                  placeholder="username/repository"
                  disabled={isAnalyzing}
                  className="w-full px-6 py-5 pl-16 text-lg border-2 border-gray-200 rounded-full focus:border-blue-500 focus:outline-none transition-all disabled:bg-gray-50 disabled:text-gray-400"
                />
              </div>

              <button
                type="submit"
                disabled={isAnalyzing}
                className="group w-full md:w-auto inline-flex items-center justify-center gap-3 bg-blue-600 text-white px-10 py-5 rounded-full text-lg font-semibold hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-all shadow-lg hover:shadow-xl hover:scale-105"
              >
                {isAnalyzing ? (
                  <>
                    <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                    분석 중
                  </>
                ) : (
                  <>
                    분석하기
                    <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
                  </>
                )}
              </button>
            </div>

            {error && (
              <div className="mt-4 flex items-center justify-center gap-2 text-red-600">
                <AlertCircle className="w-5 h-5" />
                <span className="text-sm font-medium">{error}</span>
              </div>
            )}
          </form>
        </div>
      </div>
    </section>
  );
};

export default AnalyzeForm;
