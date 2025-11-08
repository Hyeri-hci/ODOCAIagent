import React from 'react';
import { Sparkles, ArrowRight, Zap, Shield, Target, TrendingUp, GitBranch, Users, Star, GitFork, Code, Activity, CheckCircle } from 'lucide-react';

const HeroSection = ({ onAnalyzeClick }) => {
  return (
    <section className="relative min-h-[55vh] flex items-center justify-center overflow-hidden bg-gradient-to-br from-[#2563EB] via-[#1E3A8A] to-[#0F172A]">
      {/* Animated Background Elements */}
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute top-0 left-0 w-full h-full opacity-30">
          <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-blue-400 rounded-full mix-blend-multiply filter blur-3xl animate-float"></div>
          <div className="absolute top-1/3 right-1/4 w-96 h-96 bg-indigo-400 rounded-full mix-blend-multiply filter blur-3xl animate-float" style={{animationDelay: '2s'}}></div>
          <div className="absolute bottom-1/4 left-1/3 w-96 h-96 bg-cyan-400 rounded-full mix-blend-multiply filter blur-3xl animate-float" style={{animationDelay: '4s'}}></div>
        </div>
        
        {/* Grid Pattern */}
        <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PGRlZnM+PHBhdHRlcm4gaWQ9ImdyaWQiIHdpZHRoPSI2MCIgaGVpZ2h0PSI2MCIgcGF0dGVyblVuaXRzPSJ1c2VyU3BhY2VPblVzZSI+PHBhdGggZD0iTSAxMCAwIEwgMCAwIDAgMTAiIGZpbGw9Im5vbmUiIHN0cm9rZT0id2hpdGUiIHN0cm9rZS13aWR0aD0iMC41IiBvcGFjaXR5PSIwLjEiLz48L3BhdHRlcm4+PC9kZWZzPjxyZWN0IHdpZHRoPSIxMDAlIiBoZWlnaHQ9IjEwMCUiIGZpbGw9InVybCgjZ3JpZCkiLz48L3N2Zz4=')] opacity-20"></div>
      </div>

      <div className="relative container mx-auto px-4 py-12">
        <div className="max-w-7xl mx-auto">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 items-center">
            
            {/* Left Content */}
            <div className="text-white space-y-5">
              {/* Badge */}
              <div className="inline-flex items-center gap-2 bg-white/10 backdrop-blur-md px-3 py-1.5 rounded-full border border-white/20">
                <Sparkles className="w-4 h-4 text-blue-200" />
                <span className="text-xs font-semibold">AI-Powered Open Source Analysis</span>
              </div>
              
              {/* Main Headline */}
              <h1 className="text-4xl md:text-5xl lg:text-6xl font-black leading-tight">
                오픈소스 기여,
                <br />
                <span className="bg-gradient-to-r from-blue-200 via-cyan-200 to-blue-300 bg-clip-text text-transparent">
                  이제 더 쉽게
                </span>
              </h1>
              
              {/* English Subtext */}
              <p className="text-lg text-blue-100 leading-relaxed">
                AI analyzes GitHub repositories instantly,
                <br />
                recommending the perfect contributions for you.
              </p>
              
              {/* Trust Badges */}
              <div className="flex flex-wrap gap-3 pt-2">
                <div className="flex items-center gap-2 bg-white/10 backdrop-blur-md px-3 py-1.5 rounded-lg border border-white/20">
                  <Shield className="w-4 h-4 text-green-300" />
                  <span className="text-xs font-semibold">CVE 보안 검출</span>
                </div>
                <div className="flex items-center gap-2 bg-white/10 backdrop-blur-md px-3 py-1.5 rounded-lg border border-white/20">
                  <Zap className="w-4 h-4 text-yellow-300" />
                  <span className="text-xs font-semibold">AI 분석</span>
                </div>
                <div className="flex items-center gap-2 bg-white/10 backdrop-blur-md px-3 py-1.5 rounded-lg border border-white/20">
                  <Target className="w-4 h-4 text-pink-300" />
                  <span className="text-xs font-semibold">맞춤형 기여 매칭</span>
                </div>
              </div>
              
              {/* CTA Button */}
              <div className="pt-3">
                <button
                  onClick={onAnalyzeClick}
                  className="group inline-flex items-center gap-2 bg-white text-blue-600 px-8 py-3.5 rounded-xl font-bold text-base hover:bg-blue-50 active:scale-95 transition-all duration-300 shadow-2xl hover:shadow-blue-500/50"
                >
                  <Sparkles className="w-5 h-5" />
                  <span>지금 바로 시작하기</span>
                  <ArrowRight className="w-5 h-5 group-hover:translate-x-2 transition-transform" />
                </button>
              </div>
            </div>

            {/* Right - AI Dashboard Mockup - Matching ResultCards Design */}
            <div className="hidden lg:block">
              <div className="bg-white/10 backdrop-blur-xl rounded-2xl p-6 border border-white/20 shadow-2xl">
                <div className="grid grid-cols-12 gap-4">
                  
                  {/* LEFT: HEALTH SCORE CARD (Same as ResultCards) */}
                  <div className="col-span-5">
                    <div className="bg-gradient-to-br from-[#4F46E5] to-[#6366F1] rounded-xl p-5 h-full shadow-xl">
                      <div className="flex items-center gap-2 mb-4">
                        <div className="w-8 h-8 bg-white/20 rounded-lg flex items-center justify-center">
                          <TrendingUp className="w-4 h-4 text-white" />
                        </div>
                        <div>
                          <h3 className="text-white font-bold text-sm">프로젝트 분석</h3>
                          <p className="text-indigo-200 text-xs">Health Score</p>
                        </div>
                      </div>
                      
                      <div className="bg-white rounded-xl p-4 text-center mb-4">
                        <div className="text-5xl font-black text-indigo-600 mb-2">92</div>
                        <div className="text-gray-600 text-xs font-semibold mb-3">종합 점수</div>
                        <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                          <div className="h-full bg-gradient-to-r from-green-400 to-emerald-500 rounded-full transition-all duration-1000" style={{width: '92%'}}></div>
                        </div>
                      </div>
                      
                      <div className="bg-green-50 border-2 border-green-200 px-3 py-2 rounded-lg flex items-center gap-2 justify-center">
                        <CheckCircle className="w-4 h-4 text-green-700" />
                        <span className="text-green-700 font-bold text-xs">Excellent</span>
                      </div>
                    </div>
                  </div>

                  {/* RIGHT: REPOSITORY STATISTICS (Same as ResultCards) */}
                  <div className="col-span-7">
                    <h3 className="text-sm font-black text-white mb-3">Repository Statistics</h3>
                    
                    {/* Stats Grid */}
                    <div className="grid grid-cols-3 gap-2 mb-4">
                      <div className="bg-gradient-to-br from-yellow-50 to-orange-50 rounded-lg p-3 border border-yellow-200">
                        <Star className="w-4 h-4 text-yellow-500 mb-1" />
                        <div className="text-xl font-bold text-gray-900">182k</div>
                        <div className="text-xs text-gray-600">Stars</div>
                      </div>
                      <div className="bg-gradient-to-br from-cyan-50 to-blue-50 rounded-lg p-3 border border-cyan-200">
                        <GitFork className="w-4 h-4 text-cyan-600 mb-1" />
                        <div className="text-xl font-bold text-gray-900">12k</div>
                        <div className="text-xs text-gray-600">Forks</div>
                      </div>
                      <div className="bg-gradient-to-br from-purple-50 to-pink-50 rounded-lg p-3 border border-purple-200">
                        <Users className="w-4 h-4 text-purple-600 mb-1" />
                        <div className="text-xl font-bold text-gray-900">4.2k</div>
                        <div className="text-xs text-gray-600">Contributors</div>
                      </div>
                    </div>

                    {/* Metric Bars */}
                    <div className="space-y-3">
                      {/* Security */}
                      <div>
                        <div className="flex items-center justify-between mb-1">
                          <div className="flex items-center gap-1">
                            <Shield className="w-3 h-3 text-green-600" />
                            <span className="font-bold text-white text-xs">보안 점수</span>
                          </div>
                          <span className="text-xs font-bold text-green-400">85%</span>
                        </div>
                        <div className="h-2 bg-white/10 rounded-full overflow-hidden">
                          <div className="h-full bg-gradient-to-r from-green-400 to-emerald-500 rounded-full" style={{width: '85%'}}></div>
                        </div>
                      </div>

                      {/* Code Quality */}
                      <div>
                        <div className="flex items-center justify-between mb-1">
                          <div className="flex items-center gap-1">
                            <Code className="w-3 h-3 text-blue-600" />
                            <span className="font-bold text-white text-xs">코드 품질</span>
                          </div>
                          <span className="text-xs font-bold text-blue-400">92%</span>
                        </div>
                        <div className="h-2 bg-white/10 rounded-full overflow-hidden">
                          <div className="h-full bg-gradient-to-r from-blue-400 to-indigo-500 rounded-full" style={{width: '92%'}}></div>
                        </div>
                      </div>

                      {/* Activity */}
                      <div>
                        <div className="flex items-center justify-between mb-1">
                          <div className="flex items-center gap-1">
                            <Activity className="w-3 h-3 text-purple-600" />
                            <span className="font-bold text-white text-xs">커뮤니티 활성도</span>
                          </div>
                          <span className="text-xs font-bold text-purple-400">78%</span>
                        </div>
                        <div className="h-2 bg-white/10 rounded-full overflow-hidden">
                          <div className="h-full bg-gradient-to-r from-purple-400 to-pink-500 rounded-full" style={{width: '78%'}}></div>
                        </div>
                      </div>
                    </div>
                  </div>

                </div>

                {/* Action Button */}
                <button className="w-full mt-4 bg-gradient-to-r from-blue-500 to-cyan-500 text-white py-2.5 rounded-lg text-sm font-semibold hover:shadow-lg transition-all">
                  기여 작업 추천받기
                </button>
              </div>
            </div>

          </div>
        </div>
      </div>
    </section>
  );
};

export default HeroSection;
