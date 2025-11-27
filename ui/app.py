from __future__ import annotations

import os
import sys

# 프로젝트 루트(ODOCAIGENT)를 sys.path에 추가
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

import streamlit as st

from backend.agents.diagnosis.service import run_diagnosis

st.set_page_config(page_title="ODOC Diagnosis Agent", layout="centered")
st.title("ODOC Diagnosis Agent")

owner = st.text_input("GitHub Repository Owner", value="torvalds")
repo = st.text_input("GitHub Repository Name", value="linux")
task_type = st.selectbox(
    "Task Type", 
    ["full_diagnosis"]
)

if st.button("Run Diagnosis"):
  with st.spinner("Running Diagnosis Agent..."):
    payload = {
        "owner": owner,
        "repo": repo,
        "task_type": task_type,
        "focus": ["documentation", "activity"],
    }
    try:
      result = run_diagnosis(payload)
    except Exception as e:
        st.error(f"Error occurred: {e}")
    else:
       st.subheader("Repository Score")
       st.json(result["scores"])
       
       st.subheader("Diagnosis Details")
       st.json(result["details"])

       st.subheader("Summary")
       st.text(result["natural_language_summary_for_user"])