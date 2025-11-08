import React from "react";
import { GitHub } from "lucide-react";

export const Footer = () => {
  return (
    <footer className="bg-[#0F172A] text-white py-16 border-t border-slate-800 shadow-2xl">
      <div className="container mx-auto px-4">
        <div className="max-w-6xl mx-auto">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-12 mb-12">
            {/* Logo & Description */}
            <div className="md:col-span-2">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-12 h-12 bg-gradient-to-br from-[#2563EB] to-[#1E3A8A] rounded-xl flex items-center justify-center shadow-lg">
                  <Github className="w-6 h-6 text-white" />
                </div>
                <span className="text-2xl font-black">ODOC AI Agent</span>
              </div>
              <p className="text-slate-400 leading-relaxed mb-6">
                AI 기반 오픈소스 분석으로 더 나은 기여 경험을 제공합니다.
                <br />
                Powered by OSSDoctor AI
              </p>
              <div className="flex gap-4">
                <a
                  href="https://github.com"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="w-10 h-10 bg-white/10 hover:bg-white/20 rounded-lg flex items-center justify-center transition-all hover:scale-110"
                >
                  <Github className="w-5 h-5" />
                </a>
              </div>
            </div>

            {/* Quick Links */}
            <div>
              <h4 className="text-lg font-bold mb-4">Quick Links</h4>
              <ul className="space-y-2">
                <li>
                  <a
                    href="#analyze"
                    className="text-slate-400 hover:text-white transition-colors"
                  >
                    분석하기
                  </a>
                </li>
                <li>
                  <a
                    href="#"
                    className="text-slate-400 hover:text-white transition-colors"
                  >
                    Documentation
                  </a>
                </li>
                <li>
                  <a
                    href="#"
                    className="text-slate-400 hover:text-white transition-colors"
                  >
                    API Reference
                  </a>
                </li>
                <li>
                  <a
                    href="https://github.com/Hyeri-hci/ODOCAIagent"
                    className="text-slate-400 hover:text-white transition-colors"
                  >
                    GitHub Repository
                  </a>
                </li>
              </ul>
            </div>

            {/* Legal */}
            <div>
              <h4 className="text-lg font-bold mb-4">Legal</h4>
              <ul className="space-y-2">
                <li>
                  <a
                    href="#"
                    className="text-slate-400 hover:text-white transition-colors"
                  >
                    Terms of Service
                  </a>
                </li>
                <li>
                  <a
                    href="#"
                    className="text-slate-400 hover:text-white transition-colors"
                  >
                    Privacy Policy
                  </a>
                </li>
                <li>
                  <a
                    href="#"
                    className="text-slate-400 hover:text-white transition-colors"
                  >
                    Contact
                  </a>
                </li>
                <li>
                  <a
                    href="mailto:hyeri.hci.du@gmail.com"
                    className="text-slate-400 hover:text-white transition-colors"
                  >
                    hyeri.hci.du@gmail.com
                  </a>
                </li>
              </ul>
            </div>
          </div>

          {/* Bottom Bar */}
          <div className="pt-8 border-t border-slate-800">
            <div className="flex flex-col md:flex-row items-center justify-between gap-4">
              <p className="text-sm text-slate-500">
                © 2025 ODOC AI Agent. All rights reserved.
              </p>
              <div className="flex items-center gap-6 text-sm text-slate-500">
                <span>ODOC-HCI Project</span>
                <span>•</span>
                <span className="px-3 py-1 bg-[#2563EB]/20 text-[#60A5FA] rounded-full font-semibold">
                  v1.0.0
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
