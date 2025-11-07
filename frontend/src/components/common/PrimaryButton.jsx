import React from "react";
import { Loader2 } from "lucide-react";

// 주요 액션 버튼 컴포넌트 (Blue)
export const PrimaryButton = ({
  children,
  onClick,
  disabled = false,
  loading = false,
  icon: Icon,
  size = "md",
  fullWidth = false,
  className = "",
  ...props
}) => {
  const sizeClasses = {
    sm: "px-4 py-2 text-sm",
    md: "px-6 py-3 text-base",
    lg: "px-8 py-4 text-lg",
  };

  return (
    <button
      onClick={onClick}
      disabled={disabled || loading}
      className={`
        inline-flex items-center justify-center gap-2
        bg-gradient-to-r from-[#2563EB] to-[#1E3A8A]
        text-white font-bold rounded-xl
        hover:shadow-2xl hover:scale-105
        disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100
        transition-all duration-300
        ${sizeClasses[size]}
        ${fullWidth ? "w-full" : ""}
        ${className}
      `}
      {...props}
    >
      {loading && <Loader2 className="w-5 h-5 animate-spin" />}
      {!loading && Icon && <Icon className="w-5 h-5" />}
      {children}
    </button>
  );
};

export default PrimaryButton;
