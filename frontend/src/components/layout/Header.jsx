import React from "react";
import { Link, useNavigate } from "react-router-dom";
import { GitBranch } from "lucide-react";
import { StorageSettingsButton } from "../common/StorageSettings";

export const Header = () => {
  const navigate = useNavigate();

  const handleStorageClear = (clearedKeys) => {
    console.log("Storage cleared:", clearedKeys);
    // 필요시 페이지 새로고침 또는 상태 초기화
    if (clearedKeys.includes("odoc_session_id")) {
      // 세션이 삭제되면 알림
      console.log("Session cleared - you may need to refresh");
    }
  };

  return (
    <header className="fixed top-0 left-0 right-0 bg-white/80 backdrop-blur-md shadow-sm z-50 border-b border-slate-100">
      <div className="container mx-auto px-4 py-4">
        <div className="flex items-center justify-between">
          {/* Logo */}
          <Link
            to="/"
            className="flex items-center gap-3 cursor-pointer hover:opacity-80 transition-opacity"
          >
            <div className="w-10 h-10 bg-gradient-to-br from-[#2563EB] to-[#1E3A8A] rounded-xl flex items-center justify-center shadow-lg">
              <GitBranch className="w-5 h-5 text-white" />
            </div>
            <span className="text-xl font-bold bg-gradient-to-r from-[#2563EB] to-[#1E3A8A] bg-clip-text text-transparent">
              ODOC AI Agent
            </span>
          </Link>

          {/* Navigation */}
          <nav className="hidden md:flex items-center gap-2">
            <button
              onClick={() => navigate("/analyze")}
              className="px-5 py-2.5 text-slate-600 hover:text-[#2563EB] hover:bg-blue-50 rounded-xl transition-all font-semibold cursor-pointer"
            >
              분석 시작
            </button>
            {/* 저장 데이터 관리 버튼 */}
            <StorageSettingsButton onClearComplete={handleStorageClear} />
          </nav>
        </div>
      </div>
    </header>
  );
};

export default Header;
