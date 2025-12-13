import React, { useState } from "react";
import {
  Star,
  GitFork,
  TrendingUp,
  ExternalLink,
  ChevronDown,
  ChevronUp,
  Sparkles,
  Target,
  Award,
} from "lucide-react";

/**
 * 유사 프로젝트 추천 섹션
 * 진단 결과를 기반으로 유사한 오픈소스 프로젝트를 추천
 */
const SimilarProjectsSection = ({
  projects = [],
  isExpanded = true,
  onToggle,
}) => {
  const [selectedProject, setSelectedProject] = useState(null);

  if (!projects || projects.length === 0) {
    return null;
  }

  return (
    <div className="bg-white rounded-2xl shadow-lg overflow-hidden border border-gray-100">
      {/* 헤더 */}
      <button
        onClick={onToggle}
        className="w-full px-6 py-5 flex items-center justify-between hover:bg-gray-50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-gradient-to-br from-purple-500 to-pink-500 rounded-xl flex items-center justify-center">
            <Sparkles className="w-5 h-5 text-white" />
          </div>
          <div className="text-left">
            <h3 className="text-lg font-bold text-gray-900">
              유사 프로젝트 추천
            </h3>
            <p className="text-sm text-gray-500">
              {projects.length}개의 비슷한 프로젝트를 발견했습니다
            </p>
          </div>
        </div>
        {isExpanded ? (
          <ChevronUp className="w-5 h-5 text-gray-400" />
        ) : (
          <ChevronDown className="w-5 h-5 text-gray-400" />
        )}
      </button>

      {/* 컨텐츠 */}
      {isExpanded && (
        <div className="px-6 pb-6 space-y-4">
          {/* 프로젝트 카드 그리드 */}
          <div className="grid grid-cols-1 gap-4">
            {projects.map((project, index) => (
              <ProjectCard
                key={index}
                project={project}
                isSelected={selectedProject === index}
                onSelect={() =>
                  setSelectedProject(index === selectedProject ? null : index)
                }
              />
            ))}
          </div>

          {/* 안내 메시지 */}
          <div className="mt-6 p-4 bg-blue-50 border border-blue-200 rounded-xl">
            <div className="flex gap-3">
              <Target className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
              <div className="text-sm text-blue-900">
                <p className="font-medium mb-1">💡 추천 활용 팁</p>
                <p className="text-blue-700">
                  유사한 프로젝트를 탐색하여 다양한 접근 방식을 배우고, 커뮤니티
                  트렌드를 파악할 수 있습니다.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

/**
 * 개별 프로젝트 카드 컴포넌트
 */
const ProjectCard = ({ project, isSelected, onSelect }) => {
  const {
    owner,
    repo,
    full_name,
    description,
    match_score,
    similarity_score,
    health_score,
    onboarding_score,
    stars,
    reason,
    matched_stack = [],
    url,
  } = project;

  const matchScore = match_score || similarity_score || 0;
  const healthScore = health_score || 0;
  const onboardingScore = onboarding_score || 0;
  const repoUrl =
    url || `https://github.com/${owner || full_name}/${repo || ""}`;

  return (
    <div
      className={`
        border-2 rounded-xl p-5 transition-all cursor-pointer
        ${
          isSelected
            ? "border-purple-500 bg-purple-50/50 shadow-lg"
            : "border-gray-200 hover:border-purple-300 hover:shadow-md bg-white"
        }
      `}
      onClick={onSelect}
    >
      <div className="flex items-start justify-between gap-4">
        {/* 왼쪽: 프로젝트 정보 */}
        <div className="flex-1 min-w-0">
          {/* 제목 & 링크 */}
          <div className="flex items-center gap-2 mb-2">
            <a
              href={repoUrl}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="text-lg font-bold text-gray-900 hover:text-purple-600 transition-colors flex items-center gap-2 group"
            >
              <span className="truncate">
                {full_name || `${owner}/${repo}`}
              </span>
              <ExternalLink className="w-4 h-4 text-gray-400 group-hover:text-purple-600 flex-shrink-0" />
            </a>
          </div>

          {/* 설명 */}
          {description && (
            <p className="text-sm text-gray-600 mb-3 line-clamp-2">
              {description}
            </p>
          )}

          {/* 점수 배지 */}
          <div className="flex flex-wrap gap-2 mb-3">
            {/* 매칭 점수 */}
            <div
              className={`px-3 py-1 rounded-full text-xs font-medium flex items-center gap-1 ${getMatchBadgeColor(
                matchScore
              )}`}
            >
              <Award className="w-3 h-3" />
              매칭도 {Math.round(matchScore * 100)}%
            </div>

            {/* 건강도 점수 */}
            {healthScore > 0 && (
              <div
                className={`px-3 py-1 rounded-full text-xs font-medium border ${getScoreBadgeColor(
                  healthScore
                )}`}
              >
                건강도 {healthScore}점
              </div>
            )}

            {/* 온보딩 점수 */}
            {onboardingScore > 0 && (
              <div
                className={`px-3 py-1 rounded-full text-xs font-medium border ${getScoreBadgeColor(
                  onboardingScore
                )}`}
              >
                온보딩 {onboardingScore}점
              </div>
            )}
          </div>

          {/* 매칭 스택 */}
          {matched_stack && matched_stack.length > 0 && (
            <div className="flex flex-wrap gap-1 mb-3">
              {matched_stack.slice(0, 5).map((stack, idx) => (
                <span
                  key={idx}
                  className="px-2 py-0.5 bg-gray-100 text-gray-700 rounded text-xs"
                >
                  {stack}
                </span>
              ))}
              {matched_stack.length > 5 && (
                <span className="px-2 py-0.5 text-gray-500 text-xs">
                  +{matched_stack.length - 5}
                </span>
              )}
            </div>
          )}

          {/* GitHub 통계 */}
          {stars && (
            <div className="flex items-center gap-3 text-sm text-gray-600">
              <div className="flex items-center gap-1">
                <Star className="w-4 h-4 fill-yellow-400 text-yellow-400" />
                <span>{formatStars(stars)}</span>
              </div>
            </div>
          )}
        </div>

        {/* 오른쪽: 추천 이유 (확장 시) */}
        {isSelected && reason && (
          <div className="w-48 flex-shrink-0">
            <div className="p-3 bg-white border border-purple-200 rounded-lg">
              <p className="text-xs font-medium text-purple-900 mb-2">
                추천 이유:
              </p>
              <p className="text-xs text-purple-700 leading-relaxed">
                {reason}
              </p>
            </div>
          </div>
        )}
      </div>

      {/* 추천 이유 (접힌 상태 미리보기) */}
      {!isSelected && reason && (
        <div className="mt-3 pt-3 border-t border-gray-200">
          <p className="text-xs text-gray-600 line-clamp-2">
            <span className="font-medium text-gray-700">추천 이유:</span>{" "}
            {reason}
          </p>
        </div>
      )}
    </div>
  );
};

// 유틸리티 함수들

const getMatchBadgeColor = (score) => {
  if (score >= 0.8)
    return "bg-purple-100 text-purple-700 border border-purple-300";
  if (score >= 0.6) return "bg-blue-100 text-blue-700 border border-blue-300";
  return "bg-gray-100 text-gray-700 border border-gray-300";
};

const getScoreBadgeColor = (score) => {
  if (score >= 80) return "text-green-600 bg-green-50 border-green-200";
  if (score >= 60) return "text-yellow-600 bg-yellow-50 border-yellow-200";
  return "text-red-600 bg-red-50 border-red-200";
};

const formatStars = (stars) => {
  if (stars >= 1000) {
    return `${(stars / 1000).toFixed(1)}k`;
  }
  return stars.toString();
};

export default SimilarProjectsSection;
