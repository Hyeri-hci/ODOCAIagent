import React, { useState, useEffect } from "react";
import {
  Github,
  Sparkles,
  ArrowRight,
  AlertCircle,
  Search,
} from "lucide-react";

const UserProfileForm = ({ onSubmit, error, isLoading: externalLoading }) => {
  const [inputValue, setInputValue] = useState("");
  const [userMessage, setUserMessage] = useState("");
  const [priority, setPriority] = useState("thoroughness");
  const [validationError, setValidationError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const inputRef = React.useRef(null);

  // 외부 로딩 상태가 끝나면 (에러 발생 시) 제출 상태 해제
  useEffect(() => {
    if (error) {
      setIsSubmitting(false);
    }
  }, [error]);

  const isLoading = isSubmitting || externalLoading;

  // GitHub URL 추출 및 정규화 로직
  const extractGitHubUrl = (text) => {
    // 1. Full URL 패턴 (문장 중간에 있어도 찾음)
    const urlPattern = /https?:\/\/(www\.)?github\.com\/[\w-]+\/[\w.-]+/g;
    const urlMatch = text.match(urlPattern);

    if (urlMatch) {
      return { url: urlMatch[0], isFullUrl: true };
    }

    // 2. Short Pattern (owner/repo) - 문장 중간에 있어도 찾음
    const shortPattern = /(^|[\s,])([A-Za-z0-9][\w-]*\/[\w.-]+)/;
    const shortMatch = text.match(shortPattern);

    if (shortMatch) {
      const repoPath = shortMatch[2].trim();
      return { url: `https://github.com/${repoPath}`, isFullUrl: false };
    }

    return null;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setValidationError("");

    const extracted = extractGitHubUrl(inputValue);

    // URL이 없어도 자연어 메시지로 제출 허용 (백엔드가 저장소 검색)
    if (!extracted) {
      // 입력값이 비어있으면 에러
      if (!inputValue.trim()) {
        setValidationError("메시지를 입력해주세요.");
        return;
      }

      // URL 없이 자연어 메시지로 제출
      setIsSubmitting(true);
      onSubmit({
        repositoryUrl: null,  // URL 없음
        message: inputValue.trim(),
        userMessage: inputValue.trim(),
        priority: priority,
        isNaturalLanguageQuery: true,  // 자연어 쿼리 플래그
      });
      return;
    }

    setIsSubmitting(true);

    // URL을 제거한 텍스트 (UI 표시용)
    let textWithoutUrl = "";
    if (extracted.isFullUrl) {
      textWithoutUrl = inputValue.replace(extracted.url, "").trim();
    }

    onSubmit({
      repositoryUrl: extracted.url,
      // 원본 메시지 그대로 전달 (백엔드에서 저장소 감지용)
      message: inputValue.trim(),
      userMessage: inputValue.trim(),
      // URL 제거된 텍스트 (optional, UI용)
      textWithoutUrl: textWithoutUrl,
      priority: priority,
    });
  };

  return (
    <div className="min-h-screen flex flex-col items-center justify-center py-12 px-4 bg-[#f8f9fa]">
      <div className="w-full max-w-3xl">
        {/* Header */}
        <div className="text-center mb-12">
          {/* Logo or Brand */}
          <div className="inline-flex items-center gap-2 mb-6">
            <div className="w-10 h-10 bg-black rounded-xl flex items-center justify-center">
              <Sparkles className="w-6 h-6 text-white" />
            </div>
          </div>

          <h1 className="text-4xl md:text-5xl font-bold text-gray-900 mb-6 tracking-tight">
            무엇을 도와드릴까요?
          </h1>

          <p className="text-lg text-gray-500 max-w-xl mx-auto">
            GitHub 저장소 주소와 함께 궁금한 점을 자연스럽게 물어보세요.
          </p>
        </div>

        {/* Error Alert */}
        {error && (
          <div className="mb-6 mx-auto max-w-2xl p-4 bg-red-50 border border-red-100 rounded-xl flex items-center gap-3 animate-fade-in">
            <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0" />
            <p className="text-sm text-red-700 font-medium">{error}</p>
          </div>
        )}

        {/* Validation Alert */}
        {validationError && (
          <div className="mb-6 mx-auto max-w-2xl p-4 bg-orange-50 border border-orange-100 rounded-xl flex items-center gap-3 animate-fade-in">
            <AlertCircle className="w-5 h-5 text-orange-500 flex-shrink-0" />
            <p className="text-sm text-orange-700 font-medium">
              {validationError}
            </p>
          </div>
        )}

        {/* Integrated Search Form */}
        <form
          onSubmit={handleSubmit}
          className="relative max-w-2xl mx-auto group"
        >
          <div
            className={`
              relative flex items-center bg-white rounded-2xl shadow-[0_8px_30px_rgb(0,0,0,0.08)] 
              border-2 transition-all duration-300 cursor-text
              ${isLoading
                ? "border-gray-100 bg-gray-50"
                : "border-transparent hover:border-gray-200 focus-within:border-black focus-within:shadow-[0_8px_40px_rgb(0,0,0,0.12)]"
              }
            `}
            onClick={() => inputRef.current?.focus()}
          >
            {/* Icon */}
            <div className="pl-6 text-gray-400">
              {isLoading ? (
                <div className="w-6 h-6 border-2 border-gray-300 border-t-black rounded-full animate-spin" />
              ) : (
                <Search className="w-6 h-6" />
              )}
            </div>

            {/* Input */}
            <input
              ref={inputRef}
              type="text"
              value={inputValue}
              onChange={(e) => {
                setInputValue(e.target.value);
                setValidationError("");
              }}
              placeholder="https://github.com/owner/repo 보안 취약점 분석해줘"
              className="w-full px-4 py-6 text-lg bg-transparent border-none focus:ring-0 focus:outline-none placeholder:text-gray-400 text-gray-900"
              disabled={isLoading}
              autoFocus
            />

            {/* Submit Arrow */}
            <button
              type="submit"
              disabled={isLoading || !inputValue.trim()}
              className="mr-3 p-3 rounded-xl bg-gray-100 text-gray-500 hover:bg-black hover:text-white disabled:opacity-50 disabled:hover:bg-gray-100 disabled:hover:text-gray-500 transition-all duration-200"
              onClick={(e) => e.stopPropagation()} // Prevent double focus trigger
            >
              <ArrowRight className="w-5 h-5" />
            </button>
          </div>

          {/* Helper / Suggestion Chips */}
          {!isLoading && (
            <div className="mt-6 flex flex-wrap justify-center gap-3">
              <button
                type="button"
                onClick={() =>
                  setInputValue(
                    "https://github.com/pallets/flask 초보자가 기여하기 좋은 이슈 찾아줘"
                  )
                }
                className="px-4 py-2 bg-white border border-gray-200 rounded-full text-sm text-gray-600 hover:border-gray-400 hover:bg-gray-50 transition-colors"
              >
                Flask 기여하기 좋은 이슈 추천
              </button>
              <button
                type="button"
                onClick={() =>
                  setInputValue(
                    "https://github.com/facebook/react 보안 취약점 분석해줘"
                  )
                }
                className="px-4 py-2 bg-white border border-gray-200 rounded-full text-sm text-gray-600 hover:border-gray-400 hover:bg-gray-50 transition-colors"
              >
                React 보안 분석
              </button>
              <button
                type="button"
                onClick={() =>
                  setInputValue(
                    "https://github.com/django/django 구조랑 기술 스택 설명해줘"
                  )
                }
                className="px-4 py-2 bg-white border border-gray-200 rounded-full text-sm text-gray-600 hover:border-gray-400 hover:bg-gray-50 transition-colors"
              >
                Django 구조 분석
              </button>
            </div>
          )}
        </form>
      </div>
    </div>
  );
};

export default UserProfileForm;
