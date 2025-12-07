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
} from "lucide-react";

/**
 * 온보딩 플랜 UI 컴포넌트
 *
 * 주차별 목표와 태스크를 타임라인 형식으로 표시합니다.
 *
 * @param {Object} props
 * @param {Array} props.plan - 온보딩 플랜 배열 [{week, goals, tasks}, ...]
 * @param {Object} props.userProfile - 사용자 프로필 정보
 * @param {Function} props.onTaskToggle - 태스크 완료 상태 변경 콜백
 */
const OnboardingPlanSection = ({ plan, userProfile, onTaskToggle }) => {
  const [expandedWeeks, setExpandedWeeks] = useState(() => {
    // 첫 번째 주만 기본 확장
    return plan && plan.length > 0 ? { 1: true } : {};
  });

  const [completedTasks, setCompletedTasks] = useState({});
  const [isCollapsed, setIsCollapsed] = useState(false);

  if (!plan || plan.length === 0) {
    return null;
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
    <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
      {/* 헤더 */}
      <div
        className="bg-gradient-to-r from-indigo-600 to-purple-600 p-6 cursor-pointer"
        onClick={() => setIsCollapsed(!isCollapsed)}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-white/20 rounded-xl flex items-center justify-center">
              <Rocket className="w-6 h-6 text-white" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-white">온보딩 플랜</h2>
              <p className="text-indigo-200 text-sm">
                {userProfile?.experienceLevel || "초보"} 수준을 위한{" "}
                {plan.length}주 학습 계획
              </p>
            </div>
          </div>

          <div className="flex items-center gap-4">
            {/* 전체 진행률 */}
            <div className="text-right mr-4">
              <div className="text-2xl font-bold text-white">
                {totalProgress}%
              </div>
              <div className="text-indigo-200 text-xs">전체 진행률</div>
            </div>

            {/* 확장/축소 버튼 */}
            <button className="w-10 h-10 bg-white/20 rounded-lg flex items-center justify-center hover:bg-white/30 transition-colors">
              {isCollapsed ? (
                <ChevronDown className="w-5 h-5 text-white" />
              ) : (
                <ChevronUp className="w-5 h-5 text-white" />
              )}
            </button>
          </div>
        </div>

        {/* 전체 진행률 바 */}
        <div className="mt-4 h-2 bg-white/20 rounded-full overflow-hidden">
          <div
            className="h-full bg-white rounded-full transition-all duration-500"
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
                  <div key={weekNum} className="relative pl-16">
                    {/* 타임라인 노드 */}
                    <div
                      className={`absolute left-0 w-12 h-12 rounded-full bg-gradient-to-br ${theme.bg} ${theme.border} border-2 flex items-center justify-center shadow-sm`}
                    >
                      <WeekIcon className={`w-5 h-5 ${theme.accent}`} />
                    </div>

                    {/* 주차 카드 */}
                    <div
                      className={`bg-gradient-to-br ${theme.bg} ${theme.border} border rounded-xl overflow-hidden`}
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
                                    typeof task === "object" ? task.url : null;

                                  return (
                                    <div
                                      key={taskIdx}
                                      className={`flex items-start gap-3 p-2 rounded-lg cursor-pointer transition-colors ${
                                        isCompleted
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
                                        className={`text-sm flex-1 ${
                                          isCompleted
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
  );
};

export default OnboardingPlanSection;
