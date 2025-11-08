import React, { useState } from 'react';
import { Github, Loader2, CheckCircle, AlertCircle, FileText } from 'lucide-react';

const AnalyzeForm = ({ onAnalyze, isAnalyzing, hasResult }) => {
  const [repoUrl, setRepoUrl] = useState('');
  const [error, setError] = useState('');

  const validateAndNormalizeGitHubUrl = (input) => {
    const trimmedInput = input.trim();
    
    // 전체 URL 형식: https://github.com/owner/repo
    const fullUrlPattern = /^https?:\/\/(www\.)?github\.com\/[\w-]+\/[\w.-]+\/?$/;
    if (fullUrlPattern.test(trimmedInput)) {
      return { valid: true, url: trimmedInput };
    }
    
    // 짧은 형식: owner/repo
    const shortPattern = /^[\w-]+\/[\w.-]+$/;
    if (shortPattern.test(trimmedInput)) {
      return { valid: true, url: `https://github.com/${trimmedInput}` };
    }
    
    return { valid: false, url: null };
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    setError('');

    if (!repoUrl.trim()) {
      setError('GitHub URL 또는 owner/repository 형식을 입력해주세요');
      return;
    }

    const result = validateAndNormalizeGitHubUrl(repoUrl);
    if (!result.valid) {
      setError('올바른 GitHub 리포지토리 URL을 입력해주세요 (예: username/repository 또는 https://github.com/username/repository)');
      return;
    }

    onAnalyze(result.url);
  };

  const preparationSteps = [
    {
      icon: <Github className="w-5 h-5" />,
      title: "리포지토리 접근성 확인",
      description: "Public 리포지토리만 분석 가능합니다"
    },
    {
      icon: <FileText className="w-5 h-5" />,
      title: "README 파일 준비",
      description: "프로젝트 설명이 잘 작성되어 있으면 더 정확한 분석이 가능합니다"
    },
    {
      icon: <CheckCircle className="w-5 h-5" />,
      title: "카카오톡 연동 준비",
      description: "분석 후 결과를 카카오톡으로 받아보실 수 있습니다"
    }
  ];

  return (
    <section className="py-16 bg-gray-50">
      <div className="container mx-auto px-4">
        <div className="max-w-2xl mx-auto">
          <div className="text-center mb-10">
            <h2 className="text-3xl font-bold text-gray-800 mb-4">
              오픈소스 프로젝트 분석 시작
            </h2>
            <p className="text-gray-600">
              GitHub 리포지토리 URL 또는 <span className="font-semibold text-blue-600">owner/repository</span> 형식을 입력하면 AI가 종합적인 분석을 시작합니다
            </p>
          </div>

          <form onSubmit={handleSubmit} className="mb-12">
            <div className="bg-white rounded-lg shadow-sm p-6">
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  GitHub 리포지토리 URL
                </label>
                <div className="relative">
                  <input
                    type="text"
                    value={repoUrl}
                    onChange={(e) => setRepoUrl(e.target.value)}
                    placeholder="username/repository 또는 https://github.com/username/repository"
                    className={`w-full px-4 py-3 pl-12 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors ${
                      error ? 'border-red-500' : 'border-gray-300'
                    }`}
                    disabled={isAnalyzing}
                  />
                  <Github className="absolute left-4 top-3.5 w-5 h-5 text-gray-400" />
                </div>
                {error && (
                  <div className="mt-2 flex items-center gap-2 text-red-600 text-sm">
                    <AlertCircle className="w-4 h-4" />
                    {error}
                  </div>
                )}
              </div>

              <button
                type="submit"
                disabled={isAnalyzing}
                className="w-full bg-blue-600 text-white py-3 rounded-lg font-semibold hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
              >
                {isAnalyzing ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    분석 중...
                  </>
                ) : (
                  <>
                    <Github className="w-5 h-5" />
                    분석 시작
                  </>
                )}
                  </button>
                </div>
              </form>

              {!hasResult && (
                <div className="space-y-4">
                  <h3 className="text-lg font-semibold text-gray-800 mb-4">
                    분석 준비 사항
                  </h3>
                  {preparationSteps.map((step, index) => (
                    <div
                      key={index}
                      className="bg-white rounded-lg p-4 flex gap-4 hover:shadow-md transition-shadow"
                    >
                      <div className="flex-shrink-0 w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center text-blue-600">
                        {step.icon}
                      </div>
                      <div className="flex-1">
                        <h4 className="font-semibold text-gray-800 mb-1">{step.title}</h4>
                        <p className="text-sm text-gray-600">{step.description}</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </section>
  );
};

export default AnalyzeForm;
