import React, { useState, useRef } from "react";
import { Github, Sparkles, ArrowRight } from "lucide-react";

const UserProfileForm = ({ onSubmit }) => {
  const [formData, setFormData] = useState({
    repositoryUrl: "",
    techStack: [],
    interests: [],
    experienceLevel: "",
    preferredLanguage: "ko",
    additionalNotes: "",
  });

  const [errors, setErrors] = useState({});
  
  // 섹션 refs
  const techStackRef = useRef(null);
  const interestsRef = useRef(null);
  const experienceRef = useRef(null);
  const additionalNotesRef = useRef(null);

  // 기술 스택 옵션
  const techStackOptions = [
    { id: "javascript", label: "JavaScript", color: "bg-yellow-500" },
    { id: "typescript", label: "TypeScript", color: "bg-blue-500" },
    { id: "python", label: "Python", color: "bg-green-600" },
    { id: "java", label: "Java", color: "bg-orange-600" },
    { id: "go", label: "Go", color: "bg-cyan-500" },
    { id: "rust", label: "Rust", color: "bg-orange-700" },
    { id: "cpp", label: "C++", color: "bg-blue-700" },
    { id: "react", label: "React", color: "bg-sky-500" },
    { id: "vue", label: "Vue", color: "bg-emerald-500" },
    { id: "node", label: "Node.js", color: "bg-green-700" },
  ];

  // 관심 분야 옵션
  const interestOptions = [
    { id: "web", label: "웹 개발" },
    { id: "ai", label: "AI/ML" },
    { id: "mobile", label: "모바일" },
    { id: "devops", label: "DevOps" },
    { id: "backend", label: "백엔드" },
    { id: "frontend", label: "프론트엔드" },
    { id: "security", label: "보안" },
    { id: "data", label: "데이터" },
  ];

  // 경험 수준 옵션
  const experienceLevels = [
    { id: "beginner", label: "초급", desc: "1년 미만" },
    { id: "intermediate", label: "중급", desc: "1-3년" },
    { id: "advanced", label: "고급", desc: "3년 이상" },
  ];

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

  const scrollToSection = (ref) => {
    setTimeout(() => {
      ref.current?.scrollIntoView({
        behavior: "smooth",
        block: "center",
      });
    }, 100);
  };

  const toggleSelection = (field, value) => {
    setFormData((prev) => ({
      ...prev,
      [field]: prev[field].includes(value)
        ? prev[field].filter((item) => item !== value)
        : [...prev[field], value],
    }));
    
    // 항목 선택 후 다음 섹션으로 스크롤
    if (field === "techStack" && interestsRef.current) {
      scrollToSection(interestsRef);
    } else if (field === "interests" && experienceRef.current) {
      scrollToSection(experienceRef);
    }
  };
  
  const handleExperienceSelect = (level) => {
    setFormData((prev) => ({ ...prev, experienceLevel: level }));
    
    // 경험 수준 선택 후 추가 정보 섹션으로 스크롤
    if (additionalNotesRef.current) {
      scrollToSection(additionalNotesRef);
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    const newErrors = {};

    // 검증
    if (!formData.repositoryUrl.trim()) {
      newErrors.repositoryUrl = "GitHub 저장소 URL을 입력해주세요.";
    } else if (!validateGitHubUrl(formData.repositoryUrl)) {
      newErrors.repositoryUrl = "올바른 GitHub URL 형식이 아닙니다.";
    }

    if (formData.techStack.length === 0) {
      newErrors.techStack = "최소 1개 이상의 기술 스택을 선택해주세요.";
    }

    if (formData.interests.length === 0) {
      newErrors.interests = "최소 1개 이상의 관심 분야를 선택해주세요.";
    }

    if (!formData.experienceLevel) {
      newErrors.experienceLevel = "경험 수준을 선택해주세요.";
    }

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    // 제출
    onSubmit({
      ...formData,
      repositoryUrl: normalizeGitHubUrl(formData.repositoryUrl),
    });
  };

  return (
    <div className="min-h-screen flex items-center justify-center py-12 px-4">
      <div className="w-full max-w-4xl">
        {/* Header */}
        <div className="text-center mb-12">
          <div className="inline-flex items-center gap-2 bg-gradient-to-r from-blue-500/10 to-purple-500/10 backdrop-blur-sm px-4 py-2 rounded-full border border-blue-200/30 mb-6">
            <Sparkles className="w-4 h-4 text-blue-600" />
            <span className="text-sm font-semibold text-blue-700">
              AI 맞춤형 분석
            </span>
          </div>
          
          <h1 className="text-5xl md:text-6xl font-black text-gray-900 mb-4 tracking-tight">
            당신에 대해
            <br />
            <span className="bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
              알려주세요
            </span>
          </h1>
          
          <p className="text-xl text-gray-600 max-w-2xl mx-auto">
            프로필 정보를 기반으로 AI가 더욱 정확하고 맞춤화된 분석을 제공합니다
          </p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-10">
          {/* GitHub Repository URL */}
          <div className="bg-white rounded-3xl p-8 shadow-lg border border-gray-100">
            <label className="block text-2xl font-bold text-gray-900 mb-4">
              GitHub 저장소
            </label>
            <div className="relative">
              <Github className="absolute left-5 top-1/2 -translate-y-1/2 w-6 h-6 text-gray-400" />
              <input
                type="text"
                value={formData.repositoryUrl}
                onChange={(e) => {
                  setFormData({ ...formData, repositoryUrl: e.target.value });
                  setErrors({ ...errors, repositoryUrl: "" });
                }}
                placeholder="username/repository 또는 전체 URL"
                className="w-full px-6 py-5 pl-16 text-lg border-2 border-gray-200 rounded-2xl focus:border-blue-500 focus:outline-none transition-all"
              />
            </div>
            {errors.repositoryUrl && (
              <p className="mt-2 text-sm text-red-600 font-medium">
                {errors.repositoryUrl}
              </p>
            )}
          </div>

          {/* Tech Stack */}
          <div ref={techStackRef} className="bg-white rounded-3xl p-8 shadow-lg border border-gray-100">
            <label className="block text-2xl font-bold text-gray-900 mb-4">
              기술 스택
            </label>
            <p className="text-gray-600 mb-6">
              사용 가능한 기술을 모두 선택해주세요
            </p>
            <div className="flex flex-wrap gap-3">
              {techStackOptions.map((tech) => (
                <button
                  key={tech.id}
                  type="button"
                  onClick={() => toggleSelection("techStack", tech.id)}
                  className={`px-6 py-3 rounded-full font-semibold transition-all transform hover:scale-105 ${
                    formData.techStack.includes(tech.id)
                      ? `${tech.color} text-white shadow-lg`
                      : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                  }`}
                >
                  {tech.label}
                </button>
              ))}
            </div>
            {errors.techStack && (
              <p className="mt-4 text-sm text-red-600 font-medium">
                {errors.techStack}
              </p>
            )}
          </div>

          {/* Interests */}
          <div ref={interestsRef} className="bg-white rounded-3xl p-8 shadow-lg border border-gray-100">
            <label className="block text-2xl font-bold text-gray-900 mb-4">
              관심 분야
            </label>
            <p className="text-gray-600 mb-6">
              관심 있는 분야를 선택해주세요
            </p>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {interestOptions.map((interest) => (
                <button
                  key={interest.id}
                  type="button"
                  onClick={() => toggleSelection("interests", interest.id)}
                  className={`p-5 rounded-2xl font-semibold transition-all transform hover:scale-105 ${
                    formData.interests.includes(interest.id)
                      ? "bg-gradient-to-br from-blue-500 to-purple-500 text-white shadow-xl"
                      : "bg-gray-50 text-gray-700 hover:bg-gray-100 border-2 border-gray-200"
                  }`}
                >
                  <div className="text-lg">{interest.label}</div>
                </button>
              ))}
            </div>
            {errors.interests && (
              <p className="mt-4 text-sm text-red-600 font-medium">
                {errors.interests}
              </p>
            )}
          </div>

          {/* Experience Level */}
          <div ref={experienceRef} className="bg-white rounded-3xl p-8 shadow-lg border border-gray-100">
            <label className="block text-2xl font-bold text-gray-900 mb-4">
              경험 수준
            </label>
            <p className="text-gray-600 mb-6">
              오픈소스 기여 또는 개발 경험을 선택해주세요
            </p>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {experienceLevels.map((level) => (
                <button
                  key={level.id}
                  type="button"
                  onClick={() => {
                    handleExperienceSelect(level.id);
                    setErrors({ ...errors, experienceLevel: "" });
                  }}
                  className={`p-6 rounded-2xl font-semibold transition-all transform hover:scale-105 ${
                    formData.experienceLevel === level.id
                      ? "bg-gradient-to-br from-indigo-500 to-blue-500 text-white shadow-xl"
                      : "bg-gray-50 text-gray-700 hover:bg-gray-100 border-2 border-gray-200"
                  }`}
                >
                  <div className="text-xl mb-2">{level.label}</div>
                  <div className="text-sm opacity-90">{level.desc}</div>
                </button>
              ))}
            </div>
            {errors.experienceLevel && (
              <p className="mt-4 text-sm text-red-600 font-medium">
                {errors.experienceLevel}
              </p>
            )}
          </div>

          {/* Additional Notes */}
          <div ref={additionalNotesRef} className="bg-white rounded-3xl p-8 shadow-lg border border-gray-100">
            <label className="block text-2xl font-bold text-gray-900 mb-4">
              추가 정보 (선택사항)
            </label>
            <textarea
              value={formData.additionalNotes}
              onChange={(e) =>
                setFormData({ ...formData, additionalNotes: e.target.value })
              }
              placeholder="관심사 또는 참고해야 할 사항을 알려주세요."
              rows={5}
              className="w-full px-6 py-5 text-lg border-2 border-gray-200 rounded-2xl focus:border-blue-500 focus:outline-none transition-all resize-none"
            />
            <p className="mt-2 text-sm text-gray-500">
              예: "TypeScript 마이그레이션에 관심이 있습니다", "보안 취약점 수정을 우선적으로 다루고 싶습니다"
            </p>
          </div>

          {/* Submit Button */}
          <div className="flex justify-center pt-4">
            <button
              type="submit"
              className="group inline-flex items-center gap-3 bg-gradient-to-r from-blue-600 to-purple-600 text-white px-12 py-6 rounded-full text-xl font-bold hover:from-blue-700 hover:to-purple-700 shadow-2xl hover:shadow-blue-500/50 hover:scale-105 transition-all"
            >
              분석 시작하기
              <ArrowRight className="w-6 h-6 group-hover:translate-x-1 transition-transform" />
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default UserProfileForm;

