from __future__ import annotations

import os
import sys

# 프로젝트 루트(ODOCAIGENT)를 sys.path에 추가
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

import streamlit as st

# from backend.agents.diagnosis.service import run_diagnosis
from backend.agents.supervisor.service import run_supervisor, SupervisorInput
from backend.common.github_client import clear_repo_cache, clear_all_cache

st.set_page_config(page_title="ODOC Diagnosis Agent", layout="centered")
st.title("ODOC Diagnosis Agent")

owner = st.text_input("GitHub Repository Owner", value="Hyeri-hci")
repo = st.text_input("GitHub Repository Name", value="OSSDoctor")
task_type = st.selectbox(
    "Task Type", 
    ["full_diagnosis", "docs_only", "activity_only"],
    index=0,
    format_func=lambda x:{
        "full_diagnosis": "full_diagnosis (문서 + 활동성)",
        "docs_only": "docs_only (문서만)",
        "activity_only": "activity_only (활동성만)",
    }[x],
)

# 고급 분석 모드 옵션
advanced_analysis = st.checkbox(
    "🔬 고급 분석 모드",
    value=False,
    help="카테고리별 상세 임베딩 요약을 생성합니다. (LLM 호출 5회, 기본 모드보다 느림)"
)

# 캐시 옵션
col1, col2 = st.columns(2)
with col1:
    force_refresh = st.checkbox(
        "🔄 캐시 무시 (새로 가져오기)",
        value=False,
        help="GitHub API 결과를 캐시에서 가져오지 않고 새로 요청합니다."
    )
with col2:
    if st.button("🗑️ 전체 캐시 삭제"):
        clear_all_cache()
        st.success("캐시가 삭제되었습니다.")

if st.button("Run Diagnosis", type="primary"):
      owner_clean = owner.strip()
      repo_clean = repo.strip()

      if not owner_clean or not repo_clean:
          st.error("Please enter both owner and repository name.")
      else:
        # 캐시 무시 옵션이 켜져 있으면 해당 repo 캐시 삭제
        if force_refresh:
            clear_repo_cache(owner_clean, repo_clean)
            
        try:
            with st.spinner("🔍 저장소 분석 중... (첫 요청 시 10-20초, 캐시 히트 시 더 빠름)"):
                sup_in = SupervisorInput(
                        user_query=f"{owner_clean}/{repo_clean} 저장소 상태를 진단해 주세요.",
                        owner=owner_clean,
                        repo=repo_clean,
                        language="ko",
                        user_level="beginner",
                        advanced_analysis=advanced_analysis,
                    )
                sup_out = run_supervisor(sup_in)
        except Exception as e:
                st.error(f"Error: {e}")
        else:
            diagnosis_result = sup_out.intermediate["diagnosis"]
            details = diagnosis_result.get("details", {})
            docs = details.get("docs", {})

            # 분석 모드 표시
            analysis_mode = details.get("analysis_mode", "basic")
            if analysis_mode == "advanced":
                st.success("🔬 고급 분석 모드로 실행됨 (카테고리별 상세 요약 포함)")
            else:
                st.info("⚡ 기본 모드로 실행됨 (빠른 통합 요약)")

            st.subheader("Repository Score")
            st.json(diagnosis_result["scores"])
            
            # README 요약 표시
            st.subheader("📄 README 요약")
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**🇺🇸 영어 (임베딩용)**")
                st.text_area(
                    "English Summary",
                    docs.get("readme_summary_for_embedding", ""),
                    height=150,
                    label_visibility="collapsed",
                )
            with col2:
                st.markdown("**🇰🇷 한국어 (사용자용)**")
                st.text_area(
                    "Korean Summary",
                    docs.get("readme_summary_for_user", ""),
                    height=150,
                    label_visibility="collapsed",
                )
            
            # 고급 분석 모드: 카테고리별 상세 요약 표시
            if analysis_mode == "advanced":
                st.subheader("🔬 카테고리별 상세 요약")
                readme_categories = docs.get("readme_categories", {})
                for cat_name in ["WHAT", "WHY", "HOW", "CONTRIBUTING"]:
                    cat_info = readme_categories.get(cat_name, {})
                    semantic_summary = cat_info.get("semantic_summary_en", "")
                    if semantic_summary:
                        with st.expander(f"📁 {cat_name}"):
                            st.write(semantic_summary)
            
            st.subheader("Detailed Diagnosis")
            st.json(diagnosis_result["details"])

            st.subheader("Supervisor Final Answer")
            st.text(sup_out.answer)
            