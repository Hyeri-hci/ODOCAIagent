import streamlit as st
from backend.diagnosis.service import diagnose_repo

st.title("Repository Health Diagnosis Test")
st.write("Enter a GitHub repository full name (e.g., 'owner/repo') to diagnose its health.")

default_repo = "microsoft/vscode"

full_name_input = st.text_input(
    "Repository (owner/repo):", 
    value=default_repo,
    help="Enter the full name of the GitHub repository in the format 'owner/repo'."
)

if st.button("진단 실행"):
  if "/" not in full_name_input:
      st.error("Invalid repository name format. Please use 'owner/repo'.")

  else:
      with st.spinner("Diagnosing repository..."):
          try:
              diagnosis_result = diagnose_repo(full_name_input)
              st.success("Diagnosis Complete!")
              
              st.subheader("Health Score")
              st.metric(label="Health Score", value=f"{diagnosis_result.health_score}")

              st.subheader("Diagnosis Details")
              st.write(f"**Activity Level:** {diagnosis_result.activity_level}")
              st.write(f"**Maintenance Level:** {diagnosis_result.maintenance_level}")
              st.write(f"**Issue Responsiveness:** {diagnosis_result.issue_responsiveness}")
              if diagnosis_result.recommendations:
                  st.info(f"**Recommendations:** {diagnosis_result.recommendations}")
          
          except Exception as e:
              st.error(f"An error occurred during diagnosis: {e}")