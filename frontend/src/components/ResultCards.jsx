import React, { useState } from 'react';
import { 
  Shield, AlertTriangle, CheckCircle, Clock, 
  Star, GitFork, Users, Calendar, Send,
  ExternalLink, Activity, Code, TrendingUp, Github, FileText, Zap, Search, ArrowRight, ArrowUp
} from 'lucide-react';

const ResultCards = ({ 
  analysisResult, 
  onCreateMilestone, 
  onSendReport, 
  isCreatingMilestone,
  isSendingReport 
}) => {
  const [selectedActions, setSelectedActions] = useState([]);

  if (!analysisResult) return null;

  let { score, risks, actions, similar, readme_summary, analysis } = analysisResult;
  
  // risks가 문자열 배열인 경우 객체 배열로 변환
  if (risks && risks.length > 0 && typeof risks[0] === 'string') {
    risks = risks.map((riskStr, index) => ({
      id: index + 1,
      type: 'general',
      severity: 'medium',
      description: riskStr
    }));
  }

  const toggleAction = (actionId) => {
    setSelectedActions(prev =>
      prev.includes(actionId)
        ? prev.filter(id => id !== actionId)
        : [...prev, actionId]
    );
  };

  const handleCreateMilestone = () => {
    if (selectedActions.length > 0) {
      onCreateMilestone(selectedActions, analysis);
    }
  };

  // Status badge configuration
  const getStatusConfig = (score) => {
    if (score >= 80) return { 
      label: 'Excellent', 
      color: 'bg-green-500', 
      textColor: 'text-green-700',
      bgColor: 'bg-green-50',
      borderColor: 'border-green-200',
      icon: CheckCircle
    };
    if (score >= 60) return { 
      label: 'Good', 
      color: 'bg-yellow-500',
      textColor: 'text-yellow-700',
      bgColor: 'bg-yellow-50',
      borderColor: 'border-yellow-200',
      icon: AlertTriangle
    };
    return { 
      label: 'Needs Attention', 
      color: 'bg-red-500',
      textColor: 'text-red-700',
      bgColor: 'bg-red-50',
      borderColor: 'border-red-200',
      icon: AlertTriangle
    };
  };

  const statusConfig = getStatusConfig(score);
  const StatusIcon = statusConfig.icon;

  // Extract repository name
  const repoName = analysis?.repo_name || 'Repository';

  return (
    <section className="py-16 bg-[#F9FAFB] animate-fadeIn">
      <div className="container mx-auto px-4">
        <div className="max-w-7xl mx-auto animate-slideUp">
          
          {/* Section Title */}
          <div className="text-center mb-12">
            <div className="inline-flex items-center gap-3 bg-gradient-to-r from-[#2563EB] to-[#1E3A8A] px-6 py-3 rounded-2xl shadow-lg mb-4">
              <CheckCircle className="w-6 h-6 text-white" />
              <span className="text-white font-bold text-lg">분석 완료</span>
            </div>
            <h2 className="text-4xl md:text-5xl font-black text-[#1E3A8A] mb-4">
              분석 결과 리포트
            </h2>
            <p className="text-lg text-slate-600">
              AI가 프로젝트를 종합적으로 분석한 결과입니다
            </p>
          </div>

          {/* ========== MAIN LAYOUT: 2 COLUMNS ========== */}
          <div className="bg-white/40 backdrop-blur-sm rounded-3xl shadow-2xl p-8 border border-white/60">
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
              
              {/* ========== LEFT: HEALTH SCORE CARD ========== */}
              <div className="lg:col-span-4">
                <div className="bg-gradient-to-br from-[#4F46E5] to-[#6366F1] rounded-2xl p-8 h-full shadow-xl">
                  <div className="flex items-center gap-3 mb-6">
                    <div className="w-12 h-12 bg-white/20 rounded-xl flex items-center justify-center">
                      <TrendingUp className="w-6 h-6 text-white" />
                    </div>
                    <div>
                      <h3 className="text-white font-bold text-lg">프로젝트 분석</h3>
                      <p className="text-indigo-200 text-sm">Health Score</p>
                    </div>
                  </div>
                  
                  <div className="bg-white rounded-2xl p-6 text-center mb-6">
                    <div className="text-7xl font-black text-indigo-600 mb-3">{score}</div>
                    <div className="text-gray-600 text-sm font-semibold mb-4">종합 점수</div>
                    <div className="h-3 bg-gray-100 rounded-full overflow-hidden">
                      <div 
                        className={`h-full bg-gradient-to-r ${statusConfig.color} rounded-full transition-all duration-1000`}
                        style={{width: `${score}%`}}
                      ></div>
                    </div>
                  </div>
                  
                  <div className={`${statusConfig.bgColor} ${statusConfig.borderColor} border-2 px-4 py-3 rounded-xl flex items-center gap-2 justify-center`}>
                    <StatusIcon className={`w-5 h-5 ${statusConfig.textColor}`} />
                    <span className={`${statusConfig.textColor} font-bold`}>{statusConfig.label}</span>
                  </div>
                </div>
              </div>

              {/* ========== RIGHT: REPOSITORY STATISTICS ========== */}
              <div className="lg:col-span-8">
                <h2 className="text-2xl font-black text-gray-900 mb-6">Repository Statistics</h2>
                
                {/* Stats Grid */}
                <div className="grid grid-cols-3 gap-4 mb-8">
                  <div className="bg-gradient-to-br from-yellow-50 to-orange-50 rounded-2xl p-5 border border-yellow-200">
                    <Star className="w-6 h-6 text-yellow-500 mb-2" />
                    <div className="text-3xl font-bold text-gray-900 mb-1">
                      {analysis?.stars || 0}
                    </div>
                    <div className="text-sm text-gray-600">GitHub Stars</div>
                  </div>
                  <div className="bg-gradient-to-br from-cyan-50 to-blue-50 rounded-2xl p-5 border border-cyan-200">
                    <GitFork className="w-6 h-6 text-cyan-600 mb-2" />
                    <div className="text-3xl font-bold text-gray-900 mb-1">
                      {analysis?.forks || 0}
                    </div>
                    <div className="text-sm text-gray-600">Forks</div>
                  </div>
                  <div className="bg-gradient-to-br from-purple-50 to-pink-50 rounded-2xl p-5 border border-purple-200">
                    <Users className="w-6 h-6 text-purple-600 mb-2" />
                    <div className="text-3xl font-bold text-gray-900 mb-1">
                      {analysis?.contributors || 0}
                    </div>
                    <div className="text-sm text-gray-600">Contributors</div>
                  </div>
                </div>

                {/* Metric Bars */}
                <div className="space-y-5">
                  {/* Security */}
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <Shield className="w-5 h-5 text-green-600" />
                        <span className="font-bold text-gray-900">보안 점수</span>
                      </div>
                      <span className="text-lg font-bold text-green-600">85%</span>
                    </div>
                    <div className="h-3 bg-gray-100 rounded-full overflow-hidden">
                      <div className="h-full bg-gradient-to-r from-green-400 to-emerald-500 rounded-full" style={{width: '85%'}}></div>
                    </div>
                  </div>

                  {/* Code Quality */}
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <Code className="w-5 h-5 text-blue-600" />
                        <span className="font-bold text-gray-900">코드 품질</span>
                      </div>
                      <span className="text-lg font-bold text-blue-600">92%</span>
                    </div>
                    <div className="h-3 bg-gray-100 rounded-full overflow-hidden">
                      <div className="h-full bg-gradient-to-r from-blue-400 to-indigo-500 rounded-full" style={{width: '92%'}}></div>
                    </div>
                  </div>

                  {/* Activity */}
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <Activity className="w-5 h-5 text-purple-600" />
                        <span className="font-bold text-gray-900">커뮤니티 활성도</span>
                      </div>
                      <span className="text-lg font-bold text-purple-600">78%</span>
                    </div>
                    <div className="h-3 bg-gray-100 rounded-full overflow-hidden">
                      <div className="h-full bg-gradient-to-r from-purple-400 to-pink-500 rounded-full" style={{width: '78%'}}></div>
                    </div>
                  </div>
                </div>
              </div>

            </div>
          </div>

          {/* README Summary */}
          {readme_summary && (
            <div className="bg-white/40 backdrop-blur-sm rounded-2xl shadow-lg p-6 mt-6 border border-white/60">
              <h3 className="font-bold text-gray-900 mb-3 flex items-center gap-2 text-lg">
                <FileText className="w-5 h-5 text-indigo-600" />
                README Summary
              </h3>
              <div className="text-sm text-gray-700 leading-relaxed">
                {readme_summary}
              </div>
            </div>
          )}

          {/* ========== ACTION AREA ========== */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
            
            {/* LEFT: Detected Risks */}
            <div className="bg-white/40 backdrop-blur-sm rounded-2xl shadow-lg overflow-hidden border border-white/60">
              <div className="bg-gradient-to-r from-yellow-50 to-orange-50 px-6 py-4 border-b border-yellow-100">
                <h3 className="text-xl font-black text-gray-900 flex items-center gap-2">
                  <AlertTriangle className="w-5 h-5 text-[#F59E0B]" />
                  Detected Risks
                </h3>
                <p className="text-sm text-gray-600 mt-1">{risks?.length || 0} issues found</p>
              </div>
              
              <div className="p-6 space-y-3 max-h-96 overflow-y-auto">
                {risks && risks.length > 0 ? risks.map((risk) => {
                  const severityColors = {
                    high: 'border-red-500 bg-red-50',
                    medium: 'border-yellow-500 bg-yellow-50',
                    low: 'border-blue-500 bg-blue-50'
                  };
                  const severityBadges = {
                    high: 'bg-red-500 text-white',
                    medium: 'bg-yellow-500 text-white',
                    low: 'bg-blue-500 text-white'
                  };
                  
                  return (
                    <div key={risk.id} className={`rounded-xl p-4 border-l-4 ${severityColors[risk.severity]}`}>
                      <div className="flex items-start justify-between mb-2">
                        <span className={`text-xs px-3 py-1 rounded-full font-bold ${severityBadges[risk.severity]}`}>
                          {risk.severity.toUpperCase()}
                        </span>
                        <span className="text-xs text-gray-500 flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          2 days ago
                        </span>
                      </div>
                      <p className="text-sm font-medium text-gray-900">{risk.description}</p>
                      <div className="text-xs text-gray-500 mt-2">Type: {risk.type}</div>
                    </div>
                  );
                }) : (
                  <p className="text-center text-gray-500 py-8">No risks detected</p>
                )}
              </div>
            </div>

            {/* RIGHT: Recommended Contributions */}
            <div className="bg-white/40 backdrop-blur-sm rounded-2xl shadow-lg overflow-hidden border border-white/60">
              <div className="bg-gradient-to-r from-green-50 to-emerald-50 px-6 py-4 border-b border-green-100">
                <h3 className="text-xl font-black text-gray-900 flex items-center gap-2">
                  <CheckCircle className="w-5 h-5 text-[#10B981]" />
                  Recommended Contributions
                </h3>
                <p className="text-sm text-gray-600 mt-1">{actions?.length || 0} tasks available</p>
              </div>
              
              <div className="p-6 space-y-3 max-h-96 overflow-y-auto">
                {actions && actions.length > 0 ? actions.map((action) => {
                  const priorityColors = {
                    high: 'border-red-500 bg-red-50',
                    medium: 'border-yellow-500 bg-yellow-50',
                    low: 'border-green-500 bg-green-50'
                  };
                  const priorityBadges = {
                    high: 'bg-red-500 text-white',
                    medium: 'bg-yellow-500 text-white',
                    low: 'bg-green-500 text-white'
                  };
                  
                  return (
                    <div 
                      key={action.id} 
                      className={`rounded-xl p-4 border-l-4 transition-all cursor-pointer ${priorityColors[action.priority]} ${
                        selectedActions.includes(action.id) ? 'ring-2 ring-[#2563EB]' : ''
                      }`}
                      onClick={() => toggleAction(action.id)}
                    >
                      <div className="flex items-start justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <input
                            type="checkbox"
                            checked={selectedActions.includes(action.id)}
                            onChange={() => toggleAction(action.id)}
                            className="w-4 h-4 rounded text-[#2563EB] focus:ring-[#2563EB]"
                          />
                          <span className={`text-xs px-3 py-1 rounded-full font-bold ${priorityBadges[action.priority]}`}>
                            {action.priority.toUpperCase()}
                          </span>
                        </div>
                        <span className="text-xs text-gray-500 flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          {action.duration}
                        </span>
                      </div>
                      <h4 className="text-sm font-bold text-gray-900 mb-1">{action.title}</h4>
                      <p className="text-xs text-gray-600">{action.description}</p>
                    </div>
                  );
                }) : (
                  <p className="text-center text-gray-500 py-8">No recommendations available</p>
                )}
              </div>
              
              {selectedActions.length > 0 && (
                <div className="bg-[#2563EB] px-6 py-3 text-center">
                  <p className="text-white font-bold text-sm">
                    ✓ {selectedActions.length} task{selectedActions.length > 1 ? 's' : ''} selected
                  </p>
                </div>
              )}
            </div>

          </div>

          {/* CTA Buttons */}
          <div className="flex flex-col sm:flex-row gap-4 justify-center pt-4 mt-6">
            <button
              onClick={() => window.open('#', '_blank')}
              className="inline-flex items-center justify-center gap-2 bg-white/60 backdrop-blur-sm text-indigo-600 border-2 border-indigo-300 px-8 py-4 rounded-xl font-bold text-base hover:bg-indigo-600 hover:text-white transition-all shadow-lg"
            >
              <ExternalLink className="w-5 h-5" />
              View Full Report
            </button>
            <button
              onClick={handleCreateMilestone}
              disabled={selectedActions.length === 0 || isCreatingMilestone}
              className="inline-flex items-center justify-center gap-2 bg-gradient-to-r from-green-500 to-emerald-500 text-white px-8 py-4 rounded-xl font-bold text-base hover:from-green-600 hover:to-emerald-600 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-lg"
            >
              <Calendar className="w-5 h-5" />
              {isCreatingMilestone ? 'Creating...' : 'Contribute Now with Kakao'}
            </button>
          </div>

          {/* ========== RELATED PROJECTS SECTION ========== */}
          {similar && similar.length > 0 && (
            <div className="mt-6 bg-white/40 backdrop-blur-sm rounded-2xl p-8 shadow-lg border border-white/60">
              <div className="max-w-6xl mx-auto">
                {/* Section Header */}
                <div className="flex items-center gap-3 mb-6">
                  <div className="w-10 h-10 bg-[#2563EB] rounded-lg flex items-center justify-center">
                    <Search className="w-5 h-5 text-white" />
                  </div>
                  <div>
                    <h3 className="text-2xl font-bold text-gray-900">Related Projects</h3>
                    <p className="text-sm text-gray-600">Explore similar repositories you might be interested in</p>
                  </div>
                </div>

                {/* Project Cards Grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                  {similar.slice(0, 4).map((repo, index) => {
                    // Calculate health score from similarity
                    const healthScore = Math.round(repo.similarity_score * 100);
                    const scoreConfig = healthScore >= 80 ? { 
                      color: 'text-green-600', 
                      bg: 'bg-green-50',
                      label: 'Excellent'
                    } : healthScore >= 60 ? { 
                      color: 'text-yellow-600', 
                      bg: 'bg-yellow-50',
                      label: 'Good'
                    } : { 
                      color: 'text-red-600', 
                      bg: 'bg-red-50',
                      label: 'Fair'
                    };

                    return (
                      <div 
                        key={index} 
                        className="bg-white/60 backdrop-blur-sm rounded-xl p-5 shadow-md hover:shadow-xl transition-all border border-white/60 group"
                      >
                        {/* Repository Name */}
                        <div className="flex items-start justify-between mb-3">
                          <div className="flex items-center gap-2">
                            <Github className="w-4 h-4 text-gray-400 flex-shrink-0" />
                            <h4 className="text-base font-bold text-gray-900 truncate group-hover:text-[#2563EB] transition-colors">
                              {repo.name}
                            </h4>
                          </div>
                        </div>

                        {/* Health Score Badge */}
                        <div className={`${scoreConfig.bg} rounded-lg px-3 py-2 mb-3 flex items-center justify-between`}>
                          <span className={`text-xs font-semibold ${scoreConfig.color}`}>
                            {scoreConfig.label}
                          </span>
                          <span className={`text-xl font-black ${scoreConfig.color}`}>
                            {healthScore}
                          </span>
                        </div>

                        {/* Description */}
                        <p className="text-sm text-gray-600 line-clamp-2 mb-4 min-h-[40px]">
                          {repo.description || 'No description available'}
                        </p>

                        {/* Stats */}
                        <div className="flex items-center gap-3 mb-4 text-xs text-gray-500">
                          <div className="flex items-center gap-1">
                            <Star className="w-3 h-3 text-yellow-500" />
                            <span className="font-semibold text-gray-700">
                              {repo.stars ? (repo.stars >= 1000 ? (repo.stars / 1000).toFixed(1) + 'k' : repo.stars) : '0'}
                            </span>
                          </div>
                          <div className="flex items-center gap-1">
                            <TrendingUp className="w-3 h-3 text-green-500" />
                            <span className="font-semibold text-gray-700">
                              {Math.round(repo.similarity_score * 100)}% match
                            </span>
                          </div>
                        </div>

                        {/* Action Button */}
                        <a
                          href={repo.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="w-full inline-flex items-center justify-center gap-2 bg-[#2563EB] text-white px-4 py-2.5 rounded-lg text-sm font-semibold hover:bg-[#1E3A8A] transition-all group-hover:shadow-lg"
                        >
                          <span>Analyze</span>
                          <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                        </a>
                      </div>
                    );
                  })}
                </div>

                {/* View More Link (if more than 4 projects) */}
                {similar.length > 4 && (
                  <div className="text-center mt-6">
                    <button className="text-[#2563EB] hover:text-[#1E3A8A] font-semibold text-sm flex items-center gap-2 mx-auto">
                      View {similar.length - 4} more related projects
                      <ArrowRight className="w-4 h-4" />
                    </button>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Back to Top / New Analysis Button */}
          <div className="mt-12 text-center">
            <button
              onClick={() => {
                document.getElementById('analyze')?.scrollIntoView({ behavior: 'smooth' });
              }}
              className="inline-flex items-center gap-3 bg-gradient-to-r from-[#2563EB] to-[#1E3A8A] text-white px-10 py-4 rounded-2xl font-bold text-lg hover:shadow-2xl hover:scale-105 transition-all duration-300"
            >
              <ArrowUp className="w-6 h-6" />
              <span>새로운 프로젝트 분석하기</span>
            </button>
            <p className="text-sm text-gray-500 mt-4">
              다른 오픈소스 프로젝트를 분석하고 싶으신가요?
            </p>
          </div>

        </div>
      </div>
    </section>
  );
};

export default ResultCards;
