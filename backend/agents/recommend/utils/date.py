# utils/date.py

from datetime import datetime, timezone

class DateUtilsUTC:
    @staticmethod
    def today_str() -> str:
        """
        [Prompt용] YYYY-MM-DD 문자열 반환
        예: '2025-12-06'
        """
        return DateUtilsUTC.now().strftime("%Y-%m-%d")

    @staticmethod
    def now() -> datetime:
        """
        [Logic용] 현재 시간 datetime 객체 반환 (UTC 기준)
        날짜 비교, 연산 등에 사용합니다.
        """
        return datetime.now(timezone.utc)