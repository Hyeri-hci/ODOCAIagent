import React from "react";
import { Send } from "lucide-react";

/**
 * 메시지 입력 컴포넌트
 */
const MessageInput = ({
  inputValue,
  setInputValue,
  onSendMessage,
  onKeyPress,
  isAnalyzing,
  isStreaming,
  isComparing,
  isTyping,
  suggestions,
}) => {
  return (
    <div className="border-t border-gray-100 p-4">
      {isAnalyzing && (
        <div className="mb-3 text-sm text-blue-600 font-semibold flex items-center gap-2">
          <div className="w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
          분석 중입니다...
        </div>
      )}
      {isStreaming && (
        <div className="mb-3 text-sm text-green-600 font-semibold flex items-center gap-2">
          <div className="w-4 h-4 border-2 border-green-600 border-t-transparent rounded-full animate-spin"></div>
          AI가 응답 중입니다...
        </div>
      )}
      <div className="flex gap-3">
        <input
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyPress={onKeyPress}
          placeholder="궁금한 점을 물어보세요... (GitHub URL 입력 시 바로 분석)"
          disabled={isAnalyzing || isStreaming || isComparing}
          className="flex-1 px-4 py-2.5 border border-gray-200 rounded-lg focus:border-gray-400 focus:outline-none transition-colors disabled:bg-gray-100 text-sm"
        />
        <button
          onClick={onSendMessage}
          disabled={
            !inputValue.trim() ||
            isTyping ||
            isAnalyzing ||
            isStreaming ||
            isComparing
          }
          className="bg-gray-800 text-white px-4 py-2.5 rounded-lg hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <Send className="w-4 h-4" />
        </button>
      </div>

      {/* 추천 질문 비활성화 - 필요시 다시 활성화 */}
    </div>
  );
};

/**
 * 추천 질문 버튼 컴포넌트
 */
const SuggestedQuestion = ({ text, onClick }) => {
  return (
    <button
      onClick={onClick}
      className="text-sm px-4 py-2 bg-gray-100 text-gray-700 rounded-full hover:bg-gray-200 transition-all"
    >
      {text}
    </button>
  );
};

export default MessageInput;
