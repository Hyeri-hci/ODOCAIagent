import React from "react";
import { Header } from "./Header";
import { NotificationToast } from "./NotificationToast";
import { Footer } from "./Footer";

// 전체 페이지 레이아웃 컴포넌트 (Header + Notification + Main Content + Footer)

export const AppLayout = ({ children, notification }) => {
  return (
    <div className="min-h-screen bg-white">
      {/* Header */}
      <Header />

      {/* Notification Toast */}
      {notification && (
        <NotificationToast
          type={notification.type}
          message={notification.message}
        />
      )}

      {/* Main Content */}
      <main className="pt-16">{children}</main>

      {/* Footer */}
      <Footer />
    </div>
  );
};

export default AppLayout;
