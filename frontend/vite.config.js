import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react({
      babel: {
        plugins: [["babel-plugin-react-compiler"]],
      },
    }),
  ],
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          // React 관련 라이브러리 분리
          "vendor-react": ["react", "react-dom", "react-router-dom"],
          // 기타 외부 라이브러리 분리
          "vendor-utils": ["axios"],
        },
      },
    },
  },
});
