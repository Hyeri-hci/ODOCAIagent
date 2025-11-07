// 디자인 시스템 정의

export const theme = {
  // 색상 팔레트
  colors: {
    primary: {
      50: "#EFF6FF",
      100: "#DBEAFE",
      500: "#3B82F6",
      600: "#2563EB",
      700: "#1D4ED8",
      800: "#1E3A8A",
      900: "#1E40AF",
    },

    success: {
      50: "#F0FDF4",
      500: "#10B981",
      600: "#059669",
    },

    warning: {
      50: "#FEF3C7",
      500: "#F59E0B",
      600: "#D97706",
    },

    danger: {
      50: "#FEF2F2",
      500: "#EF4444",
      600: "#DC2626",
    },

    slate: {
      50: "#F8FAFC",
      100: "#F1F5F9",
      500: "#64748B",
      600: "#475569",
      900: "#0F172A",
    },
  },

  // 타이포그래피 설정 (글자 크기)
  typography: {
    fontSizes: {
      xs: "0.75rem", // 12px
      sm: "0.875rem", // 14px
      md: "1rem", // 16px
      lg: "1.125rem", // 18px
      xl: "1.25rem", // 20px
      "2xl": "1.5rem", // 24px
      "3xl": "1.875rem", // 30px
      "4xl": "2.25rem", // 36px
      "5xl": "3rem", // 48px
    },

    fontweights: {
      light: 300,
      normal: 400,
      medium: 500,
      bold: 700,
      black: 900,
    },
  },

  // 간격 설정 (여백 및 패딩)
  spacing: {
    1: "0.25rem", // 4px
    2: "0.5rem", // 8px
    3: "0.75rem", // 12px
    4: "1rem", // 16px
    6: "1.5rem", // 24px
    8: "2rem", // 32px
    12: "3rem", // 48px
    16: "4rem", // 64px
  },

  // 둥근 모서리
  borderRadius: {
    sm: "0.25rem", // 4px
    base: "0.5rem", // 8px
    lg: "1rem", // 16px
    xl: "1.25rem", // 20px
    "2xl": "1.5rem", // 24px
    full: "9999px", // 완전한 원
  },

  // 그림자
  shadows: {
    sm: "0 1px 2px 0 rgba(0, 0, 0, 0.05)",
    base: "0 1px 3px 0 rgba(0, 0, 0, 0.1)",
    lg: "0 10px 15px -3px rgba(0, 0, 0, 0.1)",
    xl: "0 20px 25px -5px rgba(0, 0, 0, 0.1)",
    soft: "0 2px 15px -3px rgba(0, 0, 0, 0.07)",
  },
};

// 헬퍼 함수

// 색상 값 가져오기 @example: getColor('primary.500') => '#3B82F6'
export const getColor = (path) => {
  const keys = path.split(".");
  let result = theme.colors;
  keys.forEach((key) => {
    result = result[key];
    if (!result) throw new Error(`Color not found: ${path}`);
  });
  return result;
};

// 글자 크기 값 가져오기 @example: getFontSize('lg') => '1.125rem'
export const getFontSize = (size) => {
  const fontSize = theme.typography.fontSizes[size];
  if (!fontSize) throw new Error(`Font size not found: ${size}`);
  return fontSize || size;
};

// 간격 값 가져오기 @example: getSpacing(4) => '1rem'
export const getSpacing = (size) => {
  const spacing = theme.spacing[size];
  if (!spacing) throw new Error(`Spacing not found: ${size}`);
  return spacing || size;
};

// 둥근 모서리 값 가져오기 @example: getBorderRadius('lg') => '1rem'
export const getBorderRadius = (size) => {
  const borderRadius = theme.borderRadius[size];
  if (!borderRadius) throw new Error(`Border radius not found: ${size}`);
  return borderRadius || size;
};

// 그림자 값 가져오기 @example: getShadow('lg') => '0 10px 15px -3px rgba(0, 0, 0, 0.1)'
export const getShadow = (size) => {
  const shadow = theme.shadows[size];
  if (!shadow) throw new Error(`Shadow not found: ${size}`);
  return shadow || size;
};

export default theme;
