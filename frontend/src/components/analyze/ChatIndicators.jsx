import React from "react";
import ReactMarkdown from "react-markdown";

/**
 * 스트리밍 메시지 표시 컴포넌트
 */
const StreamingMessage = ({ streamingMessage, isStreaming }) => {
  if (!isStreaming) return null;

  return (
    <div className="flex items-start gap-3">
      <div className="w-10 h-10 rounded-full bg-blue-600 flex items-center justify-center flex-shrink-0">
        <span className="text-white font-bold text-sm">ODOC</span>
      </div>
      <div className="max-w-[85%] bg-gray-100 rounded-2xl rounded-tl-none px-5 py-3">
        {streamingMessage ? (
          <div className="prose prose-sm max-w-none text-gray-800">
            <ReactMarkdown>{streamingMessage}</ReactMarkdown>
            {/* 타이핑 커서 효과 */}
            <span className="inline-block w-2 h-4 bg-blue-600 ml-1 animate-pulse"></span>
          </div>
        ) : (
          /* 첫 토큰 오기 전 ... 애니메이션 */
          <div className="flex gap-1">
            <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
            <div
              className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
              style={{ animationDelay: "0.1s" }}
            ></div>
            <div
              className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
              style={{ animationDelay: "0.2s" }}
            ></div>
          </div>
        )}
      </div>
    </div>
  );
};

/**
 * 타이핑 인디케이터 컴포넌트
 */
const TypingIndicator = ({ isTyping, isStreaming }) => {
  if (!isTyping || isStreaming) return null;

  return (
    <div className="flex items-start gap-3">
      <div className="w-10 h-10 rounded-full bg-blue-600 flex items-center justify-center flex-shrink-0">
        <span className="text-white font-bold text-sm">ODOC</span>
      </div>
      <div className="bg-gray-100 rounded-2xl rounded-tl-none px-5 py-3">
        <div className="flex gap-1">
          <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
          <div
            className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
            style={{ animationDelay: "0.1s" }}
          ></div>
          <div
            className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
            style={{ animationDelay: "0.2s" }}
          ></div>
        </div>
      </div>
    </div>
  );
};

export { StreamingMessage, TypingIndicator };
