import api from "./client";

// ============ Authentication API ============

/**
 * 카카오 OAuth 인증 URL 생성
 * @returns {string} - 카카오 인증 URL
 */
export const getKakaoAuthUrl = () => {
  const KAKAO_CLIENT_ID =
    import.meta.env.VITE_KAKAO_CLIENT_ID || "your_kakao_client_id";
  const REDIRECT_URI =
    import.meta.env.VITE_KAKAO_REDIRECT_URI ||
    "http://localhost:5173/auth/kakao/callback";

  return `https://kauth.kakao.com/oauth/authorize?client_id=${KAKAO_CLIENT_ID}&redirect_uri=${REDIRECT_URI}&response_type=code`;
};

/**
 * 카카오 로그인
 * @param {string} code - 인증 코드
 * @returns {Promise<Object>} - 로그인 결과 (access_token, user)
 */
export const kakaoLogin = async (code) => {
  try {
    const response = await api.post("/api/auth/kakao/login", { code });
    return response.data;
  } catch (error) {
    console.error("카카오 로그인 실패:", error);
    throw error;
  }
};

/**
 * 카카오 인증 상태 확인
 * @returns {Promise<Object>} - 인증 상태 (authenticated, user)
 */
export const checkKakaoAuth = async () => {
  try {
    const response = await api.get("/api/auth/kakao/check");
    return response.data;
  } catch (error) {
    console.error("카카오 인증 확인 실패:", error);
    return { authenticated: false };
  }
};
