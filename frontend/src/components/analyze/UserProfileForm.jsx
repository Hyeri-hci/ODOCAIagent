import React, { useState, useEffect } from "react";
import { Github, Sparkles, ArrowRight, AlertCircle } from "lucide-react";

const UserProfileForm = ({ onSubmit, error, isLoading: externalLoading }) => {
  const [repositoryUrl, setRepositoryUrl] = useState("");
  const [validationError, setValidationError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  // 외부 로딩 상태가 끝나면 (에러 발생 시) 제출 상태 해제
  useEffect(() => {
    if (error) {
      setIsSubmitting(false);
    }
  }, [error]);

  const isLoading = isSubmitting || externalLoading;

  const validateGitHubUrl = (url) => {
    const pattern = /^https?:\/\/(www\.)?github\.com\/[\w-]+\/[\w.-]+\/?$/;
    const shortPattern = /^[\w-]+\/[\w.-]+$/;
    return pattern.test(url.trim()) || shortPattern.test(url.trim());
  };

  const normalizeGitHubUrl = (url) => {
    const trimmed = url.trim();
    if (trimmed.startsWith("http")) return trimmed;
    return `https://github.com/${trimmed}`;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setValidationError("");

    // 검증
    if (!repositoryUrl.trim()) {
      setValidationError("GitHub 저장소 URL을 입력해주세요.");
      return;
    }

    if (!validateGitHubUrl(repositoryUrl)) {
      setValidationError(
        "올바른 GitHub URL 형식이 아닙니다. (예: owner/repo 또는 https://github.com/owner/repo)"
      );
      return;
    }

    setIsSubmitting(true);

    // 제출
    onSubmit({
      repositoryUrl: normalizeGitHubUrl(repositoryUrl),
    });
  };
  return (
    <div className="min-h-screen flex items-center justify-center py-12 px-4">
      <div className="w-full max-w-2xl">
        {/* Header */}
        <div className="text-center mb-12">
          <div className="inline-flex items-center gap-2 bg-gradient-to-r from-blue-500/10 to-purple-500/10 backdrop-blur-sm px-4 py-2 rounded-full border border-blue-200/30 mb-6">
            <Sparkles className="w-4 h-4 text-blue-600" />
            <span className="text-sm font-semibold text-blue-700">
              AI 기반 저장소 분석
            </span>
          </div>

          <h1 className="text-5xl md:text-6xl font-black text-gray-900 mb-4 tracking-tight">
            GitHub 저장소
            <br />
            <span className="text-blue-600">
              분석하기
            </span>
          </h1>

          <p className="text-xl text-gray-600 max-w-xl mx-auto">
            GitHub 저장소 URL을 입력하면 AI가 프로젝트 건강도, 리스크, 기여
            기회를 분석합니다
          </p>
        </div>

        {/* Error Alert */}
        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-2xl flex items-center gap-3">
            <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0" />
            <p className="text-red-700">{error}</p>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* GitHub Repository URL */}
          <div className="bg-white rounded-3xl p-8 shadow-lg border border-gray-100">
            <label className="block text-2xl font-bold text-gray-900 mb-4">
              GitHub 저장소
            </label>
            <div className="relative">
              <Github className="absolute left-5 top-1/2 -translate-y-1/2 w-6 h-6 text-gray-400" />
              <input
                type="text"
                value={repositoryUrl}
                onChange={(e) => {
                  setRepositoryUrl(e.target.value);
                  setValidationError("");
                }}
                placeholder="owner/repo 또는 https://github.com/owner/repo"
                className="w-full px-6 py-5 pl-16 text-lg border-2 border-gray-200 rounded-2xl focus:border-blue-500 focus:outline-none transition-all"
                disabled={isLoading}
              />
            </div>
            {validationError && (
              <p className="mt-3 text-sm text-red-600 font-medium flex items-center gap-2">
                <AlertCircle className="w-4 h-4" />
                {validationError}
              </p>
            )}
            <p className="mt-3 text-sm text-gray-500">
              예:{" "}
              <code className="bg-gray-100 px-2 py-1 rounded">
                pallets/flask
              </code>{" "}
              또는{" "}
              <code className="bg-gray-100 px-2 py-1 rounded">
                https://github.com/facebook/react
              </code>
            </p>
          </div>

          {/* Submit Button */}
          <div className="flex justify-center pt-4">
            <button
              type="submit"
              disabled={isLoading}
              className="group inline-flex items-center gap-3 bg-blue-600 text-white px-12 py-6 rounded-full text-xl font-bold hover:bg-blue-700 shadow-2xl hover:shadow-blue-500/50 hover:scale-105 transition-all disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100"
            >
              {isLoading ? (
                <>
                  <div className="w-6 h-6 border-3 border-white border-t-transparent rounded-full animate-spin" />
                  분석 중...
                </>
              ) : (
                <>
                  분석 시작하기
                  <ArrowRight className="w-6 h-6 group-hover:translate-x-1 transition-transform" />
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default UserProfileForm;
