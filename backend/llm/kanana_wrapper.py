import json
import logging
from typing import List, Dict, Any, Optional
from backend.llm.factory import fetch_llm_client
from backend.llm.base import ChatRequest, ChatMessage
from backend.common.config import LLM_MODEL_NAME

logger = logging.getLogger(__name__)

class KananaWrapper:
    """
    Kanana LLM Wrapper for Agent Tasks.
    Provides specific methods for hero scenarios.
    """
    def __init__(self):
        self.client = fetch_llm_client()
        self.model = LLM_MODEL_NAME

    def _call_llm(self, system_prompt: str, user_prompt: str, temperature: float = 0.7) -> str:
        try:
            # Logging metadata (Governance)
            logger.info(f"Calling LLM: model={self.model}, temp={temperature}")
            
            request = ChatRequest(
                messages=[
                    ChatMessage(role="system", content=system_prompt),
                    ChatMessage(role="user", content=user_prompt),
                ],
                model=self.model,
                temperature=temperature,
            )
            response = self.client.chat(request)
            
            # Log success (token usage if available in future)
            logger.info("LLM call successful")
            return response.content
        except Exception as e:
            logger.error(f"LLM call failed: {type(e).__name__} - {e}")
            raise e

    def generate_onboarding_plan(
        self, 
        repo_id: str, 
        diagnosis_summary: str, 
        user_context: Dict[str, Any],
        candidate_issues: List[Dict[str, Any]],
        max_retries: int = 2
    ) -> List[Dict[str, Any]]:
        """
        Generate a structured onboarding plan in Korean.
        Returns a list of weeks (dicts).
        Includes retry logic for JSON parsing errors.
        """
        # 난이도에 따른 설명 추가
        experience_level = user_context.get('experience_level', 'beginner')
        level_descriptions = {
            'beginner': '입문자 (프로그래밍을 막 시작했거나 이 기술 스택이 처음인 사람)',
            'intermediate': '중급자 (기본 개념은 알고 있고 실제 프로젝트 경험을 쌓고 싶은 사람)',
            'advanced': '숙련자 (경험이 많고 핵심 기여나 아키텍처 이해를 원하는 사람)'
        }
        level_desc = level_descriptions.get(experience_level, level_descriptions['beginner'])
        
        system_prompt = (
            "당신은 오픈소스 프로젝트 온보딩을 도와주는 전문 멘토입니다. "
            "새로운 기여자를 위한 체계적인 온보딩 플랜을 한국어로 작성하세요. "
            "반드시 유효한 JSON 배열만 반환하세요. 각 객체는 다음 필드를 포함해야 합니다:\n"
            "- 'week' (int): 주차 번호\n"
            "- 'goals' (list of strings): 해당 주의 목표들 (한국어)\n"
            "- 'tasks' (list of strings): 구체적인 할 일 목록 (한국어)\n\n"
            "마크다운 포맷(```json 등)을 사용하지 마세요. 순수 JSON만 반환하세요."
        )
        
        issues_text = "\n".join([f"- #{i['number']}: {i['title']}" for i in candidate_issues]) if candidate_issues else "추천 이슈 없음"
        
        user_prompt = (
            f"저장소: {repo_id}\n"
            f"프로젝트 요약: {diagnosis_summary}\n"
            f"사용자 난이도: {level_desc}\n"
            f"추천 이슈:\n{issues_text}\n\n"
            f"위 정보를 바탕으로 {experience_level} 수준에 맞는 1-4주 온보딩 플랜을 한국어로 생성하세요.\n"
            "각 주차마다 명확한 목표와 구체적인 태스크를 포함하세요.\n"
            "입문자의 경우 기초적인 내용부터, 숙련자의 경우 심화 내용을 포함하세요."
        )
        
        last_error = None
        
        for attempt in range(max_retries):
            try:
                response_text = self._call_llm(system_prompt, user_prompt, temperature=0.5)
                
                # Clean up markdown code blocks
                cleaned_text = response_text.strip()
                if cleaned_text.startswith("```json"):
                    cleaned_text = cleaned_text[7:]
                if cleaned_text.startswith("```"):
                    cleaned_text = cleaned_text[3:]
                if cleaned_text.endswith("```"):
                    cleaned_text = cleaned_text[:-3]
                cleaned_text = cleaned_text.strip()
                
                
                plan = json.loads(cleaned_text)
                
                # Validate structure
                if not isinstance(plan, list):
                    raise ValueError("Expected JSON array")
                
                return plan
                
            except json.JSONDecodeError as e:
                last_error = e
                logger.warning(f"JSON parse attempt {attempt + 1}/{max_retries} failed: {e}")
                if attempt < max_retries - 1:
                    # Retry with lower temperature
                    continue
            except ValueError as e:
                last_error = e
                logger.warning(f"Validation attempt {attempt + 1}/{max_retries} failed: {e}")
                if attempt < max_retries - 1:
                    continue
        
        # All retries failed
        logger.error(f"Failed to parse onboarding plan JSON after {max_retries} attempts")
        raise ValueError(f"LLM_JSON_PARSE_ERROR: {last_error}")

    def summarize_onboarding_plan(
        self, 
        repo_id: str, 
        plan: List[Dict[str, Any]]
    ) -> str:
        """
        Summarize the onboarding plan in a friendly, encouraging tone (Korean).
        """
        system_prompt = (
            "You are a helpful mentor. Summarize the provided onboarding plan in Korean. "
            "Use a friendly and encouraging tone. "
            "Do not use emojis. "
            "Format with clear sections."
        )
        
        plan_text = str(plan)
        
        user_prompt = (
            f"Repository: {repo_id}\n"
            f"Plan: {plan_text}\n\n"
            "Summarize this plan for the user."
        )
        
        return self._call_llm(system_prompt, user_prompt, temperature=0.7)
