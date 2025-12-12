import React, { useState } from "react";
import {
  Calendar,
  Target,
  CheckCircle2,
  Circle,
  ChevronDown,
  ChevronUp,
  Rocket,
  BookOpen,
  Code,
  Users,
  GitPullRequest,
  ExternalLink,
  Loader2,
  Sparkles,
  X,
  GraduationCap,
  Briefcase,
  Trophy,
  RefreshCw,
} from "lucide-react";

// 난이도 옵션 정의
const DIFFICULTY_OPTIONS = [
  {
    id: "beginner",
    label: "입문자",
    description: "프로그래밍을 막 시작했거나 이 기술 스택이 처음이에요",
    icon: GraduationCap,
    color: "bg-green-600",
    bgColor: "bg-green-50 border-green-200",
  },
  {
    id: "intermediate",
    label: "중급자",
    description: "기본 개념은 알고 있고, 실제 프로젝트 경험을 쌓고 싶어요",
    icon: Briefcase,
    color: "bg-blue-600",
    bgColor: "bg-blue-50 border-blue-200",
  },
  {
    id: "advanced",
    label: "숙련자",
    description: "경험이 많고, 핵심 기여나 아키텍처 이해를 원해요",
    icon: Trophy,
    color: "bg-purple-600",
    bgColor: "bg-purple-50 border-purple-200",
  },
];

/**
 * 난이도 선택 모달 컴포넌트
 */
const DifficultyModal = ({ isOpen, onClose, onSelect, isGenerating }) => {
  const [selectedDifficulty, setSelectedDifficulty] = useState("beginner");

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* 배경 오버레이 */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* 모달 콘텐츠 */}
      <div className="relative bg-white rounded-xl shadow-lg w-full max-w-lg mx-4 overflow-hidden">
        {/* 헤더 */}
        <div className="bg-gray-800 p-5">
          <button
            onClick={onClose}
            className="absolute top-4 right-4 text-gray-400 hover:text-white transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-gray-700 rounded-lg flex items-center justify-center">
              <Rocket className="w-5 h-5 text-gray-300" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white">
                온보딩 플랜 생성
              </h2>
              <p className="text-gray-400 text-sm">
                나에게 맞는 난이도를 선택하세요
              </p>
            </div>
          </div>
        </div>

        {/* 난이도 선택 */}
        <div className="p-6 space-y-3">
          {DIFFICULTY_OPTIONS.map((option) => {
            const Icon = option.icon;
            const isSelected = selectedDifficulty === option.id;

            return (
              <button
                key={option.id}
                onClick={() => setSelectedDifficulty(option.id)}
                className={`
                  w-full p-4 rounded-xl border-2 transition-all duration-200 text-left
                  ${isSelected
                    ? `${option.bgColor} border-2 ring-2 ring-offset-2 ring-indigo-500`
                    : "bg-gray-50 border-gray-200 hover:bg-gray-100"
                  }
                `}
              >
                <div className="flex items-start gap-4">
                  <div
                    className={`w-10 h-10 rounded-lg ${option.color} flex items-center justify-center flex-shrink-0`}
                  >
                    <Icon className="w-5 h-5 text-white" />
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-gray-800">
                        {option.label}
                      </span>
                      {isSelected && (
                        <CheckCircle2 className="w-5 h-5 text-indigo-600" />
                      )}
                    </div>
                    <p className="text-sm text-gray-600 mt-1">
                      {option.description}
                    </p>
                  </div>
                </div>
              </button>
            );
          })}
        </div>

        {/* 안내 메시지 */}
        <div className="px-6 pb-4">
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm text-amber-700">
            <strong>참고:</strong> 플랜은 한국어로 생성되며, 선택한 난이도에
            맞는 학습 목표와 태스크가 제공됩니다.
          </div>
        </div>

        {/* 버튼 */}
        <div className="p-6 pt-2 flex gap-3">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-3 rounded-xl border border-gray-300 text-gray-700 font-medium hover:bg-gray-50 transition-colors"
          >
            취소
          </button>
          <button
            onClick={() => onSelect(selectedDifficulty)}
            disabled={isGenerating}
            className={`
              flex-1 px-4 py-3 rounded-lg font-medium transition-colors
              ${isGenerating
                ? "bg-gray-100 text-gray-400 cursor-not-allowed"
                : "bg-gray-800 text-white hover:bg-gray-700"
              }
            `}
          >
            {isGenerating ? (
              <span className="flex items-center justify-center gap-2">
                <Loader2 className="w-5 h-5 animate-spin" />
                생성 중...
              </span>
            ) : (
              "플랜 생성하기"
            )}
          </button>
        </div>
      </div>
    </div>
  );
};

/**
 * 온보딩 플랜 UI 컴포넌트
 *
 * 주차별 목표와 태스크를 타임라인 형식으로 표시합니다.
 * plan이 없을 경우 "플랜 생성" 버튼을 표시합니다.
 *
 * @param {Object} props
 * @param {Array} props.plan - 온보딩 플랜 배열 [{week, goals, tasks}, ...]
 * @param {Object} props.userProfile - 사용자 프로필 정보
 * @param {Function} props.onTaskToggle - 태스크 완료 상태 변경 콜백
 * @param {Function} props.onGeneratePlan - 플랜 생성 버튼 클릭 콜백 (difficulty 파라미터 받음)
 * @param {boolean} props.isGenerating - 플랜 생성 중 여부
 * @param {string} props.generateError - 플랜 생성 오류 메시지
 */
const OnboardingPlanSection = ({
  plan,
  userProfile,
  onTaskToggle,
  onGeneratePlan,
  isGenerating = false,
  generateError = null,
}) => {
  const [expandedWeeks, setExpandedWeeks] = useState(() => {
    // 첫 번째 주만 기본 확장
    return plan && plan.length > 0 ? { 1: true } : {};
  });

  const [completedTasks, setCompletedTasks] = useState({});
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [showDifficultyModal, setShowDifficultyModal] = useState(false);

  // 난이도 선택 후 플랜 생성
  const handleDifficultySelect = (difficulty) => {
    if (onGeneratePlan) {
      onGeneratePlan(difficulty);
    }
    // 모달은 생성 완료 후 닫히도록 isGenerating 상태로 관리
  };

  // 생성 완료 시 모달 닫기
  React.useEffect(() => {
    if (!isGenerating && showDifficultyModal && plan && plan.length > 0) {
      setShowDifficultyModal(false);
    }
  }, [isGenerating, plan, showDifficultyModal]);

  // plan이 없는 경우 - 플랜 생성 버튼 표시
  if (!plan || plan.length === 0) {
    return (
      <>
        <DifficultyModal
          isOpen={showDifficultyModal}
          onClose={() => setShowDifficultyModal(false)}
          onSelect={handleDifficultySelect}
          isGenerating={isGenerating}
        />

        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="p-8">
            <div className="text-center max-w-md mx-auto">
              <div className="w-14 h-14 bg-gray-800 rounded-xl flex items-center justify-center mx-auto mb-4">
                <Rocket className="w-7 h-7 text-gray-300" />
              </div>
              <h3 className="text-lg font-semibold text-gray-800 mb-2">
                맞춤 온보딩 플랜
              </h3>
              <p className="text-gray-500 mb-6 text-sm">
                AI가 이 프로젝트와 당신의 경험 수준에 맞는
                <br />
                단계별 학습 계획을 생성합니다.
              </p>

              {generateError && (
                <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">
                  {generateError}
                </div>
              )}

              <button
                onClick={() => setShowDifficultyModal(true)}
                disabled={isGenerating}
                className={`
                  inline-flex items-center gap-2 px-5 py-2.5 rounded-lg font-medium
                  transition-colors
                  ${isGenerating
                    ? "bg-gray-100 text-gray-400 cursor-not-allowed"
                    : "bg-gray-800 text-white hover:bg-gray-700"
                  }
                `}
              >
                {isGenerating ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    <span>플랜 생성 중...</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-5 h-5" />
                    <span>온보딩 플랜 생성</span>
                  </>
                )}
              </button>

              {isGenerating && (
                <p className="mt-4 text-xs text-gray-500">
                  프로젝트 분석과 이슈 검토 중입니다. 잠시만 기다려주세요...
                </p>
              )}
            </div>
          </div>
        </div>
      </>
    );
  }

  const toggleWeek = (weekNum) => {
    setExpandedWeeks((prev) => ({
      ...prev,
      [weekNum]: !prev[weekNum],
    }));
  };

  const toggleTask = (weekNum, taskIndex) => {
    const key = `${weekNum}-${taskIndex}`;
    const newCompleted = !completedTasks[key];

    setCompletedTasks((prev) => ({
      ...prev,
      [key]: newCompleted,
    }));

    // 상위 컴포넌트에 알림
    if (onTaskToggle) {
      onTaskToggle(weekNum, taskIndex, newCompleted);
    }
  };

  const getWeekProgress = (weekNum, tasks) => {
    if (!tasks || tasks.length === 0) return 0;
    const completed = tasks.filter(
      (_, idx) => completedTasks[`${weekNum}-${idx}`]
    ).length;
    return Math.round((completed / tasks.length) * 100);
  };

  const getTotalProgress = () => {
    const allTasks = plan.flatMap((week, weekIdx) =>
      (week.tasks || []).map(
        (_, taskIdx) => `${week.week || weekIdx + 1}-${taskIdx}`
      )
    );
    if (allTasks.length === 0) return 0;
    const completed = allTasks.filter((key) => completedTasks[key]).length;
    return Math.round((completed / allTasks.length) * 100);
  };

  const getWeekIcon = (weekNum) => {
    const icons = {
      1: BookOpen,
      2: Code,
      3: GitPullRequest,
      4: Users,
    };
    return icons[weekNum] || Target;
  };

  const getWeekTheme = (weekNum) => {
    const themes = {
      1: {
        bg: "from-blue-50 to-indigo-50",
        border: "border-blue-200",
        accent: "text-blue-600",
        progress: "bg-blue-500",
      },
      2: {
        bg: "from-green-50 to-emerald-50",
        border: "border-green-200",
        accent: "text-green-600",
        progress: "bg-green-500",
      },
      3: {
        bg: "from-purple-50 to-violet-50",
        border: "border-purple-200",
        accent: "text-purple-600",
        progress: "bg-purple-500",
      },
      4: {
        bg: "from-orange-50 to-amber-50",
        border: "border-orange-200",
        accent: "text-orange-600",
        progress: "bg-orange-500",
      },
    };
    return themes[weekNum] || themes[1];
  };

  const totalProgress = getTotalProgress();

  return (
    <>
      <DifficultyModal
        isOpen={showDifficultyModal}
        onClose={() => setShowDifficultyModal(false)}
        onSelect={handleDifficultySelect}
        isGenerating={isGenerating}
      />

      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        {/* 헤더 */}
        <div
          className="bg-gray-800 p-5 cursor-pointer"
          onClick={() => setIsCollapsed(!isCollapsed)}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-gray-700 rounded-lg flex items-center justify-center">
                <Rocket className="w-5 h-5 text-gray-300" />
              </div>
              <div>
                <h2 className="text-base font-semibold text-white">
                  온보딩 플랜
                </h2>
                <p className="text-gray-400 text-sm">
                  {plan.length}주 학습 계획
                </p>
              </div>
            </div>

            <div className="flex items-center gap-4">
              {/* 다시 생성하기 버튼 */}
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  // 채팅에 메시지를 자동으로 보내서 새로운 온보딩 플랜 생성
                  if (onGeneratePlan) {
                    // 난이도 없이 기본 메시지 전송 (사용자가 원하면 직접 지정)
                    onGeneratePlan();
                  }
                }}
                disabled={isGenerating}
                className="flex items-center gap-2 px-3 py-1.5 bg-gray-700 hover:bg-gray-600 rounded-lg text-white text-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                title="새로운 온보딩 플랜을 생성합니다"
              >
                {isGenerating ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <RefreshCw className="w-4 h-4" />
                )}
                <span className="hidden sm:inline">다시 생성</span>
              </button>

              {/* 전체 진행률 */}
              <div className="text-right mr-3">
                <div className="text-xl font-semibold text-white">
                  {totalProgress}%
                </div>
                <div className="text-gray-400 text-xs">진행률</div>
              </div>

              {/* 확장/축소 버튼 */}
              <button className="w-8 h-8 bg-gray-700 rounded-lg flex items-center justify-center hover:bg-gray-600 transition-colors">
                {isCollapsed ? (
                  <ChevronDown className="w-4 h-4 text-gray-300" />
                ) : (
                  <ChevronUp className="w-4 h-4 text-gray-300" />
                )}
              </button>
            </div>
          </div>

          {/* 전체 진행률 바 */}
          <div className="mt-3 h-1.5 bg-gray-700 rounded-full overflow-hidden">
            <div
              className="h-full bg-blue-500 rounded-full transition-all duration-300"
              style={{ width: `${totalProgress}%` }}
            />
          </div>
        </div>

        {/* 타임라인 콘텐츠 */}
        {!isCollapsed && (
          <div className="p-6">
            <div className="relative">
              {/* 타임라인 세로선 */}
              <div className="absolute left-6 top-0 bottom-0 w-0.5 bg-gray-200" />

              {/* 주차별 카드 */}
              <div className="space-y-6">
                {plan.map((week, weekIdx) => {
                  const weekNum = week.week || weekIdx + 1;
                  const WeekIcon = getWeekIcon(weekNum);
                  const theme = getWeekTheme(weekNum);
                  const progress = getWeekProgress(weekNum, week.tasks);
                  const isExpanded = expandedWeeks[weekNum];

                  return (
                    <div key={weekNum} className="relative pl-14">
                      {/* 타임라인 노드 */}
                      <div
                        className={`absolute left-0 w-10 h-10 rounded-full bg-gray-100 border-2 border-gray-200 flex items-center justify-center`}
                      >
                        <WeekIcon className={`w-4 h-4 text-gray-600`} />
                      </div>

                      {/* 주차 카드 */}
                      <div
                        className={`bg-gray-50 border border-gray-200 rounded-lg overflow-hidden`}
                      >
                        {/* 주차 헤더 */}
                        <div
                          className="p-4 cursor-pointer hover:bg-white/50 transition-colors"
                          onClick={() => toggleWeek(weekNum)}
                        >
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3">
                              <div
                                className={`text-lg font-bold ${theme.accent}`}
                              >
                                Week {weekNum}
                              </div>
                              <div className="flex items-center gap-2 text-sm text-gray-600">
                                <Calendar className="w-4 h-4" />
                                <span>{week.goals?.length || 0}개 목표</span>
                                <span className="text-gray-400">•</span>
                                <span>{week.tasks?.length || 0}개 태스크</span>
                              </div>
                            </div>

                            <div className="flex items-center gap-3">
                              {/* 진행률 */}
                              <div className="flex items-center gap-2">
                                <div className="w-24 h-2 bg-white rounded-full overflow-hidden">
                                  <div
                                    className={`h-full ${theme.progress} rounded-full transition-all duration-300`}
                                    style={{ width: `${progress}%` }}
                                  />
                                </div>
                                <span
                                  className={`text-sm font-medium ${theme.accent}`}
                                >
                                  {progress}%
                                </span>
                              </div>

                              {/* 확장 버튼 */}
                              <button className="p-1">
                                {isExpanded ? (
                                  <ChevronUp className="w-5 h-5 text-gray-400" />
                                ) : (
                                  <ChevronDown className="w-5 h-5 text-gray-400" />
                                )}
                              </button>
                            </div>
                          </div>
                        </div>

                        {/* 확장된 콘텐츠 */}
                        {isExpanded && (
                          <div className="px-4 pb-4 space-y-4">
                            {/* 목표 섹션 */}
                            {week.goals && week.goals.length > 0 && (
                              <div>
                                <h4 className="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-2">
                                  <Target className="w-4 h-4" />
                                  이번 주 목표
                                </h4>
                                <div className="bg-white rounded-lg p-3 space-y-2">
                                  {week.goals.map((goal, goalIdx) => (
                                    <div
                                      key={goalIdx}
                                      className="flex items-start gap-2 text-sm text-gray-700"
                                    >
                                      <div
                                        className={`w-1.5 h-1.5 rounded-full ${theme.progress} mt-1.5 flex-shrink-0`}
                                      />
                                      <span>{goal}</span>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}

                            {/* 태스크 섹션 */}
                            {week.tasks && week.tasks.length > 0 && (
                              <div>
                                <h4 className="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-2">
                                  <CheckCircle2 className="w-4 h-4" />할 일 목록
                                </h4>
                                <div className="bg-white rounded-lg p-3 space-y-2">
                                  {week.tasks.map((task, taskIdx) => {
                                    const isCompleted =
                                      completedTasks[`${weekNum}-${taskIdx}`];
                                    const taskText =
                                      typeof task === "string"
                                        ? task
                                        : task.title ||
                                        task.description ||
                                        JSON.stringify(task);
                                    const taskUrl =
                                      typeof task === "object"
                                        ? task.url
                                        : null;

                                    return (
                                      <div
                                        key={taskIdx}
                                        className={`flex items-start gap-3 p-2 rounded-lg cursor-pointer transition-colors ${isCompleted
                                            ? "bg-green-50 border border-green-200"
                                            : "hover:bg-gray-50"
                                          }`}
                                        onClick={() =>
                                          toggleTask(weekNum, taskIdx)
                                        }
                                      >
                                        <button className="mt-0.5 flex-shrink-0">
                                          {isCompleted ? (
                                            <CheckCircle2 className="w-5 h-5 text-green-500" />
                                          ) : (
                                            <Circle className="w-5 h-5 text-gray-300" />
                                          )}
                                        </button>
                                        <span
                                          className={`text-sm flex-1 ${isCompleted
                                              ? "text-gray-500 line-through"
                                              : "text-gray-700"
                                            }`}
                                        >
                                          {taskText}
                                        </span>
                                        {taskUrl && (
                                          <a
                                            href={taskUrl}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="text-gray-400 hover:text-blue-500"
                                            onClick={(e) => e.stopPropagation()}
                                          >
                                            <ExternalLink className="w-4 h-4" />
                                          </a>
                                        )}
                                      </div>
                                    );
                                  })}
                                </div>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* 완료 메시지 */}
            {totalProgress === 100 && (
              <div className="mt-6 bg-gradient-to-r from-green-50 to-emerald-50 border border-green-200 rounded-xl p-4 flex items-center gap-4">
                <div className="w-12 h-12 bg-green-500 rounded-full flex items-center justify-center">
                  <CheckCircle2 className="w-6 h-6 text-white" />
                </div>
                <div>
                  <h3 className="font-bold text-green-800">축하합니다! 🎉</h3>
                  <p className="text-sm text-green-600">
                    온보딩 플랜을 모두 완료했습니다. 이제 본격적인 기여를
                    시작해보세요!
                  </p>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </>
  );
};

export default OnboardingPlanSection;
