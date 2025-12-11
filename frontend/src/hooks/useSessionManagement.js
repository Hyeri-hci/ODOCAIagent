import { useState } from "react";
import { listActiveSessions, getSessionInfo } from "../lib/api";

/**
 * 세션 관리 Hook
 *
 * @returns {Object} 세션 상태 및 관리 함수
 */
export const useSessionManagement = () => {
  const [sessionId, setSessionId] = useState(null);
  const [showSessionHistory, setShowSessionHistory] = useState(false);
  const [sessionList, setSessionList] = useState([]);

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
      console.log("세션 전환:", sessionInfo);
      setShowSessionHistory(false);
    } catch (error) {
      console.error("세션 전환 실패:", error);
    }
  };

  return {
    sessionId,
    setSessionId,
    showSessionHistory,
    setShowSessionHistory,
    sessionList,
    setSessionList,
    toggleSessionHistory,
    switchToSession,
  };
};
