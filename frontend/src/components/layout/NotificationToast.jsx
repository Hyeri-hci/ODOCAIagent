import React from "react";

export const NotificationToast = ({ type, message }) => {
  const typeStyles = {
    success: "bg-emerald-50/90 text-emerald-800 border-emerald-200",
    error: "bg-red-50/90 text-red-800 border-red-200",
  };

  const Icon =
    type === "success"
      ? () => (
          <svg
            className="w-6 h-6"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M5 13l4 4L19 7"
            />
          </svg>
        )
      : () => (
          <svg
            className="w-6 h-6"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        );

  return (
    <div
      className={`
        fixed top-24 right-6 z-50 
        px-6 py-4 rounded-2xl shadow-xl 
        flex items-center gap-3 
        animate-fadeIn backdrop-blur-md border-2
        ${typeStyles[type]}
      `}
    >
      <Icon />
      <span className="font-semibold">{message}</span>
    </div>
  );
};

export default NotificationToast;
