import React from "react";
import { Github, Mail } from "lucide-react";

/**
 * Footer Component
 * 페이지 하단 정보 (로고, 간단한 링크, 저작권)
 */
export const Footer = () => {
  return (
    <footer className="bg-[#0F172A] text-white py-6 border-t border-slate-800">
      <div className="container mx-auto px-4">
        <div className="max-w-6xl mx-auto">
          {/* Main Content - Compact Single Row */}
          <div className="flex flex-col md:flex-row items-center justify-between gap-4">
            {/* Left: Logo & Copyright */}
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 bg-gradient-to-br from-[#2563EB] to-[#1E3A8A] rounded-lg flex items-center justify-center">
                <Github className="w-4 h-4 text-white" />
              </div>
              <span className="text-sm font-bold">ODOC AI Agent</span>
              <span className="hidden md:inline text-slate-500 text-sm">
                © 2025
              </span>
            </div>

            {/* Right: Links & Contact */}
            <div className="flex items-center gap-4">
              <a
                href="#analyze"
                className="text-slate-400 hover:text-white transition-colors text-sm font-semibold"
              >
                분석하기
              </a>
              <a
                href="https://github.com/Hyeri-hci/ODOCAIagent"
                target="_blank"
                rel="noopener noreferrer"
                className="w-8 h-8 bg-white/10 hover:bg-white/20 rounded-lg flex items-center justify-center transition-all hover:scale-110"
                title="GitHub"
              >
                <Github className="w-4 h-4" />
              </a>
              <a
                href="mailto:hyeri.hci.du@gmail.com"
                className="w-8 h-8 bg-white/10 hover:bg-white/20 rounded-lg flex items-center justify-center transition-all hover:scale-110"
                title="Contact"
              >
                <Mail className="w-4 h-4" />
              </a>
            </div>
          </div>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
