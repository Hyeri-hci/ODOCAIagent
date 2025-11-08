import React from "react";
import { FileText, Mail, Loader2 } from "lucide-react";

// PDF 리포트 전송 확인 모달 컴포넌트
// isOpen: 모달 표시 여부
// onClose: 모달 닫기 핸들러
// onConfirm: 전송 확인 핸들러
// isLoading: 로딩 상태
const ConfirmSendModal = ({
  isOpen,
  onClose,
  onConfirm,
  isLoading = false,
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50">
      <div className="bg-white rounded-2xl p-8 shadow-2xl max-w-md mx-4 animate-fadeIn">
        <div className="text-center">
          <div className="w-16 h-16 bg-gradient-to-br from-[#2563EB] to-[#1E3A8A] rounded-full flex items-center justify-center mx-auto mb-4">
            <FileText className="w-8 h-8 text-white" />
          </div>
          <h3 className="text-2xl font-black text-gray-900 mb-3">
            분석 리포트 전송
          </h3>
          <p className="text-gray-600 mb-6 leading-relaxed">
            카카오톡 연동 이메일로
            <br />
            분석 리포트를 PDF로 전송하시겠습니까?
          </p>
          <div className="flex gap-3">
            <button
              onClick={onClose}
              disabled={isLoading}
              className="flex-1 px-6 py-3 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-xl font-semibold transition-all disabled:opacity-50"
            >
              취소
            </button>
            <button
              onClick={onConfirm}
              disabled={isLoading}
              className="flex-1 px-6 py-3 bg-gradient-to-r from-[#2563EB] to-[#1E3A8A] hover:from-[#1E3A8A] hover:to-[#0F172A] text-white rounded-xl font-semibold transition-all disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  확인 중...
                </>
              ) : (
                <>
                  <Mail className="w-5 h-5" />
                  전송
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ConfirmSendModal;
