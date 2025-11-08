import React from "react";
import { Search, Github, Star, TrendingUp, ArrowRight } from "lucide-react";

// 관련 프로젝트 섹션 컴포넌트
export const RelatedProjectsSection = ({
  projects = [],
  onAnalyzeProject,
  className = "",
}) => {
  if (!projects || projects.length === 0) return null;

  return (
    <div
      className={`mt-6 bg-white/40 backdrop-blur-sm rounded-2xl p-8 shadow-lg border border-white/60 ${className}`}
    >
      <div className="max-w-6xl mx-auto">
        {/* Section Header */}
        <div className="flex items-center gap-3 mb-6">
          <div className="w-10 h-10 bg-[#2563EB] rounded-lg flex items-center justify-center">
            <Search className="w-5 h-5 text-white" />
          </div>
          <div>
            <h3 className="text-2xl font-bold text-gray-900">
              Related Projects
            </h3>
            <p className="text-sm text-gray-600">
              Explore similar repositories you might be interested in
            </p>
          </div>
        </div>

        {/* Project Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {projects.slice(0, 4).map((project, index) => (
            <ProjectCard
              key={index}
              project={project}
              onAnalyze={onAnalyzeProject}
            />
          ))}
        </div>

        {/* View More Link (if more than 4 projects) */}
        {projects.length > 4 && (
          <div className="text-center mt-6">
            <button className="text-[#2563EB] hover:text-[#1E3A8A] font-semibold text-sm flex items-center gap-2 mx-auto">
              View {projects.length - 4} more related projects
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

const ProjectCard = ({ project, onAnalyze }) => {
  const healthScore = Math.round(project.similarity_score * 100);
  const scoreConfig = getScoreConfig(healthScore);

  return (
    <div className="bg-white/60 backdrop-blur-sm rounded-xl p-5 shadow-md hover:shadow-xl transition-all border border-white/60 group">
      {/* Repository Name */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <Github className="w-4 h-4 text-gray-400 flex-shrink-0" />
          <h4 className="text-base font-bold text-gray-900 truncate group-hover:text-[#2563EB] transition-colors">
            {project.name}
          </h4>
        </div>
      </div>

      {/* Score Badge */}
      <div
        className={`${scoreConfig.bg} rounded-lg px-3 py-2 mb-3 flex items-center justify-between`}
      >
        <span className={`text-xs font-semibold ${scoreConfig.color}`}>
          {scoreConfig.label}
        </span>
        <span className={`text-xl font-black ${scoreConfig.color}`}>
          {healthScore}
        </span>
      </div>

      {/* Description */}
      <p className="text-sm text-gray-600 line-clamp-2 mb-4 min-h-[40px]">
        {project.description || "No description available"}
      </p>

      {/* Stats */}
      <div className="flex items-center gap-3 mb-4 text-xs text-gray-500">
        <div className="flex items-center gap-1">
          <Star className="w-3 h-3 text-yellow-500" />
          <span className="font-semibold text-gray-700">
            {formatNumber(project.stars || 0)}
          </span>
        </div>
        <div className="flex items-center gap-1">
          <TrendingUp className="w-3 h-3 text-green-500" />
          <span className="font-semibold text-gray-700">
            {Math.round(project.similarity_score * 100)}% match
          </span>
        </div>
      </div>

      {/* Action Button */}
      <a
        href={project.url}
        target="_blank"
        rel="noopener noreferrer"
        onClick={(e) => {
          if (onAnalyze) {
            e.preventDefault();
            onAnalyze(project.url);
          }
        }}
        className="w-full inline-flex items-center justify-center gap-2 bg-[#2563EB] text-white px-4 py-2.5 rounded-lg text-sm font-semibold hover:bg-[#1E3A8A] transition-all group-hover:shadow-lg"
      >
        <span>Analyze</span>
        <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
      </a>
    </div>
  );
};

const getScoreConfig = (score) => {
  if (score >= 80)
    return {
      color: "text-green-600",
      bg: "bg-green-50",
      label: "Excellent",
    };
  if (score >= 60)
    return {
      color: "text-yellow-600",
      bg: "bg-yellow-50",
      label: "Good",
    };
  return {
    color: "text-red-600",
    bg: "bg-red-50",
    label: "Fair",
  };
};

const formatNumber = (num) => {
  if (num >= 1000) return (num / 1000).toFixed(1) + "k";
  return num;
};

export default RelatedProjectsSection;
