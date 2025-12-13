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
        from backend.prompts.loader import load_prompt, render_prompt

        # 난이도에 따른 설명 추가
        experience_level = user_context.get('experience_level', 'beginner')
        level_descriptions = {
            'beginner': '입문자 (프로그래밍을 막 시작했거나 이 기술 스택이 처음인 사람)',
            'intermediate': '중급자 (기본 개념은 알고 있고 실제 프로젝트 경험을 쌓고 싶은 사람)',
            'advanced': '숙련자 (경험이 많고 핵심 기여나 아키텍처 이해를 원하는 사람)'
        }
        level_desc = level_descriptions.get(experience_level, level_descriptions['beginner'])
        
        # 난이도별 구체적 지침
        level_guidelines = {
            'beginner': '- good first issue나 docs 라벨의 쉬운 이슈로 시작하세요\n- 프로젝트 구조 이해와 환경 설정에 초점\n- 첫 PR은 문서 수정이나 간단한 버그 수정 권장',
            'intermediate': '- help wanted, enhancement, bug 라벨의 이슈를 다루세요\n- 기능 개선이나 버그 수정에 초점\n- 코드 리뷰와 테스트 작성 경험을 쌓도록 계획\n- good first issue는 언급하지 마세요',
            'advanced': '- core, architecture, performance, security 관련 이슈를 다루세요\n- 아키텍처 이해와 핵심 모듈 분석에 초점\n- 성능 최적화나 보안 개선 작업 권장\n- 입문자용 내용(good first issue 등)은 언급하지 마세요'
        }
        level_guideline = level_guidelines.get(experience_level, level_guidelines['beginner'])
        
        # 프롬프트 로드
        prompt_data = load_prompt("onboarding_prompts")
        plan_gen_prompt = prompt_data.get("plan_generation", {})
        
        system_prompt = plan_gen_prompt.get("system_prompt", "")
        
        issues_text = "\n".join([f"- #{i['number']}: {i['title']}" for i in candidate_issues]) if candidate_issues else "추천 이슈 없음"
        
        # 유동적인 주차 수 (기본 1-4주)
        weeks = user_context.get("weeks", "1-4")

        user_prompt = render_prompt(
            "onboarding_prompts", 
            template_key="plan_generation", # loader가 딕셔너리를 지원하는지 확인 필요 (지원 X시 아래처럼 수동 포맷)
        )
        # render_prompt는 키가 'user_prompt_template'라고 가정하거나 직접 텍스트를 받지 않음.
        # loader.py의 render_prompt는 YAML의 특정 키 값을 템플릿으로 사용함.
        # onboarding_prompts.yaml 구조: plan_generation: { system_prompt: ..., user_prompt_template: ... }
        # 따라서 render_prompt를 쓰려면 loader.py 수정이 필요할 수 있음.
        # 현재 loader.py는 `prompt.get(template_key)`를 수행함.
        # 만약 template_key가 'plan_generation'이면 딕셔너리가 반환됨 -> format 실패.
        
        # 해결책:
        # loader.py를 수정하지 않고 여기서 직접 format
        user_template = plan_gen_prompt.get("user_prompt_template", "")
        
        # Context-Aware Section extraction
        previous_context_section = user_context.get("previous_context_section", "")

        try:
            user_prompt = user_template.format(
                repo_id=repo_id,
                diagnosis_summary=diagnosis_summary,
                level_desc=level_desc,
                experience_level_upper=experience_level.upper(),
                level_guideline=level_guideline,
                issues_text=issues_text,
                experience_level=experience_level,
                weeks=weeks,
                previous_context_section=previous_context_section
            )
        except Exception:
            # fallback formatting
            user_prompt = user_template.replace("{repo_id}", str(repo_id))\
                .replace("{diagnosis_summary}", str(diagnosis_summary))\
                .replace("{level_desc}", str(level_desc))\
                .replace("{experience_level_upper}", experience_level.upper())\
                .replace("{level_guideline}", str(level_guideline))\
                .replace("{issues_text}", str(issues_text))\
                .replace("{experience_level}", str(experience_level))\
                .replace("{weeks}", str(weeks))\
                .replace("{previous_context_section}", str(previous_context_section))
        
        last_error = None
        
        for attempt in range(max_retries):
            try:
                # 재시도 시 temperature 점진적으로 낮추기 (0.5 -> 0.3 -> 0.1)
                current_temp = max(0.1, 0.5 - (attempt * 0.2))
                response_text = self._call_llm(system_prompt, user_prompt, temperature=current_temp)
                
                # Clean up markdown code blocks (강화된 클리닝)
                cleaned_text = response_text.strip()
                
                # 마크다운 코드 블록 제거
                if cleaned_text.startswith("```json"):
                    cleaned_text = cleaned_text[7:]
                elif cleaned_text.startswith("```"):
                    cleaned_text = cleaned_text[3:]
                if cleaned_text.endswith("```"):
                    cleaned_text = cleaned_text[:-3]
                cleaned_text = cleaned_text.strip()
                
                # 추가 클리닝: JSON 배열 시작/끝 찾기
                start_idx = cleaned_text.find('[')
                end_idx = cleaned_text.rfind(']')
                if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                    cleaned_text = cleaned_text[start_idx:end_idx+1]
                
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
        from backend.prompts.loader import load_prompt
        
        prompt_data = load_prompt("onboarding_prompts")
        summary_prompt_config = prompt_data.get("plan_summary", {})
        
        system_prompt = summary_prompt_config.get("system_prompt", "System prompt not found")
        user_template = summary_prompt_config.get("user_prompt_template", "User template not found")
        
        plan_text = str(plan)
        
        try:
            user_prompt = user_template.format(
                repo_id=repo_id,
                plan_text=plan_text
            )
        except Exception:
            user_prompt = user_template.replace("{repo_id}", str(repo_id)).replace("{plan_text}", plan_text)
        
        return self._call_llm(system_prompt, user_prompt, temperature=0.7)
