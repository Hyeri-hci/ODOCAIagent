"""config_loader 단위 테스트."""
import pytest
from backend.agents.diagnosis.config.config_loader import (
    load_diagnosis_config,
    get_config_hash,
    reload_config,
    get_marketing_config,
    get_consilience_config,
    get_freshness_config,
    get_docs_config,
    get_gate_config,
    get_tech_patterns,
    get_marketing_keywords,
    get_readme_preference,
)


class TestConfigLoader:
    """설정 로더 테스트."""

    def test_load_diagnosis_config(self):
        """설정 파일 로드 테스트."""
        config = load_diagnosis_config()
        assert isinstance(config, dict)
        assert "marketing" in config
        assert "consilience" in config
        assert "gate" in config

    def test_get_config_hash(self):
        """설정 해시 생성 테스트."""
        hash_value = get_config_hash()
        assert isinstance(hash_value, str)
        assert len(hash_value) == 16  # sha256[:16]

    def test_reload_config(self):
        """설정 리로드 테스트."""
        config1 = load_diagnosis_config()
        config2 = reload_config()
        assert config1 == config2

    def test_get_marketing_config(self):
        """마케팅 설정 반환 테스트."""
        marketing = get_marketing_config()
        assert "threshold" in marketing
        assert "penalty_cap" in marketing
        assert marketing["threshold"] == 0.6
        assert marketing["penalty_cap"] == 0.4

    def test_get_consilience_config(self):
        """교차검증 설정 반환 테스트."""
        consilience = get_consilience_config()
        assert "weights" in consilience
        assert consilience["weights"]["path"] == 0.4
        assert consilience["weights"]["workflow"] == 0.35
        assert consilience["weights"]["link"] == 0.25

    def test_get_freshness_config(self):
        """문서 최신성 설정 반환 테스트."""
        freshness = get_freshness_config()
        assert "tau" in freshness
        assert freshness["tau"] == 60

    def test_get_docs_config(self):
        """유효 문서 설정 반환 테스트."""
        docs = get_docs_config()
        assert "floor" in docs
        assert "weights" in docs
        assert docs["floor"] == 35
        assert docs["weights"]["raw"] == 0.55

    def test_get_gate_config(self):
        """지속성 게이트 설정 반환 테스트."""
        gate = get_gate_config()
        assert "recency_days" in gate
        assert "early_stage_days" in gate
        assert gate["recency_days"] == 90
        assert gate["early_stage_days"] == 60

    def test_get_tech_patterns(self):
        """기술 패턴 반환 테스트."""
        patterns = get_tech_patterns()
        assert "commands" in patterns
        assert "paths" in patterns
        assert "pip install" in patterns["commands"]
        assert "src/" in patterns["paths"]

    def test_get_marketing_keywords(self):
        """마케팅 키워드 반환 테스트."""
        keywords = get_marketing_keywords()
        assert "en" in keywords
        assert "ko" in keywords
        assert "revolutionary" in keywords["en"]
        assert "혁신적" in keywords["ko"]

    def test_get_readme_preference(self):
        """README 우선순위 반환 테스트."""
        prefer = get_readme_preference()
        assert isinstance(prefer, list)
        assert "README.md" in prefer
