import React from "react";
import { CheckCircle } from "lucide-react";

// 카카오 로그인 유도 모달 컴포넌트
// isOpen: 모달 표시 여부
// onClose: 모달 닫기 핸들러
// onLogin: 카카오 로그인 핸들러
const KakaoLoginModal = ({ isOpen, onClose, onLogin }) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50">
      <div className="bg-white rounded-2xl p-8 shadow-2xl max-w-md mx-4 animate-fadeIn">
        <div className="text-center">
          <div className="w-16 h-16 bg-[#FEE500] rounded-full flex items-center justify-center mx-auto mb-4">
            <svg className="w-10 h-10" viewBox="0 0 24 24" fill="#3C1E1E">
              <path d="M12 3C6.48 3 2 6.58 2 11c0 2.89 1.86 5.44 4.65 7.02-.28 1.03-1 3.58-1.06 3.85-.08.36.13.36.27.26.11-.07 3.56-2.39 4.14-2.78.66.09 1.32.15 2 .15 5.52 0 10-3.58 10-8S17.52 3 12 3z" />
            </svg>
          </div>
          <h3 className="text-2xl font-black text-gray-900 mb-3">
            카카오 로그인 필요
          </h3>
          <p className="text-gray-600 mb-6 leading-relaxed">
            분석 리포트를 전송하려면
            <br />
            카카오 계정 연동이 필요합니다
          </p>
          <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 mb-6 text-left">
            <div className="flex items-start gap-3">
              <CheckCircle className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
              <div className="text-sm">
                <p className="font-semibold text-blue-900 mb-1">연동 후 혜택</p>
                <ul className="text-blue-700 space-y-1">
                  <li>• 분석 리포트 자동 전송</li>
                  <li>• 마일스톤 캘린더 동기화</li>
                  <li>• 알림 메시지 수신</li>
                </ul>
              </div>
            </div>
          </div>
          <div className="flex gap-3">
            <button
              onClick={onClose}
              className="flex-1 px-6 py-3 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-xl font-semibold transition-all"
            >
              취소
            </button>
            <button
              onClick={onLogin}
              className="flex-1 px-6 py-3 bg-[#FEE500] hover:bg-[#FDD835] text-[#3C1E1E] rounded-xl font-bold transition-all"
            >
              카카오 로그인
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default KakaoLoginModal;
