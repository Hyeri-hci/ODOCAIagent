import React from 'react';
import { Loader2, CheckCircle } from 'lucide-react';


const LoadingOverlay = ({ isOpen }) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-gradient-to-br from-[#1E3A8A]/95 to-[#0F172A]/95 backdrop-blur-md flex items-center justify-center z-50">
      <div className="bg-white rounded-2xl p-10 shadow-2xl max-w-md mx-4">
        <div className="flex flex-col items-center">
          {/* Spinner */}
          <div className="relative w-20 h-20 mb-6">
            <div className="absolute inset-0 bg-gradient-to-br from-[#2563EB] to-[#1E3A8A] rounded-xl animate-pulse"></div>
            <div className="absolute inset-0 flex items-center justify-center">
              <Loader2 className="w-10 h-10 animate-spin text-white" />
            </div>
          </div>
          
          {/* Text */}
          <h3 className="text-2xl font-black text-gray-900 mb-2">AI 분석 진행 중</h3>
          <p className="text-gray-600 text-center mb-6">
            프로젝트를 심층 분석하고 있습니다<br />
            잠시만 기다려주세요...
          </p>
          
          {/* Progress Steps */}
          <div className="w-full space-y-3">
            <div className="flex items-center gap-3 text-sm">
              <CheckCircle className="w-5 h-5 text-green-500" />
              <span className="text-gray-700">리포지토리 데이터 수집</span>
            </div>
            <div className="flex items-center gap-3 text-sm">
              <Loader2 className="w-5 h-5 text-[#2563EB] animate-spin" />
              <span className="text-[#2563EB] font-semibold">AI 분석 실행 중</span>
            </div>
            <div className="flex items-center gap-3 text-sm opacity-50">
              <div className="w-5 h-5 border-2 border-gray-300 rounded-full"></div>
              <span className="text-gray-400">기여 작업 추천</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default LoadingOverlay;

