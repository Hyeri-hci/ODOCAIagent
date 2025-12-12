import React, { useState, useEffect } from "react";
import {
  Settings,
  Trash2,
  Clock,
  Database,
  X,
  Check,
  AlertTriangle,
} from "lucide-react";

// localStorage 키 상수
const STORAGE_KEYS = {
  SESSION_ID: "odoc_session_id",
  SESSION_REPO: "odoc_session_repo",
  ANALYSIS_HISTORY: "odoc_analysis_history",
  USER_PREFERENCES: "odoc_preferences",
};

/**
 * 저장된 데이터 크기 계산 (KB)
 */
const getStorageSize = () => {
  let total = 0;
  for (const key in localStorage) {
    if (key.startsWith("odoc_")) {
      total += localStorage.getItem(key)?.length || 0;
    }
  }
  return (total / 1024).toFixed(2);
};

/**
 * 저장 데이터 항목 정보 가져오기
 */
const getStorageItems = () => {
  const items = [];

  const sessionId = localStorage.getItem(STORAGE_KEYS.SESSION_ID);
  if (sessionId) {
    items.push({
      key: STORAGE_KEYS.SESSION_ID,
      name: "세션 ID",
      size: sessionId.length,
      preview: sessionId.substring(0, 20) + "...",
    });
  }

  const sessionRepo = localStorage.getItem(STORAGE_KEYS.SESSION_REPO);
  if (sessionRepo) {
    try {
      const repo = JSON.parse(sessionRepo);
      items.push({
        key: STORAGE_KEYS.SESSION_REPO,
        name: "현재 저장소",
        size: sessionRepo.length,
        preview: repo.full_name || `${repo.owner}/${repo.repo}`,
      });
    } catch {
      items.push({
        key: STORAGE_KEYS.SESSION_REPO,
        name: "현재 저장소",
        size: sessionRepo.length,
        preview: "파싱 오류",
      });
    }
  }

  const history = localStorage.getItem(STORAGE_KEYS.ANALYSIS_HISTORY);
  if (history) {
    try {
      const parsed = JSON.parse(history);
      const count = Array.isArray(parsed.data) ? parsed.data.length : 0;
      items.push({
        key: STORAGE_KEYS.ANALYSIS_HISTORY,
        name: "분석 히스토리",
        size: history.length,
        preview: `${count}개 항목`,
        expiresAt: parsed.expiresAt,
      });
    } catch {
      items.push({
        key: STORAGE_KEYS.ANALYSIS_HISTORY,
        name: "분석 히스토리",
        size: history.length,
        preview: "파싱 오류",
      });
    }
  }

  return items;
};

/**
 * 스토리지 설정 모달 컴포넌트
 */
const StorageSettingsModal = ({ isOpen, onClose, onClearComplete }) => {
  const [items, setItems] = useState([]);
  const [totalSize, setTotalSize] = useState("0");
  const [selectedItems, setSelectedItems] = useState(new Set());
  const [confirmDelete, setConfirmDelete] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setItems(getStorageItems());
      setTotalSize(getStorageSize());
      setSelectedItems(new Set());
      setConfirmDelete(false);
    }
  }, [isOpen]);

  const toggleItem = (key) => {
    setSelectedItems((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(key)) {
        newSet.delete(key);
      } else {
        newSet.add(key);
      }
      return newSet;
    });
    setConfirmDelete(false);
  };

  const selectAll = () => {
    if (selectedItems.size === items.length) {
      setSelectedItems(new Set());
    } else {
      setSelectedItems(new Set(items.map((i) => i.key)));
    }
    setConfirmDelete(false);
  };

  const handleDelete = () => {
    if (!confirmDelete) {
      setConfirmDelete(true);
      return;
    }

    // 선택된 항목 삭제
    selectedItems.forEach((key) => {
      localStorage.removeItem(key);
    });

    // 상태 업데이트
    setItems(getStorageItems());
    setTotalSize(getStorageSize());
    setSelectedItems(new Set());
    setConfirmDelete(false);

    if (onClearComplete) {
      onClearComplete(Array.from(selectedItems));
    }
  };

  const clearAll = () => {
    // ODOC 관련 모든 데이터 삭제
    Object.values(STORAGE_KEYS).forEach((key) => {
      localStorage.removeItem(key);
    });

    setItems([]);
    setTotalSize("0");
    setSelectedItems(new Set());
    setConfirmDelete(false);

    if (onClearComplete) {
      onClearComplete(Object.values(STORAGE_KEYS));
    }
  };

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md bg-white dark:bg-gray-800 rounded-xl shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* 헤더 */}
        <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-gray-100 dark:bg-gray-700 rounded-lg">
              <Database className="w-5 h-5 text-gray-600 dark:text-gray-400" />
            </div>
            <div>
              <h3 className="font-semibold text-gray-900 dark:text-white">
                저장 데이터 관리
              </h3>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                총 {totalSize} KB 사용 중
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
          >
            <X className="w-5 h-5 text-gray-500" />
          </button>
        </div>

        {/* 콘텐츠 */}
        <div className="p-4">
          {items.length === 0 ? (
            <div className="text-center py-8 text-gray-500 dark:text-gray-400">
              <Database className="w-12 h-12 mx-auto mb-3 opacity-50" />
              <p>저장된 데이터가 없습니다</p>
            </div>
          ) : (
            <>
              {/* 전체 선택 */}
              <div className="flex items-center justify-between mb-3">
                <button
                  onClick={selectAll}
                  className="text-sm text-indigo-600 dark:text-indigo-400 hover:underline"
                >
                  {selectedItems.size === items.length
                    ? "전체 해제"
                    : "전체 선택"}
                </button>
                <span className="text-xs text-gray-500">
                  {selectedItems.size}개 선택됨
                </span>
              </div>

              {/* 항목 목록 */}
              <div className="space-y-2">
                {items.map((item) => (
                  <label
                    key={item.key}
                    className={`flex items-center gap-3 p-3 rounded-lg cursor-pointer transition-colors ${
                      selectedItems.has(item.key)
                        ? "bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800"
                        : "bg-gray-50 dark:bg-gray-700/50 border border-transparent hover:bg-gray-100 dark:hover:bg-gray-700"
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={selectedItems.has(item.key)}
                      onChange={() => toggleItem(item.key)}
                      className="w-4 h-4 text-red-600 rounded border-gray-300 focus:ring-red-500"
                    />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-900 dark:text-white">
                        {item.name}
                      </p>
                      <p className="text-xs text-gray-500 dark:text-gray-400 truncate">
                        {item.preview}
                      </p>
                      {item.expiresAt && (
                        <p className="text-xs text-gray-400 flex items-center gap-1 mt-1">
                          <Clock className="w-3 h-3" />
                          만료:{" "}
                          {new Date(item.expiresAt).toLocaleString("ko-KR")}
                        </p>
                      )}
                    </div>
                    <span className="text-xs text-gray-400">
                      {(item.size / 1024).toFixed(1)} KB
                    </span>
                  </label>
                ))}
              </div>
            </>
          )}
        </div>

        {/* 푸터 */}
        <div className="flex items-center justify-between p-4 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-700/50">
          <button
            onClick={clearAll}
            className="flex items-center gap-1 text-sm text-red-600 dark:text-red-400 hover:text-red-700 dark:hover:text-red-300"
          >
            <Trash2 className="w-4 h-4" />
            모두 삭제
          </button>

          <div className="flex gap-2">
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-600 rounded-lg transition-colors"
            >
              취소
            </button>
            <button
              onClick={handleDelete}
              disabled={selectedItems.size === 0}
              className={`flex items-center gap-1 px-4 py-2 text-sm rounded-lg transition-colors ${
                selectedItems.size === 0
                  ? "bg-gray-200 dark:bg-gray-600 text-gray-400 cursor-not-allowed"
                  : confirmDelete
                  ? "bg-red-600 hover:bg-red-700 text-white"
                  : "bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400 hover:bg-red-200 dark:hover:bg-red-900/50"
              }`}
            >
              {confirmDelete ? (
                <>
                  <AlertTriangle className="w-4 h-4" />
                  정말 삭제
                </>
              ) : (
                <>
                  <Trash2 className="w-4 h-4" />
                  선택 삭제
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

/**
 * 설정 버튼 컴포넌트 (헤더에 추가용)
 */
export const StorageSettingsButton = ({ onClearComplete }) => {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <>
      <button
        onClick={() => setIsOpen(true)}
        className="p-2 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
        title="저장 데이터 관리"
      >
        <Settings className="w-5 h-5" />
      </button>

      <StorageSettingsModal
        isOpen={isOpen}
        onClose={() => setIsOpen(false)}
        onClearComplete={(keys) => {
          if (onClearComplete) onClearComplete(keys);
          setIsOpen(false);
        }}
      />
    </>
  );
};

export default StorageSettingsModal;
