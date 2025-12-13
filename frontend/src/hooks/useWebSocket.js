/**
 * useWebSocket - WebSocket 연결 관리 훅
 */

import { useState, useCallback, useRef, useEffect } from "react";

const WS_URL = import.meta.env.VITE_WS_URL || "ws://localhost:8000/ws/chat";

const useWebSocket = (options) => {
  const {
    onMessage,
    onAgentComplete,
    onAnswer,
    onError,
    onConnected,
    onDisconnected,
    autoConnect = false,
  } = options;

  const [isConnected, setIsConnected] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const heartbeatIntervalRef = useRef(null);

  // 하트비트 시작
  const startHeartbeat = useCallback(() => {
    if (heartbeatIntervalRef.current) {
      clearInterval(heartbeatIntervalRef.current);
    }
    heartbeatIntervalRef.current = setInterval(() => {
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: "ping" }));
      }
    }, 30000);
  }, []);

  // 하트비트 중지
  const stopHeartbeat = useCallback(() => {
    if (heartbeatIntervalRef.current) {
      clearInterval(heartbeatIntervalRef.current);
      heartbeatIntervalRef.current = null;
    }
  }, []);

  // 메시지 핸들러
  const handleMessage = useCallback(
    function (event) {
      try {
        const data = JSON.parse(event.data);
        console.log("[WebSocket] Received:", data.type, data);

        if (data.type === "connected") {
          setSessionId(data.session_id);
          if (onConnected) {
            onConnected(data.session_id);
          }
        } else if (data.type === "pong") {
          // 하트비트 응답 - 무시
        } else if (data.type === "agent_complete") {
          if (onAgentComplete && data.agent) {
            onAgentComplete(data.agent, data.result || data.data);
          }
        } else if (data.type === "answer" || data.type === "final_answer") {
          if (onAnswer) {
            onAnswer(data.content || data.message || data.data);
          }
        } else if (data.type === "error") {
          console.error("[WebSocket] Error from server:", data);
          if (onError) {
            onError(data.message || data.error || "Unknown error");
          }
        } else {
          // 기타 메시지는 onMessage로 전달
          if (onMessage) {
            onMessage(data);
          }
        }
      } catch (error) {
        console.error("[WebSocket] Failed to parse message:", error);
      }
    },
    [onMessage, onAgentComplete, onAnswer, onError, onConnected]
  );

  // WebSocket 연결
  const connect = useCallback(
    (existingSessionId = null) => {
      // 이미 연결 중이거나 연결됨
      if (wsRef.current?.readyState === WebSocket.CONNECTING) {
        console.log("[WebSocket] Already connecting...");
        return;
      }

      if (wsRef.current?.readyState === WebSocket.OPEN) {
        console.log("[WebSocket] Already connected");
        return;
      }

      // 기존 연결 정리
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }

      const wsUrl = existingSessionId
        ? `${WS_URL}?session_id=${existingSessionId}`
        : WS_URL;

      console.log("[WebSocket] Connecting to:", wsUrl);

      try {
        const ws = new WebSocket(wsUrl);

        ws.onopen = () => {
          console.log("[WebSocket] Connected, sending init message...");
          setIsConnected(true);

          // 백엔드가 첫 번째 메시지를 기다리므로 초기화 메시지 전송
          const initMessage = {
            type: "init",
            session_id: existingSessionId || null,
          };
          ws.send(JSON.stringify(initMessage));

          startHeartbeat();
        };

        ws.onmessage = handleMessage;

        ws.onerror = (error) => {
          console.error("[WebSocket] Error:", error);
          if (onError) {
            onError("WebSocket connection error");
          }
        };

        ws.onclose = (event) => {
          console.log("[WebSocket] Closed:", event.code, event.reason);
          setIsConnected(false);
          stopHeartbeat();

          if (onDisconnected) {
            onDisconnected();
          }

          // 비정상 종료 시 재연결 시도
          if (event.code !== 1000 && event.code !== 1001) {
            console.log("[WebSocket] Scheduling reconnect...");
            reconnectTimeoutRef.current = setTimeout(() => {
              connect(sessionId);
            }, 3000);
          }
        };

        wsRef.current = ws;
      } catch (error) {
        console.error("[WebSocket] Connection failed:", error);
        if (onError) {
          onError("Failed to create WebSocket connection");
        }
      }
    },
    [
      handleMessage,
      onError,
      onDisconnected,
      startHeartbeat,
      stopHeartbeat,
      sessionId,
    ]
  );

  // WebSocket 연결 해제
  const disconnect = useCallback(() => {
    console.log("[WebSocket] Disconnecting...");

    // 재연결 타이머 취소
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    stopHeartbeat();

    if (wsRef.current) {
      wsRef.current.close(1000, "Client disconnect");
      wsRef.current = null;
    }

    setIsConnected(false);
    setSessionId(null);
  }, [stopHeartbeat]);

  // 메시지 전송
  const sendMessage = useCallback(
    (message, owner = null, repo = null) => {
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
        console.error("[WebSocket] Not connected, cannot send message");
        if (onError) {
          onError("WebSocket is not connected");
        }
        return false;
      }

      const payload = {
        type: "analyze",
        message,
        ...(owner && { owner }),
        ...(repo && { repo }),
      };

      console.log("[WebSocket] Sending:", payload);
      wsRef.current.send(JSON.stringify(payload));
      return true;
    },
    [onError]
  );

  // 작업 취소
  const cancelTask = useCallback(() => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      console.error("[WebSocket] Not connected, cannot cancel task");
      return false;
    }

    const payload = {
      type: "cancel",
    };

    console.log("[WebSocket] Cancelling task");
    wsRef.current.send(JSON.stringify(payload));
    return true;
  }, []);

  // 자동 연결
  useEffect(() => {
    if (autoConnect) {
      connect();
    }

    return () => {
      disconnect();
    };
  }, [autoConnect]); // eslint-disable-line react-hooks/exhaustive-deps

  return {
    isConnected,
    sessionId,
    connect,
    disconnect,
    sendMessage,
    cancelTask,
  };
};

export default useWebSocket;
