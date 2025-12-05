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
        candidate_issues: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Generate a structured onboarding plan.
        Returns a list of weeks (dicts).
        """
        system_prompt = (
            "You are an expert engineering mentor. "
            "Create a structured onboarding plan for a new contributor based on the repository diagnosis and user profile. "
            "Return ONLY a JSON array of objects, where each object represents a week with 'week' (int), 'goals' (list of strings), and 'tasks' (list of strings). "
            "Do not include markdown formatting like ```json."
        )
        
        issues_text = "\n".join([f"- #{i['number']}: {i['title']}" for i in candidate_issues])
        
        user_prompt = (
            f"Repository: {repo_id}\n"
            f"Diagnosis Summary: {diagnosis_summary}\n"
            f"User Profile: {user_context}\n"
            f"Recommended Issues:\n{issues_text}\n\n"
            "Generate a 1-4 week onboarding plan."
        )
        
        response_text = self._call_llm(system_prompt, user_prompt, temperature=0.5)
        
        # Parse JSON
        import json
        try:
            # Clean up if markdown code blocks are present
            cleaned_text = response_text.replace("```json", "").replace("```", "").strip()
            plan = json.loads(cleaned_text)
            return plan
        except json.JSONDecodeError:
            logger.error(f"Failed to parse onboarding plan JSON. Response length: {len(response_text)}")
            # Re-raise to let the node handle the fallback/error state
            raise ValueError("Invalid JSON response from LLM")

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
