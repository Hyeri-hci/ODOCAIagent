import { useState } from "react";

/**
 * 채팅 메시지 관리 Hook
 *
 * @param {Function} getInitialMessages - 초기 메시지 생성 함수
 * @returns {Object} 메시지 상태 및 관리 함수
 */
export const useChat = (getInitialMessages) => {
  const [messages, setMessages] = useState(getInitialMessages());
  const [inputValue, setInputValue] = useState("");
  const [isTyping, setIsTyping] = useState(false);

  const addMessage = (message) => {
    setMessages((prev) => [...prev, message]);
  };

  const replaceMessage = (messageId, newMessage) => {
    setMessages((prev) =>
      prev.map((msg) => (msg.id === messageId ? newMessage : msg))
    );
  };

  const removeMessage = (messageId) => {
    setMessages((prev) => prev.filter((msg) => msg.id !== messageId));
  };

  const clearInput = () => {
    setInputValue("");
  };

  return {
    messages,
    setMessages,
    inputValue,
    setInputValue,
    isTyping,
    setIsTyping,
    addMessage,
    replaceMessage,
    removeMessage,
    clearInput,
  };
};
