import api, { API_BASE_URL } from "./client";

// ============ Chat API (V2 - 세션 기반) ============

/**
 * 채팅 메시지 전송 (세션 기반)
 * @param {string} message - 사용자 메시지
 * @param {string} sessionId - 세션 ID (선택사항, 없으면 새 세션 생성)
 * @param {string} owner - 저장소 소유자
 * @param {string} repo - 저장소 이름
 * @returns {Promise<{session_id, answer, context, suggestions, trace}>}
 */
export const sendChatMessageV2 = async (
  message,
  sessionId = null,
  owner = "unknown",
  repo = "unknown"
) => {
  try {
    const response = await api.post("/api/chat/", {
      message,
      session_id: sessionId,
      owner,
      repo,
      metadata: {},
    });
    return response.data;
  } catch (error) {
    console.error("Chat message failed:", error);
    throw error;
  }
};

/**
 * 스트리밍 채팅 메시지 전송 (SSE with POST)
 * @param {string} message - 사용자 메시지
 * @param {string} sessionId - 세션 ID (선택사항)
 * @param {string} owner - 저장소 소유자
 * @param {string} repo - 저장소 이름
 * @param {function} onEvent - 이벤트 핸들러 (type, data) => void
 * @returns {function} - 취소 함수
 */
export const sendChatMessageStreamV2 = (
  message,
  sessionId,
  owner,
  repo,
  onEvent
) => {
  const abortController = new AbortController();

  // Fetch로 POST SSE 스트리밍
  fetch(`${API_BASE_URL}/api/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify({
      message,
      session_id: sessionId,
      owner: owner || "unknown",
      repo: repo || "unknown",
      metadata: {},
    }),
    signal: abortController.signal,
  })
    .then(async (response) => {
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || ""; // 마지막 불완전한 줄은 버퍼에 유지

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const data = JSON.parse(line.slice(6));
              onEvent(data.type, data);

              // done 이벤트 시 종료
              if (data.type === "done" || data.type === "error") {
                reader.cancel();
                return;
              }
            } catch (error) {
              console.error("Failed to parse SSE message:", error, line);
            }
          }
        }
      }
    })
    .catch((error) => {
      if (error.name === "AbortError") {
        console.log("Stream aborted by user");
      } else {
        console.error("SSE streaming error:", error);
        onEvent("error", {
          message: `스트리밍 오류: ${error.message}`,
          error: error.message,
        });
      }
    });

  // 취소 함수 반환
  return () => {
    abortController.abort();
  };
};

// ============ Session Management ============

/**
 * 세션 정보 조회
 * @param {string} sessionId - 세션 ID
 * @returns {Promise<{session_id, created_at, last_accessed, turn_count, accumulated_context}>}
 */
export const getSessionInfo = async (sessionId) => {
  try {
    const response = await api.get(`/api/chat/session/${sessionId}`);
    return response.data;
  } catch (error) {
    console.error("Get session info failed:", error);
    throw error;
  }
};

/**
 * 활성 세션 목록 조회
 * @returns {Promise<{total, sessions}>}
 */
export const listActiveSessions = async () => {
  try {
    const response = await api.get("/api/chat/sessions");
    return response.data;
  } catch (error) {
    console.error("List sessions failed:", error);
    throw error;
  }
};

/**
 * 세션 삭제
 * @param {string} sessionId - 세션 ID
 * @returns {Promise<{success, message}>}
 */
export const deleteSession = async (sessionId) => {
  try {
    const response = await api.delete(`/api/chat/session/${sessionId}`);
    return response.data;
  } catch (error) {
    console.error("Delete session failed:", error);
    throw error;
  }
};
