"""marketing_signals 단위 테스트."""
import pytest
from backend.agents.diagnosis.tools.readme.marketing_signals import (
    extract_marketing_signals,
    MarketingSignals,
    _jaccard_similarity,
    _get_ngrams,
)


class TestMarketingSignals:
    """마케팅 신호 추출 테스트."""

    def test_empty_readme(self):
        """빈 README 처리."""
        result = extract_marketing_signals("")
        assert isinstance(result, MarketingSignals)
        assert result.marketing_signal_count == 0

    def test_marketing_keyword_detection_en(self):
        """영문 마케팅 키워드 감지."""
        readme = """
# Revolutionary Product

This is a game-changer that provides cutting-edge solutions.
It's blazing fast and enterprise-grade.
"""
        result = extract_marketing_signals(readme)
        assert result.marketing_keyword_total > 0
        assert result.marketing_keywords.get("en", 0) > 0

    def test_marketing_keyword_detection_ko(self):
        """한글 마케팅 키워드 감지."""
        readme = """
# 혁신적인 프로젝트

차세대 기술로 완벽한 솔루션을 제공합니다.
원클릭으로 손쉽게 설치하세요.
"""
        result = extract_marketing_signals(readme)
        assert result.marketing_keyword_total > 0
        assert result.marketing_keywords.get("ko", 0) > 0

    def test_marketing_density(self):
        """마케팅 밀도 계산."""
        # 마케팅 키워드가 많은 짧은 README
        readme = "Revolutionary game-changer cutting-edge blazing fast"
        result = extract_marketing_signals(readme, token_count=5)
        assert result.marketing_density > 0

    def test_unlinked_bullets(self):
        """코드 연결 없는 불릿 감지."""
        readme = """
# Features

- Beautiful dashboard
- Seamless integration
- World-class support
- Run `pip install` to get started
"""
        result = extract_marketing_signals(readme)
        assert result.total_bullets == 4
        # 처음 3개는 코드 연결 없음
        assert result.unlinked_feature_bullets >= 2

    def test_badge_analysis(self):
        """배지 분석."""
        readme = """
# Project

![Build](https://github.com/user/repo/actions/workflows/ci.yml/badge.svg)
![Coverage](https://codecov.io/gh/user/repo/badge.svg)
![Stars](https://img.shields.io/github/stars/user/repo)
![Discord](https://img.shields.io/discord/123456)
"""
        result = extract_marketing_signals(readme)
        assert result.badge_counts["tech"] >= 2  # build, coverage
        assert result.badge_counts["promo"] >= 1  # discord
        assert result.badge_counts["total"] == 4

    def test_template_similarity(self):
        """템플릿 유사도 감지."""
        # 템플릿 문구가 많은 README
        readme = """
# Project Name

## About The Project
## Built With
## Getting Started
### Prerequisites
### Installation
## Usage
## Roadmap
## Contributing
## License
## Contact
## Acknowledgments
"""
        result = extract_marketing_signals(readme)
        assert result.template_similarity > 0.5

    def test_technical_readme_low_marketing(self):
        """기술 중심 README는 마케팅 신호 낮음."""
        readme = """
# Tool

## Install

```bash
pip install tool
```

## Usage

```python
from tool import run
run()
```

## API

- `run()`: Execute the task
- `stop()`: Stop execution
"""
        result = extract_marketing_signals(readme)
        assert result.marketing_keyword_total == 0
        assert result.promo_badge_ratio == 0

    def test_to_dict(self):
        """dict 변환 테스트."""
        result = extract_marketing_signals("Some content")
        d = result.to_dict()
        assert isinstance(d, dict)
        assert "marketing_keywords" in d
        assert "marketing_density" in d


class TestHelperFunctions:
    """헬퍼 함수 테스트."""

    def test_get_ngrams(self):
        """n-gram 추출 테스트."""
        ngrams = _get_ngrams("hello world foo bar", n=2)
        assert "hello world" in ngrams
        assert "world foo" in ngrams

    def test_jaccard_similarity(self):
        """Jaccard 유사도 테스트."""
        set1 = {"a", "b", "c"}
        set2 = {"b", "c", "d"}
        sim = _jaccard_similarity(set1, set2)
        # 교집합 {b, c} = 2, 합집합 {a, b, c, d} = 4
        assert sim == 0.5

    def test_jaccard_empty(self):
        """빈 집합 Jaccard."""
        assert _jaccard_similarity(set(), {"a"}) == 0.0
        assert _jaccard_similarity({"a"}, set()) == 0.0
