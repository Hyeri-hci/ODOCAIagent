from __future__ import annotations

from typing import Any, Dict, List, Optional

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from backend.llm.base import LLMClient, ChatRequest, ChatResponse, ChatMessage
from backend.common.config import LLM_MODEL_NAME

DEFAULT_MODEL_ID = LLM_MODEL_NAME or "kakaocorp/kanana-1.5-8b-instruct-2505"

_model: Optional[AutoModelForCausalLM] = None
_tokenizer: Optional[AutoTokenizer] = None
_loaded_model_id: Optional[str] = None

def _ensure_loaded(model_id: str) -> tuple[AutoModelForCausalLM, AutoTokenizer]:
    global _model, _tokenizer, _loaded_model_id
    if (
        _model is not None
        and _tokenizer is not None
        and _loaded_model_id == model_id
    ):
        return _model, _tokenizer

    print("[local_kanana] Loading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(
        model_id,
        trust_remote_code=True,
    )

    print("[local_kanana] Loading model...")
    if torch.cuda.is_available():
        dtype = torch.bfloat16  # Prefer bfloat16 to save memory on GPU
        device_map: str | Dict[str, Any] = "auto"
    else:
        dtype = torch.float32
        device_map = "cpu"

    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        dtype=dtype,
        device_map=device_map,
        trust_remote_code=True,
    )

    _model = model
    _tokenizer = tokenizer
    _loaded_model_id = model_id
    return model, tokenizer

def _to_hf_message(message: List[ChatMessage]) -> List[Dict[str, str]]:
    return [{"role": m.role, "content": m.content} for m in message]

class LocalKananaClient(LLMClient):
    """LLM client for a local Kanana model."""

    def __init__(self, model_id: str | None = None) -> None:
        self.model_id = model_id or DEFAULT_MODEL_ID

    def chat(self, request: ChatRequest) -> ChatResponse:
        model, tokenizer = _ensure_loaded(self.model_id)

        hf_messages = _to_hf_message(request.messages)

        inputs = tokenizer.apply_chat_template(
            hf_messages,
            tokenizer=True,
            add_generation_prompt=True,
            return_tensors="pt",
        )

        if isinstance(inputs, dict):
            input_ids = inputs["input_ids"]
            attention_mask = inputs.get(
                "attention_mask",
                torch.ones_like(input_ids),
            )
        else:
            input_ids = inputs
            attention_mask = torch.ones_like(input_ids)

        if torch.cuda.is_available():
            input_ids = input_ids.to(model.device)
            attention_mask = attention_mask.to(model.device)

        with torch.no_grad():
            output = model.generate(
                input_ids=input_ids,
                attention_mask=attention_mask,
                max_new_tokens=request.max_tokens,
                temperature=request.temperature,
                top_p=request.top_p,
                do_sample=True,
                pad_token_id=tokenizer.eos_token_id,
            )

        generated = output[0, input_ids.shape[1]:]
        text = tokenizer.decode(generated, skip_special_tokens=True)

        raw: Dict[str, Any] = {
            "model_id": self.model_id,
            "prompt_tokens": int(input_ids.shape[-1]),
            "output_tokens": int(generated.shape[-1]),
        }

        return ChatResponse(content=text, raw=raw)