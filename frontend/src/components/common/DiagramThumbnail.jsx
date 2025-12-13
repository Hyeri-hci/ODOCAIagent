import React, { useState, useRef, useCallback, useEffect } from "react";
import {
  Image,
  ZoomIn,
  ZoomOut,
  Download,
  Maximize2,
  Move,
  X,
  Maximize,
} from "lucide-react";
import MermaidDiagram from "./MermaidDiagram";

/**
 * 채팅창에서 다이어그램을 썸네일로 표시하는 컴포넌트
 * 클릭하면 모달로 확대 표시 + zoom 기능 + PNG 내보내기
 */
const DiagramThumbnail = ({
  mermaidCode,
  asciiTree,
  title = "코드 구조",
  className = "",
}) => {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [activeTab, setActiveTab] = useState(mermaidCode ? "diagram" : "tree");
  const [zoomLevel, setZoomLevel] = useState(0.6); // 초기값은 fitToScreen에서 계산됨
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const diagramRef = useRef(null);
  const containerRef = useRef(null);
  const initialFitDone = useRef(false); // 초기 fit 완료 플래그

  // 다이어그램이나 트리가 없으면 렌더링하지 않음
  if (!mermaidCode && !asciiTree) {
    return null;
  }

  // 화면에 맞게 줌 조절 (Fit to Screen) - 수동 호출용
  const fitToScreen = useCallback(() => {
    if (!diagramRef.current || !containerRef.current) return;

    const svg = diagramRef.current.querySelector("svg");
    if (!svg) return;

    // SVG의 원본 크기 가져오기 (viewBox 또는 width/height 속성 사용)
    const viewBox = svg.getAttribute("viewBox");
    let svgWidth, svgHeight;

    if (viewBox) {
      const parts = viewBox.split(" ");
      svgWidth = parseFloat(parts[2]) || svg.getBoundingClientRect().width;
      svgHeight = parseFloat(parts[3]) || svg.getBoundingClientRect().height;
    } else {
      svgWidth =
        parseFloat(svg.getAttribute("width")) ||
        svg.getBoundingClientRect().width;
      svgHeight =
        parseFloat(svg.getAttribute("height")) ||
        svg.getBoundingClientRect().height;
    }

    const containerRect = containerRef.current.getBoundingClientRect();

    // 컨테이너에 맞는 줌 레벨 계산 (여백 최소화하여 크게 보기)
    const padding = 40;
    const scaleX = (containerRect.width - padding * 2) / svgWidth;
    const scaleY = (containerRect.height - padding * 2) / svgHeight;
    // 최대 200%까지 허용하여 더 크게 표시
    const newZoom = Math.min(scaleX, scaleY, 2.0);

    setZoomLevel(Math.max(0.5, newZoom));
    setPosition({ x: 0, y: 0 });
  }, []); // 의존성 없음 - 수동 호출만

  // 초기 다이어그램 로드 시 한 번만 fitToScreen 실행
  const handleDiagramLoad = useCallback(() => {
    if (!initialFitDone.current) {
      initialFitDone.current = true;
      // DOM 업데이트 후 실행
      setTimeout(() => {
        fitToScreen();
      }, 150);
    }
  }, [fitToScreen]);

  // 모달 열기/닫기 핸들러
  const handleOpenModal = () => {
    initialFitDone.current = false; // 리셋하여 다시 열릴 때 fitToScreen 실행
    setZoomLevel(1.0); // 초기 줌 레벨 100%로 설정
    setPosition({ x: 0, y: 0 });
    setIsModalOpen(true);
  };

  const handleCloseModal = () => {
    setIsModalOpen(false);
  };

  // Zoom 기능
  const handleZoomIn = () => setZoomLevel((prev) => Math.min(prev + 0.1, 3));
  const handleZoomOut = () => setZoomLevel((prev) => Math.max(prev - 0.1, 0.2));
  const handleZoomReset = () => {
    fitToScreen();
  };

  // 드래그 이벤트
  const handleMouseDown = (e) => {
    if (zoomLevel > 1) {
      setIsDragging(true);
      setDragStart({ x: e.clientX - position.x, y: e.clientY - position.y });
    }
  };
  const handleMouseMove = (e) => {
    if (isDragging) {
      setPosition({ x: e.clientX - dragStart.x, y: e.clientY - dragStart.y });
    }
  };
  const handleMouseUp = () => setIsDragging(false);

  // SVG 내보내기 (PNG는 CORS 문제로 SVG로 변경)
  const handleExportSVG = useCallback(() => {
    const svgElement = diagramRef.current?.querySelector("svg");
    if (!svgElement) {
      alert("다이어그램을 찾을 수 없습니다.");
      return;
    }

    try {
      // SVG 복제 및 스타일 인라인화
      const clonedSvg = svgElement.cloneNode(true);
      clonedSvg.setAttribute("xmlns", "http://www.w3.org/2000/svg");

      // 배경색 추가
      const rect = document.createElementNS(
        "http://www.w3.org/2000/svg",
        "rect"
      );
      rect.setAttribute("width", "100%");
      rect.setAttribute("height", "100%");
      rect.setAttribute("fill", "#ffffff");
      clonedSvg.insertBefore(rect, clonedSvg.firstChild);

      const svgData = new XMLSerializer().serializeToString(clonedSvg);
      const svgBlob = new Blob([svgData], {
        type: "image/svg+xml;charset=utf-8",
      });
      const url = URL.createObjectURL(svgBlob);

      const link = document.createElement("a");
      link.href = url;
      link.download = `${title.replace(/[/\\:*?"<>|]/g, "_")}_diagram.svg`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error("SVG 내보내기 실패:", error);
      alert("SVG 내보내기에 실패했습니다.");
    }
  }, [title]);

  return (
    <>
      {/* 썸네일 카드 */}
      <div
        className={`group relative inline-block cursor-pointer ${className}`}
        onClick={handleOpenModal}
      >
        <div className="flex items-center gap-2 px-3 py-2 bg-gradient-to-r from-indigo-50 to-purple-50 dark:from-indigo-900/30 dark:to-purple-900/30 border border-indigo-200 dark:border-indigo-700 rounded-lg hover:shadow-md transition-all">
          <div className="p-1.5 bg-indigo-100 dark:bg-indigo-800 rounded">
            <Image className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
          </div>
          <div className="flex-1">
            <p className="text-sm font-medium text-indigo-700 dark:text-indigo-300">
              {title}
            </p>
            <p className="text-xs text-indigo-500 dark:text-indigo-400">
              클릭하여 확대 보기
            </p>
          </div>
          <Maximize2 className="w-4 h-4 text-indigo-400 group-hover:text-indigo-600 transition-colors" />
        </div>
      </div>

      {/* 확대 모달 (전체화면에 가깝게) */}
      {isModalOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-2"
          onClick={handleCloseModal}
        >
          <div
            className="relative w-[95vw] h-[95vh] bg-white dark:bg-gray-800 rounded-xl shadow-2xl overflow-hidden flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            {/* 모달 헤더 */}
            <div className="flex items-center justify-between p-3 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-indigo-100 dark:bg-indigo-800 rounded-lg">
                  <Image className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
                </div>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                  {title}
                </h3>
              </div>

              {/* 컨트롤 버튼들 */}
              <div className="flex items-center gap-2">
                {/* Zoom 컨트롤 */}
                {activeTab === "diagram" && (
                  <div className="flex items-center gap-1 bg-gray-100 dark:bg-gray-700 rounded-lg p-1">
                    <button
                      onClick={handleZoomOut}
                      className="p-1.5 hover:bg-gray-200 dark:hover:bg-gray-600 rounded transition-colors"
                      title="축소"
                    >
                      <ZoomOut className="w-4 h-4 text-gray-600 dark:text-gray-300" />
                    </button>
                    <span className="px-2 text-sm font-medium text-gray-600 dark:text-gray-300 min-w-[50px] text-center">
                      {Math.round(zoomLevel * 100)}%
                    </span>
                    <button
                      onClick={handleZoomIn}
                      className="p-1.5 hover:bg-gray-200 dark:hover:bg-gray-600 rounded transition-colors"
                      title="확대"
                    >
                      <ZoomIn className="w-4 h-4 text-gray-600 dark:text-gray-300" />
                    </button>
                    <div className="w-px h-4 bg-gray-300 dark:bg-gray-600 mx-1" />
                    <button
                      onClick={fitToScreen}
                      className="p-1.5 hover:bg-gray-200 dark:hover:bg-gray-600 rounded transition-colors"
                      title="화면에 맞추기"
                    >
                      <Maximize className="w-4 h-4 text-gray-600 dark:text-gray-300" />
                    </button>
                  </div>
                )}

                {/* SVG 내보내기 */}
                {activeTab === "diagram" && mermaidCode && (
                  <button
                    onClick={handleExportSVG}
                    className="flex items-center gap-1.5 px-3 py-1.5 bg-indigo-100 dark:bg-indigo-800 text-indigo-700 dark:text-indigo-300 rounded-lg hover:bg-indigo-200 dark:hover:bg-indigo-700 transition-colors text-sm font-medium"
                    title="SVG로 내보내기"
                  >
                    <Download className="w-4 h-4" />
                    SVG
                  </button>
                )}

                {/* 탭 버튼 */}
                {mermaidCode && asciiTree && (
                  <div className="flex bg-gray-100 dark:bg-gray-700 rounded-lg p-1">
                    <button
                      onClick={() => setActiveTab("diagram")}
                      className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
                        activeTab === "diagram"
                          ? "bg-white dark:bg-gray-600 text-indigo-600 dark:text-indigo-400 shadow-sm"
                          : "text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white"
                      }`}
                    >
                      다이어그램
                    </button>
                    <button
                      onClick={() => setActiveTab("tree")}
                      className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
                        activeTab === "tree"
                          ? "bg-white dark:bg-gray-600 text-indigo-600 dark:text-indigo-400 shadow-sm"
                          : "text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white"
                      }`}
                    >
                      트리 구조
                    </button>
                  </div>
                )}

                <button
                  onClick={handleCloseModal}
                  className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
                >
                  <X className="w-5 h-5 text-gray-500" />
                </button>
              </div>
            </div>

            {/* 모달 콘텐츠 - overflow-auto로 내부 스크롤 우선 */}
            <div
              ref={containerRef}
              className="flex-1 overflow-auto bg-gray-50 dark:bg-gray-900 flex items-center justify-center min-h-0"
              onMouseDown={handleMouseDown}
              onMouseMove={handleMouseMove}
              onMouseUp={handleMouseUp}
              onMouseLeave={handleMouseUp}
              style={{ cursor: isDragging ? "grabbing" : "grab" }}
            >
              {activeTab === "diagram" && mermaidCode ? (
                <div
                  ref={diagramRef}
                  className="flex items-center justify-center p-8"
                  style={{
                    transform: `translate(${position.x}px, ${position.y}px) scale(${zoomLevel})`,
                    transformOrigin: "center center",
                    transition: isDragging ? "none" : "transform 0.2s ease-out",
                    minWidth: "fit-content",
                    minHeight: "fit-content",
                  }}
                >
                  <MermaidDiagram
                    code={mermaidCode}
                    showExpandButton={false}
                    className=""
                    onLoad={handleDiagramLoad}
                  />
                </div>
              ) : (
                <pre className="p-6 bg-gray-900 text-green-400 rounded-lg overflow-auto text-sm font-mono whitespace-pre leading-relaxed max-h-full w-full">
                  {asciiTree || "트리 구조가 없습니다."}
                </pre>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default DiagramThumbnail;
