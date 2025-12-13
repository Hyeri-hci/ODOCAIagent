"""모델 설정 로더 및 LLM 클라이언트 생성."""
from __future__ import annotations

import os
import logging
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from backend.llm.base import LLMClient
from backend.llm.openai_like import OpenAILikeClient
from backend.llm.factory import LLMClientProvider

logger = logging.getLogger(__name__)

# models.yaml 경로
MODELS_CONFIG_PATH = Path(__file__).parent / "models.yaml"


def load_models_config() -> Dict[str, Any]:
    """models.yaml 파일 로드."""
    if not MODELS_CONFIG_PATH.exists():
        logger.warning(f"모델 설정 파일을 찾을 수 없음: {MODELS_CONFIG_PATH}")
        return {}
    
    with open(MODELS_CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_model_config(model_id: str) -> Optional[Dict[str, Any]]:
    """특정 모델의 설정 조회."""
    configs = load_models_config()
    return configs.get(model_id)


def list_available_models() -> list:
    """사용 가능한 모델 ID 목록."""
    return list(load_models_config().keys())


def create_llm_client(model_id: str) -> LLMClient:
    """모델 ID에 맞는 LLM 클라이언트 생성.
    
    Args:
        model_id: models.yaml에 정의된 모델 ID (kanana2, llama, qwen 등)
    
    Returns:
        LLMClient 인스턴스
    
    Raises:
        ValueError: 모델 설정을 찾을 수 없는 경우
    """
    config = get_model_config(model_id)
    if not config:
        raise ValueError(f"모델 설정을 찾을 수 없음: {model_id}. 사용 가능: {list_available_models()}")
    
    provider = config.get("provider", "openai_compatible")
    
    if provider != "openai_compatible":
        raise ValueError(f"지원하지 않는 provider: {provider}")
    
    # base_url 결정: 직접 설정 또는 환경변수
    base_url = config.get("base_url")
    if not base_url:
        base_url_env = config.get("base_url_env")
        if base_url_env:
            base_url = os.getenv(base_url_env)
    
    # api_key 결정: 직접 설정 또는 환경변수
    api_key = config.get("api_key")
    if not api_key:
        api_key_env = config.get("api_key_env")
        if api_key_env:
            api_key = os.getenv(api_key_env)
    
    model_name = config.get("model", model_id)
    params = config.get("params", {})
    
    logger.info(f"[Eval] LLM 클라이언트 생성: {model_id} (model={model_name}, base_url={base_url})")
    
    # OpenAILikeClient 생성
    client = OpenAILikeClient(
        api_base=base_url,
        api_key=api_key,
        default_model=model_name,
    )
    
    # 기본 파라미터 저장 (나중에 요청 시 사용)
    client._eval_params = params
    
    return client


class EvalLLMContext:
    """평가 모드에서 LLM을 임시로 교체하는 컨텍스트 매니저.
    
    Usage:
        with EvalLLMContext("llama"):
            # 이 블록 내에서는 llama 모델 사용
            result = run_supervisor_diagnosis(...)
    """
    
    def __init__(self, model_id: str):
        self.model_id = model_id
        self._original_client: Optional[LLMClient] = None
    
    def __enter__(self):
        # 현재 클라이언트 백업
        self._original_client = LLMClientProvider._instance
        
        # 새 클라이언트로 교체
        new_client = create_llm_client(self.model_id)
        LLMClientProvider.set_instance(new_client)
        
        logger.info(f"[Eval] LLM 교체: {self.model_id}")
        return new_client
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # 원래 클라이언트 복원
        if self._original_client is not None:
            LLMClientProvider.set_instance(self._original_client)
        else:
            LLMClientProvider.reset()
        
        logger.info(f"[Eval] LLM 복원")
        return False


def override_llm_for_eval(model_id: str) -> None:
    """평가 모드에서 LLM 싱글톤을 교체.
    
    Note: 컨텍스트 매니저 대신 명시적으로 교체할 때 사용.
          restore_llm_after_eval()로 복원 필요.
    """
    new_client = create_llm_client(model_id)
    LLMClientProvider.set_instance(new_client)
    logger.info(f"[Eval] LLM 교체 완료: {model_id}")


def restore_llm_after_eval() -> None:
    """평가 후 LLM 싱글톤 초기화."""
    LLMClientProvider.reset()
    logger.info("[Eval] LLM 초기화 완료")
