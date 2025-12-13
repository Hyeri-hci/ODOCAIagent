"""
Finalize Handler Node
Supervisor에서 최종 답변을 생성하고 포맷팅하는 노드입니다.
"""

import logging
from typing import Dict, Any

from backend.agents.supervisor.models import SupervisorState
from backend.agents.shared.metacognition import Source
from backend.agents.supervisor.metacognition import format_response_with_sources
from backend.agents.supervisor.utils import enhance_answer_with_context

logger = logging.getLogger(__name__)

async def finalize_answer_node(state: SupervisorState) -> Dict[str, Any]:
    """
    최종 답변 생성 (메타인지 + 근거 포함)
    
    - 대명사 해결 컨텍스트 포함
    - 분석에 사용된 파일 근거 링크 포함
    - 품질/신뢰도 정보 포함
    """
    logger.info("Finalizing answer")
    
    # 메인 에이전트 결과 (target_agent 기준으로 가져오기)
    target_agent = state.get("target_agent")
    multi_agent_results = state.get("multi_agent_results", {})
    
    # 메인 에이전트 결과 우선 사용
    agent_result = state.get("agent_result")
    if target_agent and target_agent in multi_agent_results:
        agent_result = multi_agent_results[target_agent]
        logger.info(f"Using main agent result from multi_agent_results: {target_agent}")
    
    # diagnosis_result가 있으면 우선 사용 (진단 요청의 경우)
    diagnosis_result = state.get("diagnosis_result")
    if diagnosis_result and target_agent == "diagnosis":
        agent_result = diagnosis_result
        logger.info("Using diagnosis_result for finalization")
    
    if not agent_result:
        return {"final_answer": "결과를 생성할 수 없습니다.", "error": "No agent result"}
    
    # 대명사 해결 정보 가져오기
    accumulated_context = state.get("accumulated_context", {})
    pronoun_info = accumulated_context.get("last_pronoun_reference", {})
    user_message = state.get("user_message", "") or ""
    
    # 저장소 정보 요청 처리 (GitHub에서 저장소를 찾은 경우)
    if accumulated_context.get("found_repo_info"):
        repo_info = accumulated_context.get("last_mentioned_repo", {})
        if repo_info:
            owner = repo_info.get("owner", "")
            repo = repo_info.get("repo", "")
            full_name = repo_info.get("full_name", f"{owner}/{repo}")
            description = repo_info.get("description", "")
            stars = repo_info.get("stars", 0)
            url = repo_info.get("url", f"https://github.com/{owner}/{repo}")
            
            # 저장소 정보 응답 생성
            answer_parts = [
                f"**{full_name}** 저장소를 찾았습니다!\n",
                f"- **URL**: [{url}]({url})",
                f"- **스타**: {stars:,}",
            ]
            if description:
                answer_parts.insert(1, f"- **설명**: {description}")
            
            answer_parts.append("\n이 저장소를 **분석**하거나 **기여 가이드**를 받고 싶으시면 말씀해주세요.")
            
            answer = "\n".join(answer_parts)
            logger.info(f"Returning found repo info: {full_name}")
            
            return {
                "final_answer": answer,
                "owner": owner,
                "repo": repo,
                "agent_result": {
                    "type": "repo_info",
                    "owner": owner,
                    "repo": repo,
                    "url": url,
                    "description": description,
                    "stars": stars
                }
            }
    
    # 대명사 참조가 있는 경우 컨텍스트 데이터 가져오기
    referenced_data = None
    if pronoun_info.get("resolved") and pronoun_info.get("confidence", 0) > 0.5:
        refers_to = pronoun_info.get("refers_to")
        if refers_to and refers_to in accumulated_context:
            referenced_data = accumulated_context.get(refers_to)
            logger.info(f"Using referenced data from: {refers_to}")
    
    # 구조 요청 감지 (코드 구조, 폴더 구조, 트리 구조 등)
    structure_keywords = ["구조", "structure", "트리", "tree", "폴더", "folder", "디렉토리", "directory"]
    is_structure_request = any(kw in user_message.lower() for kw in structure_keywords)
    
    if is_structure_request:
        # 세션에서 structure_visualization 확인
        structure_viz = accumulated_context.get("structure_visualization")
        diagnosis_result = accumulated_context.get("diagnosis_result")
        
        owner = state.get("owner", "")
        repo = state.get("repo", "")
        
        if structure_viz:
            # 이미 구조 시각화가 있으면 반환
            answer = f"## {owner}/{repo} 코드 구조\n\n코드 구조는 우측 리포트의 '구조' 탭에서 확인할 수 있습니다."
            logger.info("Returning existing structure_visualization")
            return {"final_answer": answer, "structure_visualization": structure_viz}
        elif diagnosis_result:
            # 진단 결과에서 구조 정보 추출
            file_tree = diagnosis_result.get("file_tree", diagnosis_result.get("structure", {}))
            if file_tree:
                answer = f"## {owner}/{repo} 코드 구조\n\n진단 결과에서 코드 구조를 확인할 수 있습니다."
                logger.info("Returning structure from diagnosis_result")
                return {"final_answer": answer, "agent_result": {"type": "structure", "file_tree": file_tree}}
        
        # 구조 정보가 없으면 contributor 에이전트 결과 사용
        logger.info("No cached structure, using agent_result")
    
    # 결과 타입에 따라 답변 포맷팅
    result_type = agent_result.get("type", "unknown")
    
    if result_type == "full_diagnosis":
        # 진단 결과 요약
        owner = agent_result.get("owner", state.get("owner", ""))
        repo = agent_result.get("repo", state.get("repo", ""))
        health_score = agent_result.get("health_score", 0)
        onboarding_score = agent_result.get("onboarding_score", 0)
        health_level = agent_result.get("health_level", "")
        docs_score = agent_result.get("docs_score", 0)
        activity_score = agent_result.get("activity_score", 0)
        
        # 요약 (llm_summary가 있으면 사용, 없으면 구성)
        summary = agent_result.get("llm_summary", "")
        if not summary:
            # llm_summary가 없으면 직접 구성
            warnings = agent_result.get("warnings", [])
            recommendations = agent_result.get("recommendations", [])
            
            summary_parts = []
            if health_score >= 80:
                summary_parts.append(f"전반적으로 건강한 저장소입니다.")
            elif health_score >= 60:
                summary_parts.append(f"보통 수준의 건강도를 보입니다.")
            else:
                summary_parts.append(f"개선이 필요한 상태입니다.")
            
            if warnings:
                summary_parts.append(f"주의사항: {', '.join(warnings[:2])}")
            
            summary = " ".join(summary_parts)
        
        # 주요 발견사항
        key_findings = agent_result.get("key_findings", [])
        findings_text = ""
        if key_findings:
            for finding in key_findings[:3]:
                title = finding.get('title', '')
                desc = finding.get('description', '')
                if title and desc:
                    findings_text += f"- **{title}**: {desc}\n"
                elif title:
                    findings_text += f"- {title}\n"
        else:
            # key_findings가 없으면 recommendations 사용
            recommendations = agent_result.get("recommendations", [])
            if recommendations:
                for rec in recommendations[:3]:
                    findings_text += f"- {rec}\n"
        
        answer = f"""## {owner}/{repo} 진단 결과

**건강도:** {health_score}/100
**온보딩 점수:** {onboarding_score}/100
**문서화 점수:** {docs_score}/100
**활동성 점수:** {activity_score}/100

{summary}

**주요 발견사항:**
{findings_text if findings_text else "- 특이사항 없음"}
"""
        
        # 근거 링크 추가 (메타인지) - 실제 존재하는 파일만 추가
        analyzed_files = []
        
        # documentation 결과에서 실제 존재하는 파일 확인
        documentation = agent_result.get("documentation", {})
        if isinstance(documentation, dict):
            if documentation.get("readme_present"):
                analyzed_files.append("README.md")
            if documentation.get("contributing_present"):
                analyzed_files.append("CONTRIBUTING.md")
            if documentation.get("license_present"):
                analyzed_files.append("LICENSE")
        
        # dependencies 결과에서 실제 분석된 파일 확인
        dependencies = agent_result.get("dependencies", {})
        if isinstance(dependencies, dict):
            dep_analyzed_files = dependencies.get("analyzed_files", [])
            if dep_analyzed_files:
                analyzed_files.extend(dep_analyzed_files[:3])  # 최대 3개
        
        # structure 결과에서 빌드 파일 확인
        structure = agent_result.get("structure", {})
        if isinstance(structure, dict):
            build_files = structure.get("build_files", [])
            if build_files:
                analyzed_files.extend(build_files[:2])  # 최대 2개
        
        if analyzed_files:
            sources = []
            seen = set()
            for file_path in analyzed_files:
                if file_path and file_path not in seen:
                    seen.add(file_path)
                    sources.append(Source(
                        url=f"https://github.com/{owner}/{repo}/blob/main/{file_path}",
                        title=file_path,
                        type="file"
                    ))
            if sources:
                answer = format_response_with_sources(answer, sources, max_sources=5)
        
        # 프로액티브 제안 (점수 기반 조건부 생성)
        suggested_actions = []
        
        # 건강도가 낮으면 보안 점검 추천
        if health_score < 50:
            suggested_actions.append({
                "action": "보안 취약점 점검 추천",
                "type": "security",
                "reason": f"건강도가 {health_score}점으로 낮습니다. 보안 점검을 권장합니다."
            })
        
        # 온보딩 점수가 높으면 기여 가이드 추천
        if onboarding_score >= 70:
            suggested_actions.append({
                "action": "기여 가이드 생성 가능",
                "type": "onboarding",
                "reason": f"온보딩 점수가 {onboarding_score}점으로 높습니다. 기여 가이드를 만들어 보세요."
            })
        
        # 기본 제안 추가
        suggested_actions.extend([
            {"action": "온보딩 가이드 만들기", "type": "onboarding"},
            {"action": "보안 스캔 실행", "type": "security"}
        ])
        
        # AI 판단 근거 (Agentic 요소 가시화)
        decision_reason = state.get("decision_reason", "")
        supervisor_intent = state.get("supervisor_intent", {})
        reasoning = supervisor_intent.get("reasoning", "") if isinstance(supervisor_intent, dict) else ""
        
        # 다음 단계 안내 (진단→온보딩 연결)
        next_steps = """
---
**다음 단계:**
이 저장소에 기여하고 싶다면 `온보딩 가이드 만들어줘`라고 말해보세요!
보안 취약점이 걱정된다면 `보안 분석해줘`라고 요청하세요.
"""
        
        # AI 판단 근거 (로그에만 기록, UI에는 표시 안 함)
        if reasoning or decision_reason:
            logger.info(f"[AI 판단 과정] {reasoning or decision_reason}")
        
        answer = answer + next_steps
        
        return {
            "final_answer": answer,
            "suggested_actions": suggested_actions,
            "decision_trace": {
                "reasoning": reasoning,
                "decision_reason": decision_reason,
                "target_agent": state.get("target_agent"),
                "intent_confidence": state.get("intent_confidence", 0)
            }
        }
    
    elif result_type == "error":
        error_code = agent_result.get("error_code", "UNKNOWN_ERROR")
        error_msg = agent_result.get("error", "알 수 없는 오류가 발생했습니다.")
        owner = agent_result.get("owner", state.get("owner"))
        repo = agent_result.get("repo", state.get("repo"))
        
        answer = f"⚠️ **분석 중 오류가 발생했습니다**\n\n"
        
        if error_code == "REPO_NOT_FOUND":
            answer += f"**{owner}/{repo}** 저장소를 찾을 수 없습니다.\n"
            answer += "- 저장소 이름이 정확한지 확인해주세요.\n"
            answer += "- Private 저장소라면 접근 권한이 필요할 수 있습니다.\n"
        elif error_code == "GITHUB_API_ERROR":
            answer += f"GitHub API 호출 중 문제가 발생했습니다.\n"
            answer += f"오류 메시지: {error_msg}\n"
        else:
            answer += f"{error_msg}\n"
            
        return {
            "final_answer": answer,
            "error_code": error_code,
            "error": error_msg
        }
    
    elif result_type == "quick_query":
        # 빠른 조회 결과
        target = agent_result.get("target", "")
        data = agent_result.get("data", {})
        
        answer = f"## {target.upper()} 정보\n\n"
        
        if target == "readme":
            content = data.get("content", "")
            answer += content[:500] + "..." if len(content) > 500 else content
        else:
            answer += str(data)
        
        return {"final_answer": answer}
    
    elif result_type == "reinterpret":
        # 재해석 결과
        return {"final_answer": agent_result.get("reinterpreted_answer", "")}
    
    elif result_type == "contributor_guide":
        # 기여 가이드 결과 (마크다운 형태)
        owner = state.get("owner", "")
        repo = state.get("repo", "")
        summary = agent_result.get("summary", f"{owner}/{repo} 기여 가이드가 생성되었습니다.")
        matched_issues = agent_result.get("matched_issues", [])
        total_issues = agent_result.get("total_issues", 0)
        
        # 이슈 추천 결과인 경우
        if matched_issues:
            issue_count = len(matched_issues)
            answer = f"""**🎯 {summary}**

"""
            # 전체 이슈 목록 표시 (리포트 대신 채팅에서 바로 표시)
            for i, issue in enumerate(matched_issues, 1):
                title = issue.get("title", "제목 없음")
                number = issue.get("number", "")
                url = issue.get("url", f"https://github.com/{owner}/{repo}/issues/{number}")
                labels = issue.get("labels", [])
                label_names = [l.get("name", l) if isinstance(l, dict) else str(l) for l in labels[:2]]
                label_str = " ".join([f"`{l}`" for l in label_names]) if label_names else ""
                score = issue.get("match_score", 0)
                reasons = issue.get("match_reasons", [])
                reason_str = ", ".join(reasons[:2]) if reasons else "초보자 친화적"
                
                answer += f"### {i}. [{title}]({url})\n"
                answer += f"   - **이슈**: #{number} {label_str}\n"
                answer += f"   - **추천 이유**: {reason_str}\n"
                if score:
                    answer += f"   - **매칭 점수**: {score}점\n"
                answer += "\n"
            
            answer += f"\n---\n💡 **팁**: `good first issue` 라벨이 있는 이슈는 메인테이너가 초보자에게 적합하다고 표시한 것입니다."
        elif total_issues == 0:
            # 이슈가 없는 경우
            answer = f"""**{owner}/{repo}에서 초보자 친화적 이슈를 찾지 못했습니다.**

😅 **이유**: 현재 `good first issue`, `help wanted` 등의 라벨이 붙은 열린 이슈가 없습니다.

**대안 제안:**
1. 📖 [이슈 페이지](https://github.com/{owner}/{repo}/issues) 직접 확인하기
2. 📝 문서 개선이나 오타 수정으로 시작하기
3. 🔍 `docs`, `documentation` 라벨 이슈 찾아보기
4. 💬 Discussion에서 기여 방법 문의하기
"""
        else:
            # 일반 기여 가이드
            answer = f"""**{summary}**

📖 **상세 가이드는 우측 리포트에서 확인하세요**

이 가이드에서 다루는 내용:
- 프로젝트 환경 설정
- Fork & Clone 방법
- 브랜치 생성 및 커밋 규칙
- PR 작성 가이드
"""
        
        return {
            "final_answer": answer,
            "agent_result": agent_result,
            "contributor_guide": agent_result
        }
    
    elif result_type == "structure":
        # 코드 구조 시각화 결과
        owner = state.get("owner", "")
        repo = state.get("repo", "")
        structure_viz = agent_result.get("structure_visualization", {})
        summary = agent_result.get("summary", f"{owner}/{repo} 프로젝트 코드 구조입니다.")
        
        answer = f"""**{summary}**

🌳 **코드 구조는 우측 리포트에서 확인하세요**

다이어그램 또는 트리 뷰로 프로젝트 구조를 확인할 수 있습니다.
"""
        
        return {
            "final_answer": answer,
            "agent_result": agent_result,
            "structure_visualization": structure_viz
        }
    
    elif result_type == "onboarding_plan":
        # 온보딩 플랜 결과
        plan = agent_result.get("plan", [])
        summary = agent_result.get("summary", "")
        is_regenerated = agent_result.get("is_regenerated", False)
        
        # 재생성 여부에 따른 메시지 prefix
        regen_prefix = "🔄 " if is_regenerated else ""
        
        if plan and isinstance(plan, list) and len(plan) > 0:
            # plan이 리스트인 경우 (주차별 플랜)
            step_lines = []
            for i, step in enumerate(plan[:5]):
                if isinstance(step, dict):
                    title = step.get('title') or f"Week {step.get('week', i+1)}"
                    goals = step.get('goals', [])
                    goals_preview = goals[0] if goals else ''
                    step_lines.append(f"{i+1}. **{title}**: {goals_preview[:50]}")
            steps_preview = "\n".join(step_lines)
            more_steps = "\n... (더 보기)" if len(plan) > 5 else ""
            
            answer = f"""{regen_prefix}**온보딩 플랜 생성 완료**

{summary}

**주차별 목표:**
{steps_preview if steps_preview else "- 상세 내용은 리포트를 확인하세요"}{more_steps}

📊 **상세 내용은 우측 리포트에서 확인하세요**
"""
        elif plan and isinstance(plan, dict):
            # plan이 dict인 경우
            steps_preview = "\n".join([
                f"{i+1}. {step.get('title', '')}" 
                for i, step in enumerate(plan.get('steps', [])[:5]) if isinstance(step, dict)
            ])
            more_steps = "\n... (더 보기)" if len(plan.get('steps', [])) > 5 else ""
            prereqs = ', '.join(plan.get('prerequisites', [])[:3])
            difficulty = plan.get('difficulty', 'normal')
            
            answer = f"""{regen_prefix}**온보딩 플랜 생성 완료**

{summary}

**주요 단계:**
{steps_preview if steps_preview else "- 상세 단계는 플랜을 참조하세요"}{more_steps}

**난이도:** {difficulty}
{"**필요 사전지식:** " + prereqs if prereqs else ""}

📊 **상세 내용은 우측 리포트에서 확인하세요**
"""
        else:
            answer = f"{regen_prefix}**온보딩 플랜**\n\n{agent_result.get('message', '온보딩 플랜이 생성되었습니다.')}\n\n📊 **상세 내용은 우측 리포트에서 확인하세요**"
        
        return {
            "final_answer": answer,
            "onboarding_result": agent_result,
            "agent_result": agent_result
        }
    
    elif result_type == "security_scan":
        # 보안 분석 결과
        results = agent_result.get("results", {})
        security_score = results.get("security_score", agent_result.get("security_score"))
        security_grade = results.get("security_grade", agent_result.get("security_grade", "N/A"))
        risk_level = results.get("risk_level", agent_result.get("risk_level", "unknown"))
        vulnerabilities = results.get("vulnerabilities", {})
        vuln_total = vulnerabilities.get("total", 0)
        vuln_critical = vulnerabilities.get("critical", 0)
        vuln_high = vulnerabilities.get("high", 0)
        vuln_medium = vulnerabilities.get("medium", 0)
        vuln_low = vulnerabilities.get("low", 0)
        
        # 취약점 요약
        if vuln_total == 0:
            vuln_summary = "발견된 취약점이 없습니다."
        else:
            parts = []
            if vuln_critical > 0:
                parts.append(f"🔴 Critical: {vuln_critical}")
            if vuln_high > 0:
                parts.append(f"🟠 High: {vuln_high}")
            if vuln_medium > 0:
                parts.append(f"🟡 Medium: {vuln_medium}")
            if vuln_low > 0:
                parts.append(f"🟢 Low: {vuln_low}")
            vuln_summary = " | ".join(parts) if parts else f"총 {vuln_total}개의 취약점"
        
        owner = state.get("owner", "")
        repo = state.get("repo", "")
        
        answer = f"""## {owner}/{repo} 보안 분석 결과

**보안 점수:** {security_score}/100 (등급: {security_grade})
**위험도:** {risk_level}

### 취약점 현황
{vuln_summary}

보안 분석이 완료되었습니다. 상세 정보는 우측 보고서의 "보안 분석" 섹션에서 확인하세요.
"""
        
        # 보안 분석 근거 링크 추가 (메타인지)
        vuln_details = results.get("vulnerability_details", agent_result.get("vulnerability_details", []))
        sources = []
        
        # 실제 분석된 의존성 파일만 링크 (진단 결과에서 가져옴)
        analyzed_files = results.get("analyzed_files", agent_result.get("analyzed_files", []))
        
        # analyzed_files가 없으면 vulnerabilities에서 추론
        if not analyzed_files and vuln_details:
            # 취약점에서 언급된 패키지 매니저 추론
            for vuln in vuln_details:
                pkg = vuln.get("package", "")
                if pkg and not analyzed_files:
                    # 언어별 매니저 파일 추론 (취약점이 있으면 해당 파일이 존재)
                    if any(x in pkg.lower() for x in ["django", "flask", "requests", "numpy"]):
                        analyzed_files.append("requirements.txt")
                    elif any(x in pkg.lower() for x in ["express", "react", "lodash"]):
                        analyzed_files.append("package.json")
        
        # 분석된 파일만 참고자료에 추가
        for dep_file in analyzed_files[:3]:
            if isinstance(dep_file, str) and dep_file:
                sources.append(Source(
                    url=f"https://github.com/{owner}/{repo}/blob/main/{dep_file}",
                    title=dep_file,
                    type="file"
                ))
        
        # CVE 링크 추가
        for vuln in vuln_details[:3]:
            cve_id = vuln.get("cve_id", "")
            if cve_id:
                sources.append(Source(
                    url=f"https://nvd.nist.gov/vuln/detail/{cve_id}",
                    title=cve_id,
                    type="cve"
                ))
        
        if sources:
            answer = format_response_with_sources(answer, sources, max_sources=5)
        
        # security_result 포함하여 반환 (프론트엔드에서 사용)
        security_result_data = {
            "security_score": security_score,
            "security_grade": security_grade,
            "risk_level": risk_level,
            "vulnerabilities": vulnerabilities,
            "vulnerability_details": vuln_details,
        }
        
        return {
            "final_answer": answer,
            "security_result": security_result_data,
        }
    
    elif result_type == "structure":
        # 구조만 요청한 경우 (기여 가이드 없이)
        owner = state.get("owner", "")
        repo = state.get("repo", "")
        features = agent_result.get("features", {})
        structure_viz = features.get("structure_visualization", {})
        
        answer = f"## {owner}/{repo} 코드 구조\n\n"
        if structure_viz:
            answer += "코드 구조는 우측의 '구조' 탭에서 확인할 수 있습니다.\n"
            answer += "다이어그램 또는 트리 구조로 전환하여 살펴보세요."
        else:
            answer += "구조 정보를 가져오지 못했습니다. 저장소를 확인해주세요."
        
        logger.info(f"Structure-only response for {owner}/{repo}")
        return {
            "final_answer": answer,
            "structure_visualization": structure_viz,
            "agent_result": agent_result
        }
    
    elif result_type == "recommend":
        # 프로젝트 추천 결과
        # 디버깅: agent_result 내용 확인
        logger.info(f"[DEBUG finalize] agent_result type: {type(agent_result)}")
        logger.info(f"[DEBUG finalize] agent_result keys: {list(agent_result.keys()) if isinstance(agent_result, dict) else 'N/A'}")
        if isinstance(agent_result, dict):
            logger.info(f"[DEBUG finalize] agent_result.recommendations count: {len(agent_result.get('recommendations', []))}")
        
        # 1. state.recommend_result 확인 (run_recommend_agent_node에서 직접 저장한 경우)
        recommend_result = state.get("recommend_result", {})
        logger.info(f"[DEBUG finalize] state.recommend_result: {bool(recommend_result)}, recommendations: {len(recommend_result.get('recommendations', []))}")
        
        # 2. 없으면 agent_result에서 가져오기 (multi_agent_results를 통해 온 경우)
        if not recommend_result or not recommend_result.get("recommendations"):
            recommend_result = agent_result if isinstance(agent_result, dict) else {}
            logger.info(f"[DEBUG finalize] Using agent_result as recommend_result")
        
        recommendations = recommend_result.get("recommendations", [])
        summary = recommend_result.get("summary", "")
        
        logger.info(f"Finalize recommend: {len(recommendations)} projects (from {'state' if state.get('recommend_result') else 'agent_result'})")
        
        if recommendations:
            answer = f"## 추천 프로젝트 목록\n\n"
            answer += f"{summary}\n\n" if summary else ""
            
            for i, proj in enumerate(recommendations[:5], 1):
                name = proj.get("name") or proj.get("full_name", "Unknown")
                desc = proj.get("description", "설명 없음")
                stars = proj.get("stars", 0)
                url = proj.get("html_url", "")
                language = proj.get("main_language", "")
                similarity = proj.get("similarity_score", 0)
                onboarding = proj.get("onboarding_score", 0)
                ai_reason = proj.get("ai_reason", "")
                
                # 점수 표시 형식
                similarity_pct = int(similarity * 100) if similarity else 0
                
                answer += f"### {i}. [{name}]({url})\n"
                answer += f"- **언어**: {language}\n" if language else ""
                answer += f"- **Stars**: {stars:,}\n"
                answer += f"- **온보딩 점수**: {onboarding}점\n" if onboarding else ""
                answer += f"- **유사도**: {similarity_pct}%\n" if similarity_pct else ""
                answer += f"- {desc}\n"
                answer += f"- **추천 이유**: {ai_reason}\n\n" if ai_reason else "\n"
            
            answer += "\n---\n더 자세한 정보는 우측의 '추천' 탭에서 확인하세요."
        else:
            answer = "죄송합니다. 조건에 맞는 프로젝트를 찾지 못했습니다. 다른 키워드로 다시 검색해 보세요."
        
        # agent_result에 recommendations 포함 (프론트엔드가 agent_result.recommendations를 사용)
        return {
            "final_answer": answer,
            "recommend_result": recommend_result,
            "agent_result": {
                "type": "recommend",
                "recommendations": recommendations,
                "summary": summary,
            },
        }
    
    elif result_type == "contributor":
        # 구조 요청인 경우 기여자 가이드 대신 구조만 표시
        if is_structure_request:
            owner = state.get("owner", "")
            repo = state.get("repo", "")
            features = agent_result.get("features", {})
            structure_viz = features.get("structure_visualization", {})
            
            if structure_viz:
                answer = f"## {owner}/{repo} 코드 구조\n\n코드 구조는 우측의 '구조' 탭에서 확인할 수 있습니다.\n클릭하여 트리 구조 또는 다이어그램으로 확인해보세요."
                logger.info("Structure request - returning structure_visualization only")
                return {
                    "final_answer": answer,
                    "structure_visualization": structure_viz,
                    "agent_result": {"type": "structure", "structure_visualization": structure_viz}
                }
        
        # 기여자 가이드 결과
        features = agent_result.get("features", {})
        owner = state.get("owner", "")
        repo = state.get("repo", "")
        
        guide = features.get("first_contribution_guide", {})
        checklist = features.get("contribution_checklist", {})
        
        # 첫 기여 가이드 요약
        guide_summary = ""
        steps = guide.get("steps", [])
        if steps:
            guide_summary = "\n".join([
                f"{i+1}. {step.get('title', '')}"
                for i, step in enumerate(steps[:5])
            ])
        
        # 체크리스트 요약
        checklist_items = checklist.get("items", [])
        checklist_summary = ""
        if checklist_items:
            high_priority = [item for item in checklist_items if item.get("priority") == "high"]
            checklist_summary = "\n".join([f"  - {item.get('title', '')}" for item in high_priority[:3]])
        
        answer = f"""## {owner}/{repo} 기여자 가이드

**첫 기여를 위한 단계별 가이드가 준비되었습니다!**

### 주요 단계
{guide_summary if guide_summary else "상세 가이드를 우측 리포트에서 확인하세요."}

### PR 제출 전 필수 체크
{checklist_summary if checklist_summary else "체크리스트를 우측 리포트에서 확인하세요."}

---
**팁:** 우측의 \"기여자 가이드\" 섹션에서 상세 정보와 체크리스트를 확인할 수 있습니다.
Good First Issue를 찾으시려면 `이슈 추천해줘`라고 말해보세요!
"""
        
        # 기여자 가이드 근거 링크 추가 (실제 존재 여부는 클라이언트에서 처리)
        sources = []
        
        # agent_result에서 실제 분석된 파일 확인
        first_contribution_guide = features.get("first_contribution_guide", {})
        contributing_url = first_contribution_guide.get("contributing_url")
        
        if contributing_url:
            sources.append(Source(
                url=contributing_url,
                title="CONTRIBUTING.md",
                type="file"
            ))
        
        # README.md는 기본으로 추가
        sources.append(Source(
            url=f"https://github.com/{owner}/{repo}/blob/main/README.md",
            title="README.md",
            type="file"
        ))
        
        # Issues 페이지 링크
        sources.append(Source(
            url=f"https://github.com/{owner}/{repo}/issues?q=label%3A%22good+first+issue%22",
            title="Good First Issues",
            type="issue"
        ))
        
        if sources:
            answer = format_response_with_sources(answer, sources, max_sources=5)
        
        return {
            "final_answer": answer,
            "agent_result": agent_result,
            "contributor_guide": agent_result
        }
    
    elif result_type == "comparison":
        # 비교 분석 결과 포맷팅
        summary = agent_result.get("comparison_summary", "")
        comparison_data = agent_result.get("compare_results", {})
        
        # 랭킹 점수 로직 (compare_nodes.py 참조)
        ranked_repos = []
        for r_str, data in comparison_data.items():
            health = data.get("health_score", 0)
            onboard = data.get("onboarding_score", 0)
            ranked_repos.append((r_str, health, onboard))
        
        # 건강도순 정렬
        ranked_repos.sort(key=lambda x: x[1], reverse=True)
        
        answer = f"## ⚖️ 저장소 비교 분석 결과\n\n"
        answer += f"{summary}\n\n" if summary else ""
        
        if ranked_repos:
            answer += "### 🏆 종합 순위\n\n"
            for i, (r_name, health, onboard) in enumerate(ranked_repos, 1):
                medal = ["🥇", "🥈", "🥉"][i-1] if i <= 3 else f"{i}."
                answer += f"{medal} **{r_name}**\n"
                answer += f"   - 🏥 건강도: {health}점\n"
                answer += f"   - 🔰 온보딩: {onboard}점\n\n"
        
        answer += "---\n📊 **상세 비교 데이터는 우측 리포트의 '비교' 탭에서 확인하세요.**"
        
        return {
            "final_answer": answer,
            "agent_result": agent_result
        }
    
    else:
        # 기타 - 대명사 참조 처리
        answer = str(agent_result.get("message", agent_result.get("response", str(agent_result))))
        
        # 대명사 참조가 있고 referenced_data가 있으면 컨텍스트 추가
        if referenced_data and pronoun_info.get("action") in ["refine", "summarize", "view"]:
            try:
                # LLM으로 컨텍스트를 포함한 응답 생성
                answer = await enhance_answer_with_context(
                    user_message=user_message,
                    base_answer=answer,
                    referenced_data=referenced_data,
                    action=pronoun_info.get("action"),
                    refers_to=pronoun_info.get("refers_to")
                )
            except Exception as e:
                logger.warning(f"Failed to enhance answer with context: {e}")
        
        return {"final_answer": answer}
