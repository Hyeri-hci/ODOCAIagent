"""docs_effective 모듈 테스트."""
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock

from backend.agents.diagnosis.tools.readme.docs_effective import (
    compute_docs_effective,
    DocsEffectiveResult,
    _compute_tech_score,
    _compute_marketing_penalty,
)
from backend.agents.diagnosis.tools.readme.tech_signals import TechSignals
from backend.agents.diagnosis.tools.readme.marketing_signals import MarketingSignals


class TestComputeTechScore:
    """기술 점수 계산 테스트."""
    
    def test_high_tech_signals(self):
        """기술 신호가 많으면 높은 점수."""
        signals = TechSignals(
            code_blocks={"python": 3, "bash": 2, "json": 1},
            command_blocks={"pip_install": 2, "python_run": 1},
            command_block_count=3,
            path_refs=["src/main.py", "config.yaml", "tests/", "docs/", "setup.py"],
            platform_flags={"has_docker": True, "has_ci": True, "has_pyproject": True},
            tech_signal_count=15,
            token_count=100,
            tech_density=150.0,  # per 1k tokens
        )
        
        score = _compute_tech_score(signals)
        assert score >= 80
    
    def test_low_tech_signals(self):
        """기술 신호가 적으면 낮은 점수."""
        signals = TechSignals(
            code_blocks={},
            command_blocks={},
            command_block_count=0,
            path_refs=[],
            platform_flags={},
            tech_signal_count=0,
            token_count=100,
            tech_density=0.0,
        )
        
        score = _compute_tech_score(signals)
        assert score < 30
    
    def test_medium_tech_signals(self):
        """중간 수준의 기술 신호."""
        signals = TechSignals(
            code_blocks={"python": 2},
            command_blocks={"pip_install": 1},
            command_block_count=1,
            path_refs=["README.md"],
            platform_flags={"has_pyproject": True},
            tech_signal_count=4,
            token_count=100,
            tech_density=40.0,
        )
        
        score = _compute_tech_score(signals)
        assert 30 <= score <= 70


class TestComputeMarketingPenalty:
    """마케팅 페널티 계산 테스트."""
    
    def test_no_penalty_for_technical_readme(self):
        """기술 중심 README는 페널티 없음."""
        signals = MarketingSignals(
            marketing_keywords={"en": 2, "ko": 0},
            marketing_keyword_total=2,
            marketing_density=20.0,  # per 1k tokens, 낮은 밀도
            unlinked_feature_bullets=2,
            total_bullets=5,
            badge_counts={"tech": 2, "promo": 1, "total": 3},
            badge_urls=[],
            template_similarity=0.1,
        )
        
        penalty = _compute_marketing_penalty(signals)
        assert penalty == 0
    
    def test_high_penalty_for_marketing_readme(self):
        """마케팅 과다 README는 높은 페널티."""
        signals = MarketingSignals(
            marketing_keywords={"en": 20, "ko": 5},
            marketing_keyword_total=25,
            marketing_density=200.0,  # 높은 밀도 per 1k tokens
            unlinked_feature_bullets=12,  # 많은 비연결 불릿
            total_bullets=15,
            badge_counts={"tech": 5, "promo": 10, "total": 15},  # 배지 과다
            badge_urls=[],
            template_similarity=0.7,  # 템플릿 유사
        )
        
        penalty = _compute_marketing_penalty(signals)
        assert penalty >= 20
    
    def test_template_similarity_penalty(self):
        """템플릿 유사도 높으면 페널티."""
        signals = MarketingSignals(
            marketing_keywords={"en": 5, "ko": 0},
            marketing_keyword_total=5,
            marketing_density=50.0,
            unlinked_feature_bullets=3,
            total_bullets=5,
            badge_counts={"tech": 3, "promo": 1, "total": 4},
            badge_urls=[],
            template_similarity=0.8,  # 템플릿과 유사
        )
        
        penalty = _compute_marketing_penalty(signals)
        assert penalty >= 6  # 템플릿 페널티 최소 6점


class TestComputeDocsEffective:
    """문서 유효 점수 통합 테스트."""
    
    def test_technical_readme_high_score(self):
        """기술 중심 README는 높은 유효 점수."""
        readme = """
# Project Name

## Installation

```bash
pip install myproject
```

## Usage

```python
from myproject import main
main.run()
```

## Configuration

Edit `config.yaml`:

```yaml
debug: true
port: 8080
```

## Development

```bash
pytest tests/
```
"""
        result = compute_docs_effective(
            owner="test",
            repo="test",
            readme_content=readme,
            docs_quality_raw=70,
            skip_consilience=True,
        )
        
        assert result.tech_score >= 60
        assert result.marketing_penalty <= 5
        assert result.docs_effective >= 65
    
    def test_marketing_readme_penalized(self):
        """마케팅 중심 README는 페널티 적용."""
        readme = """
# Amazing Project

The **best** solution for all your needs!

## Features

- Lightning fast performance
- Enterprise-grade security
- Unlimited scalability
- World-class support
- Revolutionary technology
- Game-changing innovation
- Industry-leading quality
- Next-generation architecture

## Why Choose Us

We are the #1 choice for developers worldwide!

![badge](https://badge1.svg)
![badge](https://badge2.svg)
![badge](https://badge3.svg)
![badge](https://badge4.svg)
![badge](https://badge5.svg)
![badge](https://badge6.svg)
![badge](https://badge7.svg)
![badge](https://badge8.svg)
![badge](https://badge9.svg)
![badge](https://badge10.svg)
"""
        result = compute_docs_effective(
            owner="test",
            repo="test",
            readme_content=readme,
            docs_quality_raw=75,
            skip_consilience=True,
        )
        
        assert result.marketing_penalty > 0
        assert result.is_marketing_heavy == True
    
    def test_skip_consilience(self):
        """교차검증 건너뛰기 옵션."""
        result = compute_docs_effective(
            owner="test",
            repo="test",
            readme_content="# Test",
            docs_quality_raw=50,
            skip_consilience=True,
        )
        
        assert result.consilience_score == 100
        assert result.consilience_details is None
    
    def test_result_serialization(self):
        """결과 직렬화 테스트."""
        result = compute_docs_effective(
            owner="test",
            repo="test",
            readme_content="# Test\n\n```python\nprint('hello')\n```",
            docs_quality_raw=60,
            skip_consilience=True,
        )
        
        d = result.to_dict()
        assert "docs_effective" in d
        assert "tech_score" in d
        assert "marketing_penalty" in d
        assert "tech_signals" in d


class TestDocsEffectiveWithConsilience:
    """교차검증 포함 테스트."""
    
    @patch("backend.agents.diagnosis.tools.readme.docs_effective.check_path_refs")
    @patch("backend.agents.diagnosis.tools.readme.docs_effective.check_badge_refs")
    @patch("backend.agents.diagnosis.tools.readme.docs_effective.check_command_refs")
    def test_consilience_affects_score(self, mock_cmd, mock_badge, mock_path):
        """교차검증 결과가 점수에 반영됨."""
        from backend.agents.diagnosis.tools.consilience import (
            PathCheckResult,
            BadgeCheckResult, 
            CommandCheckResult,
        )
        
        # 모든 검증 실패
        mock_path.return_value = PathCheckResult(valid=0, broken=2, total=2)
        mock_badge.return_value = BadgeCheckResult(valid=0, broken=1, total=1)
        mock_cmd.return_value = CommandCheckResult(valid=0, broken=1, total=1)
        
        readme = """
# Test

See `src/main.py` and `config/settings.json`.

```bash
pip install myproject
```

![CI](https://github.com/test/test/workflows/ci.yml/badge.svg)
"""
        
        result = compute_docs_effective(
            owner="test",
            repo="test",
            readme_content=readme,
            docs_quality_raw=70,
            skip_consilience=False,
        )
        
        assert result.consilience_score < 50
        assert result.has_broken_refs == True
