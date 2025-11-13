import React from "react";
import { Loader2, Sparkles, Search, FileText, Shield } from "lucide-react";

const AnalysisLoading = ({ userProfile }) => {
  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="w-full max-w-2xl text-center">
        {/* 메인 로딩 애니메이션 */}
        <div className="relative mb-12">
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="w-32 h-32 bg-gradient-to-br from-blue-500/20 to-purple-500/20 rounded-full blur-2xl animate-pulse"></div>
          </div>
          <div className="relative">
            <Loader2 className="w-24 h-24 mx-auto text-blue-600 animate-spin" />
            <Sparkles className="w-12 h-12 absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 text-purple-500 animate-pulse" />
          </div>
        </div>

        {/* 메시지 */}
        <h2 className="text-4xl md:text-5xl font-black text-gray-900 mb-6">
          AI가 분석 중입니다
        </h2>
        
        <p className="text-xl text-gray-600 mb-12">
          잠시만 기다려주세요...
        </p>

        {/* 진행 단계 표시 */}
        <div className="bg-white rounded-3xl p-8 shadow-xl border border-gray-100">
          <div className="space-y-6">
            <AnalysisStep
              icon={<Search className="w-6 h-6" />}
              label="저장소 정보 수집 중"
              status="active"
            />
            <AnalysisStep
              icon={<FileText className="w-6 h-6" />}
              label="코드 품질 분석 중"
              status="pending"
            />
            <AnalysisStep
              icon={<Shield className="w-6 h-6" />}
              label="보안 취약점 검사 중"
              status="pending"
            />
            <AnalysisStep
              icon={<Sparkles className="w-6 h-6" />}
              label="맞춤형 리포트 생성 중"
              status="pending"
            />
          </div>
        </div>

        {/* 선택된 프로필 정보 미리보기 */}
        {userProfile && (
          <div className="mt-8 bg-gradient-to-r from-blue-50 to-purple-50 rounded-2xl p-6 border border-blue-100">
            <p className="text-sm text-gray-600 mb-2">분석 대상</p>
            <p className="text-lg font-bold text-gray-900 break-all">
              {userProfile.repositoryUrl}
            </p>
          </div>
        )}
      </div>
    </div>
  );
};

const AnalysisStep = ({ icon, label, status }) => {
  return (
    <div className="flex items-center gap-4">
      <div
        className={`flex items-center justify-center w-12 h-12 rounded-full transition-all ${
          status === "active"
            ? "bg-blue-600 text-white animate-pulse"
            : "bg-gray-200 text-gray-400"
        }`}
      >
        {icon}
      </div>
      <span
        className={`text-lg font-semibold ${
          status === "active" ? "text-gray-900" : "text-gray-400"
        }`}
      >
        {label}
      </span>
      {status === "active" && (
        <div className="ml-auto">
          <div className="flex gap-1">
            <div className="w-2 h-2 bg-blue-600 rounded-full animate-bounce"></div>
            <div className="w-2 h-2 bg-blue-600 rounded-full animate-bounce delay-100"></div>
            <div className="w-2 h-2 bg-blue-600 rounded-full animate-bounce delay-200"></div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AnalysisLoading;

