import React from "react";
import ReactMarkdown from "react-markdown";
import ReportGenerationMessage from "./ReportGenerationMessage";
import DiagramThumbnail from "../common/DiagramThumbnail";

/**
 * 채팅 메시지 컴포넌트
 */
const ChatMessage = ({
  message,
  onSendMessage,
  onSectionClick,
  analysisResult,
  isReportCollapsed,
  onToggleReportCollapse,
}) => {
  const isUser = message.role === "user";
  const isReportGeneration = message.type === "report_generation";

  // 메시지에 다이어그램 데이터가 있는지 확인
  const hasDiagram = message.diagram || message.structureVisualization;
  const diagramData = message.diagram || message.structureVisualization;

  // 보고서 생성 메시지인 경우
  if (isReportGeneration) {
    return (
      <div className="flex items-start gap-3">
        <div className="w-10 h-10 rounded-full bg-blue-600 flex items-center justify-center flex-shrink-0">
          <span className="text-white font-bold text-xs">ODOC</span>
        </div>
        <div className="flex-1 max-w-[90%]">
          <ReportGenerationMessage
            sections={message.sections || {}}
            onSectionClick={onSectionClick}
            isComplete={message.isComplete}
            analysisResult={analysisResult}
            isCollapsed={isReportCollapsed}
            onToggleCollapse={onToggleReportCollapse}
            progressMessage={message.progressMessage}
          />
        </div>
      </div>
    );
  }

  return (
    <div className={`flex ${isUser ? "justify-end" : "items-start gap-3"}`}>
      {!isUser && (
        <div className="w-10 h-10 rounded-full bg-blue-600 flex items-center justify-center flex-shrink-0">
          <span className="text-white font-bold text-sm">ODOC</span>
        </div>
      )}

      <div
        className={`max-w-[80%] rounded-xl px-4 py-3 break-words overflow-hidden ${
          isUser ? "bg-gray-800 text-white" : "bg-gray-100 text-gray-900"
        }`}
      >
        {isUser ? (
          <p className="whitespace-pre-wrap leading-relaxed break-words">
            {message.content}
          </p>
        ) : (
          <div className="prose prose-sm max-w-none dark:prose-invert">
            <ReactMarkdown
              components={{
                p: ({ children }) => (
                  <p className="mb-3 last:mb-0 leading-relaxed text-gray-800 dark:text-gray-200">
                    {children}
                  </p>
                ),
                strong: ({ children }) => (
                  <strong className="font-semibold text-gray-900 dark:text-white">
                    {children}
                  </strong>
                ),
                ul: ({ children }) => (
                  <ul className="list-disc pl-4 mb-3 space-y-1.5 text-gray-700 dark:text-gray-300">
                    {children}
                  </ul>
                ),
                ol: ({ children }) => (
                  <ol className="list-decimal pl-4 mb-3 space-y-1.5 text-gray-700 dark:text-gray-300">
                    {children}
                  </ol>
                ),
                li: ({ children }) => (
                  <li className="text-sm leading-relaxed">{children}</li>
                ),
                code: ({ children }) => (
                  <code className="px-1.5 py-0.5 bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded text-xs font-mono">
                    {children}
                  </code>
                ),
                hr: () => (
                  <hr className="my-3 border-gray-200 dark:border-gray-600" />
                ),
                a: ({ href, children }) => (
                  <a
                    href={href}
                    className="text-blue-600 hover:underline"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {children}
                  </a>
                ),
              }}
            >
              {message.content}
            </ReactMarkdown>

            {/* 다이어그램 썸네일 (구조 시각화 데이터가 있는 경우) */}
            {hasDiagram && (
              <DiagramThumbnail
                mermaidCode={diagramData?.mermaid_diagram}
                asciiTree={diagramData?.ascii_tree}
                title={
                  diagramData?.owner
                    ? `${diagramData.owner}/${diagramData.repo} 구조`
                    : "코드 구조"
                }
                className="mt-3"
              />
            )}

            {/* 경험 수준 선택 버튼 (clarification 응답인 경우) */}
            {message.content.includes("프로그래밍 경험 수준을 알려주세요") &&
              onSendMessage && (
                <div className="mt-4 space-y-2">
                  <button
                    onClick={() => {
                      const text = "입문자 수준으로 온보딩 플랜 만들어줘";
                      onSendMessage(text);
                    }}
                    className="w-full text-left px-4 py-3 bg-green-50 border-2 border-green-200 rounded-lg hover:bg-green-100 transition-colors"
                  >
                    <div className="font-semibold text-green-700">
                      1️⃣ 입문자
                    </div>
                    <div className="text-sm text-green-600">
                      프로그래밍을 막 시작했거나 이 기술 스택이 처음이에요
                    </div>
                  </button>

                  <button
                    onClick={() => {
                      const text = "중급자 수준으로 온보딩 플랜 만들어줘";
                      onSendMessage(text);
                    }}
                    className="w-full text-left px-4 py-3 bg-blue-50 border-2 border-blue-200 rounded-lg hover:bg-blue-100 transition-colors"
                  >
                    <div className="font-semibold text-blue-700">2️⃣ 중급자</div>
                    <div className="text-sm text-blue-600">
                      기본 개념은 알고 있고, 실제 프로젝트 경험을 쌓고 싶어요
                    </div>
                  </button>

                  <button
                    onClick={() => {
                      const text = "숙련자 수준으로 온보딩 플랜 만들어줘";
                      onSendMessage(text);
                    }}
                    className="w-full text-left px-4 py-3 bg-purple-50 border-2 border-purple-200 rounded-lg hover:bg-purple-100 transition-colors"
                  >
                    <div className="font-semibold text-purple-700">
                      3️⃣ 숙련자
                    </div>
                    <div className="text-sm text-purple-600">
                      경험이 많고, 핵심 기여나 아키텍처 이해를 원해요
                    </div>
                  </button>
                </div>
              )}
          </div>
        )}
      </div>
    </div>
  );
};

export default ChatMessage;
