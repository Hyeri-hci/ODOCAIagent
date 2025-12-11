# agent/tool_registry.py

from typing import Dict, Callable
from tools.search_query_generator_tool import github_search_query_generator # (이름 확인 필요)
from tools.github_search_tool import github_search_tool
from tools.github_filter_tool import github_filter_tool
from tools.github_ingest_tool import github_ingest_tool
from tools.rag_query_generator_tool import rag_query_generator
from tools.qdrant_search_executor import qdrant_search_executor
from tools.github_trend_search_tool import github_trend_search_tool # [NEW]

class ToolRegistry:
    def __init__(self):
        self.tools: Dict[str, Callable] = {}
        self.tool_descriptions: Dict[str, str] = {}

    def register(self, tool_func: Callable, category: str = "general"):
        name = tool_func.name
        description = tool_func.description
        self.tools[name] = tool_func
        self.tool_descriptions[name] = description
        print(f"[ToolRegistry] Registered '{name}' (Category: {category})")

    def get_all_tools(self) -> Dict[str, Callable]:
        return self.tools

    def get_descriptions(self) -> str:
        lines = []
        for name, desc in self.tool_descriptions.items():
            lines.append(f"- **{name}**: {desc}")
        return "\n".join(lines)

_registry = ToolRegistry()

# 1. Search Tools
_registry.register(github_search_query_generator, category="search")
_registry.register(github_search_tool, category="search")
_registry.register(github_filter_tool, category="search")
_registry.register(github_trend_search_tool, category="search") # [NEW]

# 2. Analysis Tools
_registry.register(github_ingest_tool, category="analysis")

# 3. RAG Tools
_registry.register(rag_query_generator, category="rag")
_registry.register(qdrant_search_executor, category="rag")

TOOLS_MAP = _registry.get_all_tools()