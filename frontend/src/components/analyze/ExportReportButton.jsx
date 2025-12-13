import React, { useState } from "react";
import {
  Download,
  FileText,
  Shield,
  BookOpen,
  Check,
  X,
  Loader2,
} from "lucide-react";
import { exportReportMarkdown, downloadBlob } from "../../lib/api/analysis";

/**
 * 리포트 내보내기 버튼 컴포넌트
 */
const ExportReportButton = ({ analysisResult, className = "" }) => {
  const [isExporting, setIsExporting] = useState(false);
  const [showMenu, setShowMenu] = useState(false);
  const [exportStatus, setExportStatus] = useState(null); // 'success' | 'error' | null

  // 저장소 정보 추출
  const getRepoInfo = () => {
    if (!analysisResult?.repositoryUrl) return null;

    const match = analysisResult.repositoryUrl.match(
      /github\.com\/([^/]+)\/([^/]+)/
    );
    if (match) {
      return { owner: match[1], repo: match[2] };
    }
    return null;
  };

  const repoInfo = getRepoInfo();

  // 내보내기 가능한 리포트 유형 확인
  const availableReports = [];

  if (analysisResult?.summary || analysisResult?.technicalDetails) {
    availableReports.push({
      type: "diagnosis",
      label: "진단 리포트",
      icon: FileText,
      data: {
        health_score: analysisResult.summary?.score || 0,
        onboarding_score: analysisResult.technicalDetails?.onboardingScore || 0,
        docs_score: analysisResult.technicalDetails?.documentationQuality || 0,
        activity_score:
          analysisResult.technicalDetails?.activityMaintainability || 0,
        health_level: analysisResult.summary?.healthLevel || "",
        recommendations:
          analysisResult.recommendations?.map((r) => r.title) || [],
        warnings: analysisResult.risks?.map((r) => r.description) || [],
        key_findings:
          analysisResult.risks?.map((r) => ({
            title: r.type,
            description: r.description,
            severity: r.severity,
          })) || [],
      },
    });
  }

  if (analysisResult?.onboardingPlan) {
    // onboardingPlan이 배열이면 plan 키로 감싸기
    const planData = Array.isArray(analysisResult.onboardingPlan)
      ? {
          plan: analysisResult.onboardingPlan,
          summary: analysisResult.onboardingSummary || "",
        }
      : analysisResult.onboardingPlan;

    availableReports.push({
      type: "onboarding",
      label: "온보딩 가이드",
      icon: BookOpen,
      data: planData,
    });
  }

  // contributorGuide가 있고 markdown 필드가 있으면 추가 (contributor_guide 타입)
  if (analysisResult?.contributorGuide?.markdown) {
    availableReports.push({
      type: "onboarding",
      label: "기여 가이드",
      icon: BookOpen,
      data: {
        type: "contributor_guide",
        markdown: analysisResult.contributorGuide.markdown,
      },
    });
  }

  if (analysisResult?.security) {
    // security 데이터를 results 키로 감싸서 백엔드 형식에 맞추기
    const securityData = analysisResult.security.results
      ? analysisResult.security
      : { results: analysisResult.security };

    availableReports.push({
      type: "security",
      label: "보안 리포트",
      icon: Shield,
      data: securityData,
    });
  }

  const handleExport = async (report) => {
    if (!repoInfo) {
      setExportStatus("error");
      setTimeout(() => setExportStatus(null), 3000);
      return;
    }

    setIsExporting(true);
    setShowMenu(false);
    setExportStatus(null);

    try {
      const blob = await exportReportMarkdown(
        report.type,
        repoInfo.owner,
        repoInfo.repo,
        report.data,
        true
      );

      const filename = `${repoInfo.owner}_${repoInfo.repo}_${report.type}_report.md`;
      downloadBlob(blob, filename);

      setExportStatus("success");
      setTimeout(() => setExportStatus(null), 3000);
    } catch (error) {
      console.error("Export failed:", error);
      setExportStatus("error");
      setTimeout(() => setExportStatus(null), 3000);
    } finally {
      setIsExporting(false);
    }
  };

  // 내보낼 리포트가 없으면 렌더링하지 않음
  if (availableReports.length === 0 || !repoInfo) {
    return null;
  }

  return (
    <div className={`relative ${className}`}>
      {/* 메인 버튼 */}
      <button
        onClick={() => setShowMenu(!showMenu)}
        disabled={isExporting}
        className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-all ${
          exportStatus === "success"
            ? "bg-green-100 text-green-700 border border-green-300"
            : exportStatus === "error"
            ? "bg-red-100 text-red-700 border border-red-300"
            : "bg-white text-gray-700 border border-gray-300 hover:bg-gray-50 hover:border-gray-400"
        }`}
      >
        {isExporting ? (
          <>
            <Loader2 className="w-4 h-4 animate-spin" />
            내보내는 중...
          </>
        ) : exportStatus === "success" ? (
          <>
            <Check className="w-4 h-4" />
            다운로드 완료
          </>
        ) : exportStatus === "error" ? (
          <>
            <X className="w-4 h-4" />
            내보내기 실패
          </>
        ) : (
          <>
            <Download className="w-4 h-4" />
            리포트 내보내기
          </>
        )}
      </button>

      {/* 드롭다운 메뉴 */}
      {showMenu && !isExporting && (
        <>
          {/* 배경 클릭 시 닫기 */}
          <div
            className="fixed inset-0 z-40"
            onClick={() => setShowMenu(false)}
          />

          <div className="absolute right-0 mt-2 w-56 bg-white rounded-xl shadow-lg border border-gray-200 z-50 overflow-hidden">
            <div className="p-2 bg-gray-50 border-b border-gray-200">
              <p className="text-xs text-gray-500 font-medium">
                Markdown으로 저장
              </p>
            </div>

            <div className="p-1">
              {availableReports.map((report) => {
                const Icon = report.icon;
                return (
                  <button
                    key={report.type}
                    onClick={() => handleExport(report)}
                    className="w-full flex items-center gap-3 px-3 py-2.5 text-sm text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
                  >
                    <Icon className="w-4 h-4 text-gray-500" />
                    <span>{report.label}</span>
                  </button>
                );
              })}
            </div>

            {availableReports.length > 1 && (
              <>
                <div className="border-t border-gray-200" />
                <div className="p-1">
                  <button
                    onClick={() => {
                      // 모든 리포트 순차 다운로드
                      availableReports.forEach((report, index) => {
                        setTimeout(() => handleExport(report), index * 500);
                      });
                    }}
                    className="w-full flex items-center gap-3 px-3 py-2.5 text-sm text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors font-medium"
                  >
                    <Download className="w-4 h-4" />
                    <span>모두 다운로드</span>
                  </button>
                </div>
              </>
            )}
          </div>
        </>
      )}
    </div>
  );
};

export default ExportReportButton;
