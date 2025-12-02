"""tech_signals 단위 테스트."""
import pytest
from backend.agents.diagnosis.tools.readme.tech_signals import (
    extract_tech_signals,
    TechSignals,
)


class TestTechSignals:
    """기술 신호 추출 테스트."""

    def test_empty_readme(self):
        """빈 README 처리."""
        result = extract_tech_signals("")
        assert isinstance(result, TechSignals)
        assert result.tech_signal_count == 0
        assert result.token_count == 0

    def test_code_block_extraction(self):
        """코드블록 추출 테스트."""
        readme = """
# Project

```python
def hello():
    print("Hello")
```

```bash
pip install mypackage
```

```yaml
version: "3"
```
"""
        result = extract_tech_signals(readme)
        assert "python" in result.code_blocks
        assert "bash" in result.code_blocks
        assert "yaml" in result.code_blocks
        assert result.code_blocks["python"] == 1
        assert result.code_blocks["bash"] == 1

    def test_command_block_detection(self):
        """명령형 코드블록 감지 테스트."""
        readme = """
# Install

```bash
pip install mypackage
npm install something
docker run myimage
```

```python
print("not a command")
```
"""
        result = extract_tech_signals(readme)
        assert result.command_block_count >= 1
        assert "bash" in result.command_blocks or "pip" in result.command_blocks

    def test_path_refs_extraction(self):
        """경로 참조 추출 테스트."""
        readme = """
# Structure

- `src/main.py` - Main file
- `examples/demo.py` - Demo
- `.github/workflows/ci.yml` - CI

Check the `docs/` folder for more info.
"""
        result = extract_tech_signals(readme)
        assert len(result.path_refs) > 0
        # 경로가 추출되었는지 확인
        path_str = " ".join(result.path_refs)
        assert "src/" in path_str or "examples/" in path_str or "docs/" in path_str

    def test_platform_flags(self):
        """플랫폼 플래그 감지 테스트."""
        readme = """
# Setup

Edit `pyproject.toml` and run:

```bash
pip install -e .
```

See `Dockerfile` for container setup.
"""
        result = extract_tech_signals(readme)
        assert result.platform_flags.get("has_pyproject") is True
        assert result.platform_flags.get("has_dockerfile") is True

    def test_tech_density_calculation(self):
        """기술 밀도 계산 테스트."""
        # 기술 신호가 많은 README
        readme = """
```bash
pip install package
docker run image
make build
pytest tests/
```

Files: `src/`, `tests/`, `docs/`
Config: `pyproject.toml`, `Dockerfile`
"""
        result = extract_tech_signals(readme)
        assert result.token_count > 0
        assert result.tech_density > 0
        
    def test_to_dict(self):
        """dict 변환 테스트."""
        readme = "```python\nprint('hello')\n```"
        result = extract_tech_signals(readme)
        d = result.to_dict()
        assert isinstance(d, dict)
        assert "code_blocks" in d
        assert "tech_signal_count" in d
        assert "tech_density" in d


class TestRealReadme:
    """실제 README 패턴 테스트."""

    def test_technical_readme(self):
        """기술 중심 README."""
        readme = """
# MyTool

A CLI tool for processing data.

## Installation

```bash
pip install mytool
```

## Usage

```bash
mytool process --input data.csv --output result.json
```

## Development

```bash
git clone https://github.com/user/mytool
cd mytool
pip install -e ".[dev]"
pytest
```

## Project Structure

- `src/mytool/` - Main package
- `tests/` - Test files
- `docs/` - Documentation
"""
        result = extract_tech_signals(readme)
        assert result.command_block_count >= 2
        assert len(result.path_refs) >= 2
        assert result.tech_density > 5  # 기술 밀도 높음

    def test_marketing_readme(self):
        """마케팅 중심 README (기술 신호 적음)."""
        readme = """
# Amazing Product

The revolutionary solution for all your needs!

## Why Choose Us?

- Blazing fast performance
- Enterprise-grade security
- Seamless integration
- World-class support

## Features

- One-click deployment
- AI-powered insights
- Real-time analytics
- Beautiful dashboards

## Get Started

Visit our website to learn more!
"""
        result = extract_tech_signals(readme)
        assert result.command_block_count == 0
        assert len(result.code_blocks) == 0
        # 기술 밀도 낮음
        assert result.tech_density < 5
