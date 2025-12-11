import React from "react";

/**
 * 스켈레톤 로딩 컴포넌트
 * 분석 결과 로딩 중 표시되는 플레이스홀더
 */

// 기본 스켈레톤 박스
const SkeletonBox = ({ className = "" }) => (
  <div
    className={`bg-gray-200 dark:bg-gray-700 rounded animate-pulse ${className}`}
  />
);

// 점수 카드 스켈레톤
export const ScoreCardSkeleton = () => (
  <div className="bg-gray-800 rounded-xl p-6 h-full">
    <div className="flex items-center gap-3 mb-5">
      <SkeletonBox className="w-10 h-10 rounded-lg !bg-gray-700" />
      <div className="space-y-2">
        <SkeletonBox className="w-24 h-4 !bg-gray-700" />
        <SkeletonBox className="w-16 h-3 !bg-gray-700" />
      </div>
    </div>
    <div className="bg-white rounded-xl p-5 text-center mb-5">
      <SkeletonBox className="w-20 h-14 mx-auto mb-2" />
      <SkeletonBox className="w-16 h-3 mx-auto mb-3" />
      <SkeletonBox className="w-full h-2" />
    </div>
    <SkeletonBox className="w-full h-10 rounded-lg !bg-gray-700" />
  </div>
);

// 통계 카드 스켈레톤
export const StatCardSkeleton = () => (
  <div className="bg-gray-50 dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700">
    <SkeletonBox className="w-5 h-5 mb-2" />
    <SkeletonBox className="w-16 h-6 mb-1" />
    <SkeletonBox className="w-20 h-3" />
  </div>
);

// 메트릭 바 스켈레톤
export const MetricBarSkeleton = () => (
  <div className="space-y-1.5">
    <div className="flex items-center justify-between">
      <SkeletonBox className="w-20 h-4" />
      <SkeletonBox className="w-12 h-4" />
    </div>
    <SkeletonBox className="w-full h-2 rounded-full" />
  </div>
);

// 섹션 카드 스켈레톤
export const SectionCardSkeleton = ({ hasSubtitle = false }) => (
  <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
    <div className="px-5 py-4 border-b border-gray-100 dark:border-gray-700">
      <div className="flex items-center gap-2">
        <SkeletonBox className="w-5 h-5" />
        <div className="space-y-1.5">
          <SkeletonBox className="w-32 h-5" />
          {hasSubtitle && <SkeletonBox className="w-24 h-3" />}
        </div>
      </div>
    </div>
    <div className="p-5 space-y-3">
      <SkeletonBox className="w-full h-4" />
      <SkeletonBox className="w-4/5 h-4" />
      <SkeletonBox className="w-3/5 h-4" />
    </div>
  </div>
);

// 리스트 아이템 스켈레톤
export const ListItemSkeleton = () => (
  <div className="p-4 bg-gray-50 dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
    <div className="flex items-start gap-3">
      <SkeletonBox className="w-8 h-5 rounded" />
      <div className="flex-1 space-y-2">
        <SkeletonBox className="w-3/4 h-4" />
        <SkeletonBox className="w-full h-3" />
        <SkeletonBox className="w-2/3 h-3" />
      </div>
    </div>
  </div>
);

// 전체 분석 리포트 스켈레톤
export const AnalysisReportSkeleton = () => (
  <div className="space-y-4">
    {/* 편집 버튼 스켈레톤 */}
    <div className="flex justify-end">
      <SkeletonBox className="w-28 h-8 rounded-lg" />
    </div>

    {/* 온보딩 플랜 스켈레톤 */}
    <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
      <div className="bg-gray-800 p-5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <SkeletonBox className="w-10 h-10 rounded-lg !bg-gray-700" />
            <div className="space-y-2">
              <SkeletonBox className="w-24 h-4 !bg-gray-700" />
              <SkeletonBox className="w-16 h-3 !bg-gray-700" />
            </div>
          </div>
          <SkeletonBox className="w-16 h-8 rounded-lg !bg-gray-700" />
        </div>
      </div>
    </div>

    {/* 메인 분석 카드 스켈레톤 */}
    <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5">
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <div className="lg:col-span-4">
          <ScoreCardSkeleton />
        </div>
        <div className="lg:col-span-8 space-y-4">
          <SkeletonBox className="w-48 h-6 mb-4" />
          <div className="grid grid-cols-3 gap-3">
            <StatCardSkeleton />
            <StatCardSkeleton />
            <StatCardSkeleton />
          </div>
          <div className="space-y-3">
            <MetricBarSkeleton />
            <MetricBarSkeleton />
            <MetricBarSkeleton />
          </div>
        </div>
      </div>
    </div>

    {/* 추가 섹션 스켈레톤 */}
    <SectionCardSkeleton hasSubtitle />
    <SectionCardSkeleton hasSubtitle />

    {/* 리스트 섹션 스켈레톤 */}
    <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
      <div className="px-5 py-4 border-b border-gray-100 dark:border-gray-700">
        <div className="flex items-center gap-2">
          <SkeletonBox className="w-5 h-5" />
          <SkeletonBox className="w-32 h-5" />
        </div>
      </div>
      <div className="p-5 space-y-3">
        <ListItemSkeleton />
        <ListItemSkeleton />
        <ListItemSkeleton />
      </div>
    </div>
  </div>
);

export default AnalysisReportSkeleton;
