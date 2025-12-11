import { useState, useEffect, useCallback } from "react";
import { listActiveSessions, getSessionInfo } from "../lib/api";

// localStorage 키
const SESSION_STORAGE_KEY = "odoc_session_id";
const SESSION_REPO_KEY = "odoc_session_repo";

/**
 * 세션 관리 Hook
 * - localStorage에 세션 ID와 저장소 정보 저장
 * - 페이지 새로고침 시 세션 복원
 *
 * @returns {Object} 세션 상태 및 관리 함수
 */
export const useSessionManagement = () => {
  // 초기 세션 ID를 localStorage에서 복원
  const [sessionId, setSessionIdState] = useState(() => {
    try {
      return localStorage.getItem(SESSION_STORAGE_KEY) || null;
    } catch {
      return null;
    }
  });

  // 현재 세션의 저장소 정보
  const [sessionRepo, setSessionRepoState] = useState(() => {
    try {
      const stored = localStorage.getItem(SESSION_REPO_KEY);
      return stored ? JSON.parse(stored) : null;
    } catch {
      return null;
    }
  });

  const [showSessionHistory, setShowSessionHistory] = useState(false);
  const [sessionList, setSessionList] = useState([]);

  // 세션 ID 설정 시 localStorage에도 저장
  const setSessionId = useCallback((newSessionId) => {
    setSessionIdState(newSessionId);
    try {
      if (newSessionId) {
        localStorage.setItem(SESSION_STORAGE_KEY, newSessionId);
        console.log("[Session] Saved to localStorage:", newSessionId);
      } else {
        localStorage.removeItem(SESSION_STORAGE_KEY);
        console.log("[Session] Cleared from localStorage");
      }
    } catch (error) {
      console.warn("[Session] Failed to save to localStorage:", error);
    }
  }, []);

  // 저장소 정보 설정 시 localStorage에도 저장
  const setSessionRepo = useCallback((repo) => {
    setSessionRepoState(repo);
    try {
      if (repo) {
        localStorage.setItem(SESSION_REPO_KEY, JSON.stringify(repo));
        console.log("[Session] Repo saved:", repo);
      } else {
        localStorage.removeItem(SESSION_REPO_KEY);
      }
    } catch (error) {
      console.warn("[Session] Failed to save repo:", error);
    }
  }, []);

  // 세션 초기화 (새 대화 시작)
  const clearSession = useCallback(() => {
    setSessionId(null);
    setSessionRepo(null);
  }, [setSessionId, setSessionRepo]);

  const toggleSessionHistory = async () => {
    if (!showSessionHistory) {
      try {
        const response = await listActiveSessions();
        setSessionList(response.sessions || []);
      } catch (error) {
        console.error("세션 목록 가져오기 실패:", error);
        setSessionList([]);
      }
    }
    setShowSessionHistory(!showSessionHistory);
  };

  const switchToSession = async (newSessionId) => {
    try {
      const sessionInfo = await getSessionInfo(newSessionId);
      setSessionId(newSessionId);

      // 세션의 저장소 정보도 복원
      const context = sessionInfo.accumulated_context || {};
      if (context.last_mentioned_repo) {
        setSessionRepo(context.last_mentioned_repo);
      }

      console.log("세션 전환:", sessionInfo);
      setShowSessionHistory(false);
    } catch (error) {
      console.error("세션 전환 실패:", error);
    }
  };

  return {
    sessionId,
    setSessionId,
    sessionRepo,
    setSessionRepo,
    clearSession,
    showSessionHistory,
    setShowSessionHistory,
    sessionList,
    setSessionList,
    toggleSessionHistory,
    switchToSession,
  };
};
