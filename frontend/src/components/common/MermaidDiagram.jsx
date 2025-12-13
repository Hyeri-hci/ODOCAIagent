import React, { useEffect, useRef, useState, useCallback } from "react";
import mermaid from "mermaid";
import { AlertCircle, RefreshCw, ZoomIn, X, Maximize2 } from "lucide-react";

// Mermaid 초기화 설정
mermaid.initialize({
  startOnLoad: false,
  theme: "default",
  securityLevel: "loose",
  // 다이어그램이 컨테이너에 맞추지 않고 원래 크기로 렌더링되도록 설정
  flowchart: {
    useMaxWidth: false, // 컨테이너 크기에 제한받지 않음
    htmlLabels: true,
    curve: "basis",
    padding: 20,
    nodeSpacing: 50,
    rankSpacing: 50,
  },
  themeVariables: {
    primaryColor: "#818cf8",
    primaryTextColor: "#1f2937",
    primaryBorderColor: "#6366f1",
    lineColor: "#9ca3af",
    secondaryColor: "#fef3c7",
    tertiaryColor: "#dbeafe",
    fontSize: "14px",
  },
});

/**
 * Mermaid 다이어그램 문법 검증 및 수정
 * @param {string} code - 원본 Mermaid 코드
 * @returns {{ isValid: boolean, code: string, error: string | null }}
 */
const validateAndFixMermaid = async (code) => {
  if (!code || typeof code !== "string") {
    return { isValid: false, code: "", error: "다이어그램 코드가 없습니다." };
  }

  let fixedCode = code.trim();

  // 기본 수정 사항들
  const fixes = [
    // 1. graph 키워드가 없으면 추가
    {
      check: () =>
        !fixedCode.match(
          /^(graph|flowchart|sequenceDiagram|classDiagram|stateDiagram|erDiagram|gantt|pie|mindmap)/m
        ),
      fix: () => {
        fixedCode = `graph TD\n${fixedCode}`;
      },
    },
    // 2. 특수문자가 있는 노드 이름을 따옴표로 감싸기
    {
      check: () => fixedCode.includes("/") && !fixedCode.includes('"'),
      fix: () => {
        fixedCode = fixedCode.replace(/\[([^\]]*\/[^\]]*)\]/g, '["$1"]');
      },
    },
    // 3. 한글이 포함된 노드 처리
    {
      check: () => /[\uAC00-\uD7AF]/.test(fixedCode),
      fix: () => {
        // 한글 노드를 따옴표로 감싸기
        fixedCode = fixedCode.replace(
          /\[([^\]]*[\uAC00-\uD7AF][^\]]*)\]/g,
          '["$1"]'
        );
      },
    },
    // 4. 빈 줄 제거
    {
      check: () => fixedCode.includes("\n\n\n"),
      fix: () => {
        fixedCode = fixedCode.replace(/\n{3,}/g, "\n\n");
      },
    },
  ];

  // 수정 적용
  for (const { check, fix } of fixes) {
    if (check()) {
      fix();
    }
  }

  // Mermaid 문법 검증
  try {
    await mermaid.parse(fixedCode);
    return { isValid: true, code: fixedCode, error: null };
  } catch (parseError) {
    // 파싱 오류 시 추가 수정 시도
    console.warn(
      "[Mermaid] Parse error, attempting fixes:",
      parseError.message
    );

    // 일반적인 오류 패턴 수정
    const errorFixes = [
      // 화살표 형식 수정
      () => fixedCode.replace(/-->/g, " --> ").replace(/  +/g, " "),
      // 노드 ID에 특수문자 제거 (알파벳, 숫자, 밑줄만 허용)
      () =>
        fixedCode.replace(/([A-Za-z0-9_]+)[^A-Za-z0-9_\[\]\-\>\"\s]/g, "$1"),
      // subgraph 문법 수정
      () => fixedCode.replace(/subgraph\s+([^\n\[]+)\n/g, "subgraph $1\n"),
    ];

    for (const applyFix of errorFixes) {
      const attemptCode = applyFix();
      try {
        await mermaid.parse(attemptCode);
        return { isValid: true, code: attemptCode, error: null };
      } catch {
        // 계속 시도
      }
    }

    return {
      isValid: false,
      code: fixedCode,
      error: `다이어그램 문법 오류: ${parseError.message}`,
    };
  }
};

/**
 * Mermaid 다이어그램 렌더링 컴포넌트
 */
const MermaidDiagram = ({
  code,
  className = "",
  showExpandButton = true,
  onError = null,
  onLoad = null, // 렌더링 완료 콜백
}) => {
  const containerRef = useRef(null);
  const [renderState, setRenderState] = useState({
    status: "idle", // idle, loading, success, error
    error: null,
    svg: null,
    validatedCode: null,
  });
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [retryCount, setRetryCount] = useState(0);

  const renderDiagram = useCallback(async () => {
    if (!code) {
      setRenderState({
        status: "error",
        error: "다이어그램 코드가 없습니다.",
        svg: null,
        validatedCode: null,
      });
      return;
    }

    setRenderState((prev) => ({ ...prev, status: "loading" }));

    try {
      // 1단계: 검증 및 수정
      const validation = await validateAndFixMermaid(code);

      if (!validation.isValid) {
        setRenderState({
          status: "error",
          error: validation.error,
          svg: null,
          validatedCode: validation.code,
        });
        if (onError) onError(validation.error);
        return;
      }

      // 2단계: 렌더링
      const id = `mermaid-${Date.now()}-${Math.random()
        .toString(36)
        .substr(2, 9)}`;
      const { svg } = await mermaid.render(id, validation.code);

      setRenderState({
        status: "success",
        error: null,
        svg,
        validatedCode: validation.code,
      });

      // 렌더링 완료 콜백 호출 (약간의 지연 후 DOM이 업데이트된 다음)
      if (onLoad) {
        setTimeout(() => onLoad(), 100);
      }
    } catch (renderError) {
      console.error("[Mermaid] Render error:", renderError);
      setRenderState({
        status: "error",
        error: `렌더링 실패: ${renderError.message}`,
        svg: null,
        validatedCode: code,
      });
      if (onError) onError(renderError.message);
    }
  }, [code, onError, onLoad]);

  useEffect(() => {
    renderDiagram();
  }, [renderDiagram, retryCount]);

  const handleRetry = () => {
    setRetryCount((prev) => prev + 1);
  };

  // 로딩 상태
  if (renderState.status === "loading") {
    return (
      <div
        className={`flex items-center justify-center p-8 bg-gray-50 dark:bg-gray-800 rounded-lg ${className}`}
      >
        <div className="flex items-center gap-3 text-gray-500 dark:text-gray-400">
          <RefreshCw className="w-5 h-5 animate-spin" />
          <span>다이어그램 생성 중...</span>
        </div>
      </div>
    );
  }

  // 에러 상태
  if (renderState.status === "error") {
    return (
      <div
        className={`p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg ${className}`}
      >
        <div className="flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <p className="text-sm text-red-700 dark:text-red-400 font-medium">
              다이어그램을 표시할 수 없습니다
            </p>
            <p className="text-xs text-red-600 dark:text-red-500 mt-1">
              {renderState.error}
            </p>
            <button
              onClick={handleRetry}
              className="mt-2 flex items-center gap-1 text-xs text-red-600 dark:text-red-400 hover:text-red-800 dark:hover:text-red-300"
            >
              <RefreshCw className="w-3 h-3" />
              다시 시도
            </button>
          </div>
        </div>
        {/* 원본 코드 표시 (디버깅용) */}
        {renderState.validatedCode && (
          <details className="mt-3">
            <summary className="text-xs text-red-500 cursor-pointer">
              원본 코드 보기
            </summary>
            <pre className="mt-2 p-2 bg-gray-900 text-gray-300 rounded text-xs overflow-x-auto max-h-32">
              {renderState.validatedCode}
            </pre>
          </details>
        )}
      </div>
    );
  }

  // 성공 상태
  return (
    <>
      <div
        ref={containerRef}
        className={`relative bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden ${className}`}
      >
        {/* 다이어그램 */}
        <div
          className="p-4 overflow-auto max-h-96"
          dangerouslySetInnerHTML={{ __html: renderState.svg }}
        />

        {/* 확대 버튼 */}
        {showExpandButton && (
          <button
            onClick={() => setIsModalOpen(true)}
            className="absolute top-2 right-2 p-1.5 bg-white/80 dark:bg-gray-700/80 hover:bg-white dark:hover:bg-gray-700 rounded-lg shadow-sm border border-gray-200 dark:border-gray-600 transition-colors"
            title="확대해서 보기"
          >
            <Maximize2 className="w-4 h-4 text-gray-600 dark:text-gray-300" />
          </button>
        )}
      </div>

      {/* 확대 모달 */}
      {isModalOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
          onClick={() => setIsModalOpen(false)}
        >
          <div
            className="relative max-w-[90vw] max-h-[90vh] bg-white dark:bg-gray-800 rounded-xl shadow-2xl overflow-auto"
            onClick={(e) => e.stopPropagation()}
          >
            {/* 모달 헤더 */}
            <div className="sticky top-0 flex items-center justify-between p-3 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
              <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                코드 구조 다이어그램
              </span>
              <button
                onClick={() => setIsModalOpen(false)}
                className="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
              >
                <X className="w-5 h-5 text-gray-500" />
              </button>
            </div>

            {/* 다이어그램 (확대) */}
            <div
              className="p-6"
              dangerouslySetInnerHTML={{ __html: renderState.svg }}
            />
          </div>
        </div>
      )}
    </>
  );
};

export default MermaidDiagram;
