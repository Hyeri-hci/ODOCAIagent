"""
Example Selector for Few-shot Prompting
"""
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
import yaml
import random

logger = logging.getLogger(__name__)

class IntentExampleSelector:
    """
    사용자 입력과 유사한 의도(Intent) 예시를 검색하는 Selector.
    Dependency-free (Jaccard Similarity) version.
    """
    
    def __init__(self, examples_path: str = "backend/prompts/intent_examples.yaml", k: int = 3):
        self.k = k
        self.examples = self._load_examples(examples_path)
        
    def _load_examples(self, path: str) -> List[Dict[str, str]]:
        """YAML 파일에서 예제 로드"""
        try:
            # 절대 경로 계산 (backend 루트 기준)
            base_dir = Path(__file__).parent.parent.parent
            full_path = base_dir / path
            
            if not full_path.exists():
                logger.warning(f"Intent examples file not found at {full_path}")
                return []
                
            with open(full_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                return data.get("examples", [])
        except Exception as e:
            logger.error(f"Failed to load intent examples: {e}")
            return []

    def _calculate_jaccard_similarity(self, str1: str, str2: str) -> float:
        """단순 자카드 유사도 계산 (토큰 기반)"""
        set1 = set(str1.lower().split())
        set2 = set(str2.lower().split())
        
        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))
        
        if union == 0:
            return 0.0
        return intersection / union

    def select_examples(self, query: str) -> List[Dict[str, str]]:
        """쿼리와 가장 유사한 예제 선택"""
        if not self.examples:
            return []
            
        # 유사도 점수 계산
        scored_examples = []
        for ex in self.examples:
            score = self._calculate_jaccard_similarity(query, ex['input'])
            scored_examples.append((score, ex))
            
        # 점수 내림차순 정렬
        scored_examples.sort(key=lambda x: x[0], reverse=True)
        
        # 상위 K개 선택
        # 점수가 0인 경우(전혀 안 겹침)에도 일부 예제를 보여주는 것이 좋을 수 있음 (Random fallback or just top K)
        selected = [ex for score, ex in scored_examples[:self.k]]
        
        return selected

# 싱글톤 인스턴스
_selector_instance = None

def get_example_selector() -> IntentExampleSelector:
    global _selector_instance
    if _selector_instance is None:
        _selector_instance = IntentExampleSelector()
    return _selector_instance
