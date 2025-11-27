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

st.set_page_config(page_title="ODOC Diagnosis Agent", layout="centered")
st.title("ODOC Diagnosis Agent")

owner = st.text_input("GitHub Repository Owner", value="microsoft")
repo = st.text_input("GitHub Repository Name", value="vscode")
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

if st.button("Run Diagnosis"):
      owner_clean = owner.strip()
      repo_clean = repo.strip()

      if not owner_clean or not repo_clean:
          st.error("Please enter both owner and repository name.")
      else:
        try:
            sup_in = SupervisorInput(
                    user_query=f"{owner_clean}/{repo_clean} 저장소 상태를 진단해 주세요.",
                    owner=owner_clean,
                    repo=repo_clean,
                    language="ko",
                    user_level="beginner",
                )
            sup_out = run_supervisor(sup_in)
        except Exception as e:
                st.error(f"Error: {e}")
        else:
            diagnosis_result = sup_out.intermediate["diagnosis"]

            st.subheader("Repository Score")
            st.json(diagnosis_result["scores"])
            
            st.subheader("Detailed Diagnosis")
            st.json(diagnosis_result["details"])

            st.subheader("Supervisor Final Answer")
            st.text(sup_out.answer)
            