/**
 * GitHub 스타일로 숫자를 포맷팅합니다.
 * 예: 1000 -> 1k, 1500 -> 1.5k, 1000000 -> 1m
 * 
 * @param {number} num - 포맷팅할 숫자
 * @returns {string} - 포맷팅된 문자열
 */
export const formatNumber = (num) => {
  if (num === null || num === undefined) return '0';
  
  const numValue = Number(num);
  
  if (isNaN(numValue)) return '0';
  
  if (numValue >= 1000000) {
    const millions = numValue / 1000000;
    return millions % 1 === 0 
      ? `${millions}m` 
      : `${millions.toFixed(1)}m`;
  }
  
  if (numValue >= 1000) {
    const thousands = numValue / 1000;
    return thousands % 1 === 0 
      ? `${thousands}k` 
      : `${thousands.toFixed(1)}k`;
  }
  
  return numValue.toString();
};

