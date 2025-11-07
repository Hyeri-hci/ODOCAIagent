import React from "react";
import { Loader2 } from "lucide-react";

// 보조 액션 버튼 컴포넌트 (White / Gradient)
export const SecondaryButton = ({
  children,
  onClick,
  disabled = false,
  loading = false,
  icon: Icon,
  size = "md",
  fullWidth = false,
  variant = "default",
  className = "",
  ...props
}) => {
  const sizeClasses = {
    sm: "px-4 py-2 text-sm",
    md: "px-6 py-3 text-base",
    lg: "px-8 py-4 text-lg",
  };

  const variantClasses = {
    default:
      "bg-white/60 text-indigo-600 border-indigo-300 hover:bg-indigo-600 hover:text-white",
    success:
      "bg-gradient-to-r from-green-500 to-emerald-500 text-white border-0 hover:from-green-600 hover:to-emerald-600",
    danger:
      "bg-white text-red-600 border-red-300 hover:bg-red-600 hover:text-white",
  };

  return (
    <button
      onClick={onClick}
      disabled={disabled || loading}
      className={`
        inline-flex items-center justify-center gap-2
        backdrop-blur-sm border-2 font-bold rounded-xl shadow-lg
        disabled:opacity-50 disabled:cursor-not-allowed
        transition-all duration-300
        ${sizeClasses[size]}
        ${variantClasses[variant]}
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

export default SecondaryButton;
