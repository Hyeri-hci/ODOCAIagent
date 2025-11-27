from __future__ import annotations

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL_ID = "kakaocorp/kanana-1.5-8b-instruct-2505"

def main() -> None:
    # 모델 및 토크나이저 로드
    print("Loading model and tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
    print("Loading model...")
    # GPU 사용 가능 시 GPU로 로드
    if torch.cuda.is_available():
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_ID,
            torch_dtype=torch.bfloat16,
            device_map="auto",
            trust_remote_code=True,
        )
    else:
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_ID,
            torch_dtype=torch.float32,
            device_map="cpu",
            trust_remote_code=True,
        )

    messages = [
        {"role": "system", "content": "당신은 한국어를 잘하는 친절한 도우미입니다."},
        {"role": "user", "content": "Kanana 1.5 모델을 한 문장으로 설명해 주세요."},
    ]

    prompt = tokenizer.apply_chat_template(
        messages,
        tokenizer=True,
        add_generation_prompt=True,
        return_tensors="pt",
    )

    if torch.cuda.is_available():
        prompt = prompt.to(model.device)

    print("Generating response...")
    with torch.no_grad():
        output = model.generate(
            prompt,
            max_new_tokens=256,
            do_sample=True,
            top_p=0.9,
            temperature=0.2,
            pad_token_id=tokenizer.eos_token_id,
        )
        
    generated = output[0][prompt.shape[-1]:]
    text = tokenizer.decode(generated, skip_special_tokens=True)
    print("Response:")
    print(text)

if __name__ == "__main__":
    main()