/**
 * GitHub URL 파싱 및 저장소 정보 추출 유틸리티
 */

/**
 * GitHub URL에서 owner/repo 파싱
 * @param {string} url - GitHub URL
 * @returns {{ owner: string | null, repo: string | null }}
 */
export const parseGitHubUrl = (url) => {
  if (!url) return { owner: null, repo: null };

  try {
    const match = url.match(/github\.com\/([\w-]+)\/([\w.-]+)/i);
    if (match) {
      return { owner: match[1], repo: match[2].replace(/\.git$/, "") };
    }
  } catch (error) {
    console.error("GitHub URL 파싱 실패:", error);
  }

  return { owner: null, repo: null };
};

/**
 * 메시지에서 GitHub URL 감지
 * @param {string} message - 사용자 메시지
 * @returns {string | null} - 감지된 GitHub URL 또는 null
 */
export const detectGitHubUrl = (message) => {
  // github.com 포함된 전체 URL
  const fullUrlMatch = message.match(
    /(?:https?:\/\/)?(?:www\.)?github\.com\/([\w-]+\/[\w.-]+)/i
  );
  if (fullUrlMatch) {
    return fullUrlMatch[0].startsWith("http")
      ? fullUrlMatch[0]
      : `https://${fullUrlMatch[0]}`;
  }

  // 간단한 owner/repo 형식 (공백 없이)
  const trimmed = message.trim();
  const shortMatch = trimmed.match(/^([\w-]+)\/([\w.-]+)$/);
  if (shortMatch) {
    return `https://github.com/${shortMatch[0]}`;
  }

  return null;
};
