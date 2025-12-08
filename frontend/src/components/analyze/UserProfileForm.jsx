import React, { useState, useEffect } from "react";
import { Github, Sparkles, Send, AlertCircle, MessageCircle } from "lucide-react";

const UserProfileForm = ({ onSubmit, error, isLoading: externalLoading }) => {
  const [userInput, setUserInput] = useState("");
  const [validationError, setValidationError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  // 외부 로딩 상태가 끝나면 (에러 발생 시) 제출 상태 해제
  useEffect(() => {
    if (error) {
      setIsSubmitting(false);
    }
  }, [error]);

  const isLoading = isSubmitting || externalLoading;

  // GitHub URL 패턴 검증
  const isGitHubUrl = (input) => {
    const urlPattern = /^https?:\/\/(www\.)?github\.com\/[\w-]+\/[\w.-]+\/?$/;
    return urlPattern.test(input.trim());
  };

  // owner/repo 패턴 검증
  const isOwnerRepoPattern = (input) => {
    const pattern = /^[\w-]+\/[\w.-]+$/;
    return pattern.test(input.trim());
  };

  // 자연어에서 레포 이름 추출 시도
  const extractRepoFromNaturalLanguage = (input) => {
    // GitHub URL이 포함된 경우
    const urlMatch = input.match(/github\.com\/([\w-]+\/[\w.-]+)/i);
    if (urlMatch) {
      return `https://github.com/${urlMatch[1]}`;
    }

    // owner/repo 패턴이 포함된 경우
    const ownerRepoMatch = input.match(/\b([\w-]+\/[\w.-]+)\b/);
    if (ownerRepoMatch) {
      return `https://github.com/${ownerRepoMatch[1]}`;
    }

    // 레포 이름만 언급된 경우 (예: "react 분석해줘", "vscode 레포")
    // 일반적인 레포 이름 패턴: 2글자 이상의 알파벳/숫자/하이픈/언더스코어
    const words = input.split(/\s+/);
    for (const word of words) {
      // 한국어 조사 제거
      const cleanWord = word.replace(/[을를이가에서의]$/, "");
      // 유효한 레포 이름인지 확인 (2글자 이상, 알파벳으로 시작)
      if (/^[a-zA-Z][\w.-]{1,}$/.test(cleanWord)) {
        // 분석/진단/비교 등의 동사가 아닌 경우만
        const actionWords = ["분석", "진단", "비교", "보여", "알려", "설명"];
        if (!actionWords.some(action => cleanWord.includes(action))) {
          return cleanWord; // 레포 이름만 반환 (나중에 검색 필요)
        }
      }
    }

    return null;
  };

  // 입력 파싱 및 정규화
  const parseUserInput = (input) => {
    const trimmed = input.trim();
    
    // 1. 완전한 GitHub URL
    if (isGitHubUrl(trimmed)) {
      return { type: "url", value: trimmed };
    }
    
    // 2. owner/repo 형식
    if (isOwnerRepoPattern(trimmed)) {
      return { type: "url", value: `https://github.com/${trimmed}` };
    }
    
    // 3. 자연어에서 추출 시도
    const extracted = extractRepoFromNaturalLanguage(trimmed);
    if (extracted) {
      // URL 형식으로 추출된 경우
      if (extracted.startsWith("https://")) {
        return { type: "url", value: extracted };
      }
      // 레포 이름만 추출된 경우 - 검색이 필요함을 표시
      return { type: "search", value: extracted, originalInput: trimmed };
    }
    
    // 4. 파싱 실패
    return { type: "unknown", value: trimmed };
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setValidationError("");

    if (!userInput.trim()) {
      setValidationError("분석할 저장소를 입력해주세요.");
      return;
    }

    const parsed = parseUserInput(userInput);

    if (parsed.type === "unknown") {
      setValidationError(
        "저장소를 찾을 수 없습니다. 'owner/repo' 형식으로 입력해주세요. (예: facebook/react)"
      );
      return;
    }

    // 레포 이름만 입력된 경우 - owner/repo 형식 요청
    if (parsed.type === "search") {
      const repoName = parsed.value.toLowerCase();
      // 인기 레포 힌트 제공
      const popularRepos = {
        "react": "facebook/react",
        "vue": "vuejs/vue",
        "angular": "angular/angular",
        "vscode": "microsoft/vscode",
        "typescript": "microsoft/TypeScript",
        "node": "nodejs/node",
        "flask": "pallets/flask",
        "django": "django/django",
        "next": "vercel/next.js",
        "nextjs": "vercel/next.js",
      };
      
      const suggestion = popularRepos[repoName];
      if (suggestion) {
        setValidationError(
          `'${parsed.value}'를 찾으셨나요? '${suggestion}' 형식으로 입력해주세요.`
        );
      } else {
        setValidationError(
          `'${parsed.value}'의 소유자를 알 수 없습니다. 'owner/repo' 형식으로 입력해주세요. (예: facebook/react)`
        );
      }
      return;
    }

    setIsSubmitting(true);

    // 제출 (URL 타입만 허용)
    onSubmit({
      repositoryUrl: parsed.value,
    });
  };


  const handleKeyDown = (e) => {
    // Enter 키로 제출 (Shift+Enter는 줄바꿈)
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
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
            ODOC
            <br />
            <span className="text-blue-600">
              AI Assistant
            </span>
          </h1>

          <p className="text-xl text-gray-600 max-w-xl mx-auto">
            분석하고 싶은 GitHub 저장소를 자유롭게 입력해보세요
          </p>
        </div>

        {/* Error Alert */}
        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-2xl flex items-center gap-3">
            <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0" />
            <p className="text-red-700">{error}</p>
          </div>
        )}

        {/* Chat-style Input */}
        <form onSubmit={handleSubmit}>
          <div className="bg-white rounded-3xl p-6 shadow-lg border border-gray-100">
            <div className="flex items-center gap-3 mb-4">
              <MessageCircle className="w-5 h-5 text-blue-500" />
              <span className="text-sm font-medium text-gray-500">
                자연어로 입력하거나 GitHub URL을 붙여넣으세요
              </span>
            </div>
            
            <div className="relative">
              <div className="absolute left-4 top-4">
                <Github className="w-6 h-6 text-gray-400" />
              </div>
              <textarea
                value={userInput}
                onChange={(e) => {
                  setUserInput(e.target.value);
                  setValidationError("");
                }}
                onKeyDown={handleKeyDown}
                placeholder="facebook/react, microsoft/vscode, 또는 https://github.com/..."
                className="w-full px-6 py-4 pl-14 pr-16 text-lg border-2 border-gray-200 rounded-2xl focus:border-blue-500 focus:outline-none transition-all resize-none min-h-[80px]"
                disabled={isLoading}
                rows={2}
              />
              <button
                type="submit"
                disabled={isLoading || !userInput.trim()}
                className="absolute right-3 bottom-3 p-3 bg-blue-600 text-white rounded-xl hover:bg-blue-700 transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-lg hover:shadow-blue-500/25"
              >
                {isLoading ? (
                  <div className="w-6 h-6 border-2 border-white border-t-transparent rounded-full animate-spin" />
                ) : (
                  <Send className="w-6 h-6" />
                )}
              </button>
            </div>

            {validationError && (
              <p className="mt-3 text-sm text-red-600 font-medium flex items-center gap-2">
                <AlertCircle className="w-4 h-4" />
                {validationError}
              </p>
            )}

            {/* Example hints */}
            <div className="mt-4 flex flex-wrap gap-2">
              <span className="text-sm text-gray-400">예시:</span>
              {["facebook/react", "pallets/flask", "microsoft/vscode"].map((example, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => setUserInput(example)}
                  className="text-sm px-3 py-1 bg-gray-100 hover:bg-gray-200 rounded-full text-gray-600 transition-colors"
                  disabled={isLoading}
                >
                  {example}
                </button>
              ))}
            </div>
          </div>
        </form>

        {/* Feature hints */}
        <div className="mt-8 grid grid-cols-1 md:grid-cols-3 gap-4 text-center">
          <div className="p-4 rounded-2xl bg-white/50 border border-gray-100">
            <div className="text-2xl mb-2">🔍</div>
            <p className="text-sm text-gray-600">프로젝트 건강도 분석</p>
          </div>
          <div className="p-4 rounded-2xl bg-white/50 border border-gray-100">
            <div className="text-2xl mb-2">🚀</div>
            <p className="text-sm text-gray-600">기여 기회 추천</p>
          </div>
          <div className="p-4 rounded-2xl bg-white/50 border border-gray-100">
            <div className="text-2xl mb-2">💬</div>
            <p className="text-sm text-gray-600">AI 채팅 상담</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default UserProfileForm;

