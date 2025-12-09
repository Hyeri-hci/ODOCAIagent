# core/ingest/summarizer.py

import asyncio
from typing import List
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.output_parsers import StrOutputParser
from config.setting import settings

class ContentSummarizer:
    """
    [Core Logic: Map-Reduce Summarization]
    긴 문서를 청킹하여 병렬로 요약하고, 최종적으로 종합하는 요약기입니다.
    """
    
    def __init__(self):
        # 요약은 속도가 중요하므로 가벼운 모델 권장 (설정에 따름)
        self.llm = ChatOpenAI(
            base_url=settings.llm.api_base,
            api_key=settings.llm.api_key,
            model=settings.llm.model_name,
            temperature=0
        )
        
        # 1. 텍스트 분할기 (Chunker)
        # README는 코드 블록이 많으므로 넉넉하게 자릅니다.
        # chunk_size=8000 (약 2000 토큰)
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=8000,
            chunk_overlap=500,
            separators=["\n## ", "\n### ", "\n\n", "\n", " ", ""]
        )

        # 2. Map Prompt (각 조각 요약)
        self.map_prompt = ChatPromptTemplate.from_messages([
            ("system", """
            You are a Technical Document Summarizer.
            Summarize the provided section of a GitHub README.
            Capture key features, tech stack, and installation steps if present.
            Keep it concise.
            """),
            ("user", "{text}")
        ])

        # 3. Reduce Prompt (최종 종합)
        self.reduce_prompt = ChatPromptTemplate.from_messages([
            ("system", """
            You are a Senior Tech Writer.
            Below is a collection of summaries from a project's README.
            Synthesize them into a single, structured summary.
            
            ### Output Format
            1. **Overview**: One sentence explaining what this project is.
            2. **Key Features**: Bullet points of main capabilities.
            3. **Tech Stack**: Languages, Frameworks, Tools used.
            4. **Use Case**: Best scenarios to use this project.
            
            Keep the total length under 500 words.
            """),
            ("user", "{text}")
        ])

    async def summarize(self, readme_text: str) -> str:
        """
        README 텍스트를 입력받아 구조화된 요약본을 반환합니다.
        (자동으로 Stuff 방식과 Map-Reduce 방식을 스위칭합니다)
        """
        if not readme_text or len(readme_text.strip()) == 0:
            return "No README content available."

        # 길이가 짧으면(약 2500 토큰 이하) 그냥 한 번에 요약 (Stuff)
        if len(readme_text) < 10000:
            return await self._summarize_stuff(readme_text)
        
        # 길이가 길면 쪼개서 요약 (Map-Reduce)
        return await self._summarize_map_reduce(readme_text)

    async def _summarize_stuff(self, text: str) -> str:
        """단일 호출 요약"""
        try:
            chain = self.reduce_prompt | self.llm | StrOutputParser()
            return await chain.ainvoke({"text": text})
        except Exception as e:
            print(f"[Summarizer] Stuff Error: {e}")
            return "Failed to summarize text."

    async def _summarize_map_reduce(self, text: str) -> str:
        """병렬 분할 요약"""
        print(f"[Summarizer] Starting Map-Reduce for long text ({len(text)} chars)...")
        try:
            # 1. 청킹
            docs = self.splitter.create_documents([text])
            print(f"[Summarizer] Split into {len(docs)} chunks.")
            
            # 2. Map Phase (Async Parallel Execution)
            map_chain = self.map_prompt | self.llm | StrOutputParser()
            
            # 모든 청크를 동시에 요약 요청 (속도 최적화)
            tasks = [map_chain.ainvoke({"text": doc.page_content}) for doc in docs]
            chunk_summaries = await asyncio.gather(*tasks)
            
            # 3. Reduce Phase
            combined_text = "\n---\n".join(chunk_summaries)
            final_summary = await self._summarize_stuff(combined_text)
            
            return final_summary

        except Exception as e:
            print(f"[Summarizer] Map-Reduce Error: {e}")
            # 에러 발생 시 앞부분만 잘라서 Stuff 시도 (Fallback)
            return await self._summarize_stuff(text[:10000])