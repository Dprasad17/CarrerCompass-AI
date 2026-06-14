import tempfile
import os
import re
import logging
from typing import List, Dict, Any, Optional
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from src.nlp.resume_parser import ResumeParser
from src.nlp.skill_extractor import SkillExtractor
from src.nlp.ats_analyzer import ATSAnalyzer
from src.ml.placement_readiness import PlacementReadinessEvaluator
from src.core.security import validate_uploaded_file
from src.database.repository import CareerCompassRepository
from src.database.connection import db_manager
from src.utils.navigation import render_sidebar_nav, inject_custom_css, check_login_status, init_page_config


logger = logging.getLogger("ResumeAnalyzerView")

# Initialize modules
@st.cache_resource(show_spinner=False)
def get_resume_parser():
    return ResumeParser()

@st.cache_resource(show_spinner=False)
def get_skill_extractor():
    return SkillExtractor()

@st.cache_resource(show_spinner=False)
def get_ats_analyzer():
    return ATSAnalyzer()

@st.cache_resource(show_spinner=False)
def get_readiness_evaluator():
    return PlacementReadinessEvaluator()

@st.cache_resource(show_spinner=False)
def get_repository():
    return CareerCompassRepository()






def render_html(html_str: str) -> None:
    """Renders HTML after cleaning leading/trailing whitespace line by line to prevent Streamlit parsing errors."""
    cleaned = "\n".join(line.strip() for line in html_str.split("\n"))
    st.markdown(cleaned, unsafe_allow_html=True)

def render_ats_gauge(score: float) -> go.Figure:
    """Renders a Plotly gauge chart for the ATS Score."""
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        title={'text': "ATS Fit Score", 'font': {'color': '#F8FAFC'}},
        gauge={
            'axis': {'range': [0, 100], 'tickcolor': "#94A3B8"},
            'bar': {'color': "#2563EB"},
            'bgcolor': "#1E293B",
            'steps': [
                {'range': [0, 50], 'color': '#EF4444'},
                {'range': [50, 75], 'color': '#F59E0B'},
                {'range': [75, 100], 'color': '#10B981'}
            ]
        }
    ))
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font={'color': "#F8FAFC", 'family': "Inter"},
        height=200,
        margin=dict(l=20, r=20, t=30, b=20)
    )
    return fig

def render_comparison_bar(matched: int, missing: int) -> go.Figure:
    """Renders a Plotly horizontal stack chart showing matched vs missing keywords."""
    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=['Keywords'], x=[matched], name='Matched',
        orientation='h', marker=dict(color='#10B981')
    ))
    fig.add_trace(go.Bar(
        y=['Keywords'], x=[missing], name='Missing',
        orientation='h', marker=dict(color='#EF4444')
    ))
    fig.update_layout(
        barmode='stack',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font={'color': "#F8FAFC", 'family': "Inter"},
        height=100,
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(showgrid=False, visible=False),
        yaxis=dict(showgrid=False, visible=False),
        showlegend=True
    )
    return fig

def render_skills_roadmap(missing_keywords: List[str]) -> None:
    """Renders a beautiful learning roadmap and resources for missing skills."""
    if not missing_keywords:
        st.success("🎉 You have no skills gaps for this role! All skills matched.")
        return
        
    st.markdown("### 🗺️ Your Personalized Learning Roadmap")
    st.markdown("Follow this step-by-step path to master the missing skills:")
    
    # Render a timeline style roadmap
    timeline_html = "<div style='display: flex; flex-direction: column; gap: 16px; margin-bottom: 20px;'>"
    for idx, skill in enumerate(missing_keywords):
        phase_num = idx + 1
        timeline_html += f"""
        <div style='background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.04); border-radius: 8px; padding: 16px; border-left: 4px solid #3B82F6;'>
            <div style='color: #60A5FA; font-weight: bold; font-size: 0.85rem;'>PHASE {phase_num}: Master {skill}</div>
            <p style='font-size:0.8rem; margin:4px 0 0 0; color: #CBD5E1;'>Focus on acquiring hands-on expertise in <b>{skill}</b>. Build a mini-project to demonstrate implementation.</p>
        </div>
        """
    timeline_html += "</div>"
    render_html(timeline_html)
    
    st.markdown("### 📚 Curated Learning Resources")
    
    # Pre-defined resources or dynamic search fallback
    resources_data = {
        "python": {"title": "Python for Everybody Specialization", "type": "Course", "url": "https://www.coursera.org/specializations/python", "source": "Coursera"},
        "sql": {"title": "SQL for Data Science", "type": "Course", "url": "https://www.coursera.org/learn/sql-for-data-science", "source": "Coursera"},
        "git": {"title": "Git & GitHub Complete Guide", "type": "Course", "url": "https://www.udemy.com/course/git-and-github-complete-guide/", "source": "Udemy"},
        "docker": {"title": "Docker Getting Started Guide", "type": "Documentation", "url": "https://docs.docker.com/get-started/", "source": "Official Docs"},
        "postgres": {"title": "PostgreSQL Official Documentation", "type": "Documentation", "url": "https://www.postgresql.org/docs/", "source": "Official Docs"},
        "postgresql": {"title": "PostgreSQL Official Documentation", "type": "Documentation", "url": "https://www.postgresql.org/docs/", "source": "Official Docs"},
        "react": {"title": "React.js Official Tutorial", "type": "Documentation", "url": "https://react.dev/learn", "source": "Official Docs"},
        "javascript": {"title": "Modern JavaScript Tutorial", "type": "Course", "url": "https://javascript.info/", "source": "JavaScript.info"},
    }
    
    r_col1, r_col2 = st.columns(2)
    cols = [r_col1, r_col2]
    
    for idx, skill in enumerate(missing_keywords):
        skill_lower = skill.lower().strip()
        res = resources_data.get(skill_lower, {
            "title": f"Master {skill} on Coursera",
            "type": "Course",
            "url": f"https://www.coursera.org/search?query={skill}",
            "source": "Coursera"
        })
        
        col_to_use = cols[idx % 2]
        with col_to_use:
            render_html(f"""
            <div class='saas-card' style='padding: 16px; margin-bottom: 12px; border-left: 3px solid #10B981;'>
                <span class='badge badge-recruiter'>{res['type']}</span>
                <h4 style='margin: 8px 0 4px 0; color: #F8FAFC; font-size: 0.95rem;'>{res['title']}</h4>
                <div style='font-size: 0.75rem; color: #94A3B8; margin-bottom: 8px;'>Platform: <b>{res['source']}</b></div>
                <a href='{res['url']}' target='_blank' style='color: #10B981; font-weight: 600; text-decoration: none; font-size: 0.8rem;'>Start Learning ➡️</a>
            </div>
            """)

def render_analysis_results(
    ats_score: float,
    structure_score: float,
    grammar_score: float,
    keyword_score: float,
    formatting_issues: List[str],
    suggestions: List[str],
    matched_keywords: List[str],
    missing_keywords: List[str],
    target_role: str,
    email: str,
    phone: str,
    github: str,
    raw_text: str,
    has_jd: bool = True
) -> None:
    # RENDER RESULTS LAYOUT (Side-by-Side)
    col_score, col_meta = st.columns([1, 2])
    with col_score:
        st.plotly_chart(render_ats_gauge(ats_score), width="stretch")
        readiness_score = st.session_state.get("readiness_score", 0.0)
        st.metric(
            label="Placement Readiness Score",
            value=f"{readiness_score}%"
        )
    with col_meta:
        render_html(f"""
        <div class='saas-card'>
            <h3 style='margin-top:0; color:#F8FAFC;'>👤 Parsed Contact Header</h3>
            <div style='display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-top:10px;'>
                <div>📧 <b>Email:</b> {email or 'Not found'}</div>
                <div>📞 <b>Phone:</b> {phone or 'Not found'}</div>
                <div>🐙 <b>GitHub:</b> {github or 'Not found'}</div>
                <div>🎯 <b>Target Match:</b> {target_role if target_role else 'General Audit'}</div>
            </div>
        </div>
        """)
        
        if has_jd:
            matched_len = len(matched_keywords)
            missing_len = len(missing_keywords)
            st.plotly_chart(render_comparison_bar(matched_len, missing_len), width="stretch")
        else:
            render_html("""
            <div class='saas-card' style='margin-top:12px; text-align:center;'>
                <p style='color:#94A3B8; margin:0;'>💡 Provide a Target Job Title and Job Description to enable keyword matching, skill gaps, and learning roadmaps.</p>
            </div>
            """)

    st.markdown("---")

    # ADVANCED ANALYTICS SECTION
    st.subheader("📊 Advanced Resume Compliance Analytics")
    if has_jd:
        tab_skills, tab_structure, tab_formatting, tab_recs, tab_roadmap = st.tabs([
            "🧠 Semantic Keyword Match", "🏗️ Section Structural Audit", "📄 Formatting & Font Parser", "📋 Actionable Revision Plan", "🗺️ Skills Roadmap & Resources"
        ])
    else:
        tab_structure, tab_formatting, tab_recs = st.tabs([
            "🏗️ Section Structural Audit", "📄 Formatting & Font Parser", "📋 Actionable Revision Plan"
        ])

    education_found = "education" in raw_text.lower() or "degree" in raw_text.lower() or "university" in raw_text.lower()
    experience_found = "experience" in raw_text.lower() or "employment" in raw_text.lower() or "work history" in raw_text.lower()
    projects_found = "project" in raw_text.lower() or "portfolio" in raw_text.lower()
    achievements_found = "achieve" in raw_text.lower() or "award" in raw_text.lower() or "honor" in raw_text.lower()

    if has_jd:
        with tab_skills:
            col_sk1, col_sk2 = st.columns(2)
            with col_sk1:
                render_html("<p style='font-weight:600; color:#10B981;'>✅ Matched JD Keywords:</p>")
                if matched_keywords:
                    st.write(", ".join(matched_keywords))
                else:
                    st.info("No matching keywords found.")
            with col_sk2:
                render_html("<p style='font-weight:600; color:#EF4444;'>❌ Missing JD Keywords:</p>")
                if missing_keywords:
                    st.write(", ".join(missing_keywords))
                else:
                    st.success("Perfect skill matches found!")

    with tab_structure:
        st.markdown("##### Section Presence Verification")
        sections_status = {
            "Education Section": education_found,
            "Experience Section": experience_found,
            "Projects Section": projects_found,
            "Achievements Section": achievements_found,
        }
        
        sec_col1, sec_col2, sec_col3, sec_col4 = st.columns(4)
        cols = [sec_col1, sec_col2, sec_col3, sec_col4]
        for idx, (sec_name, sec_found) in enumerate(sections_status.items()):
            with cols[idx]:
                bg = "rgba(16, 185, 129, 0.1)" if sec_found else "rgba(239, 68, 68, 0.1)"
                border = "rgba(16, 185, 129, 0.3)" if sec_found else "rgba(239, 68, 68, 0.3)"
                text = "Detected" if sec_found else "Missing"
                color = "#34D399" if sec_found else "#F87171"
                render_html(f"""
                <div style='background:{bg}; border: 1px solid {border}; border-radius:8px; padding:12px; text-align:center;'>
                    <div style='font-size:0.75rem; color:#94A3B8;'>{sec_name}</div>
                    <div style='font-size:1.1rem; font-weight:700; color:{color}; margin-top:4px;'>{text}</div>
                </div>
                """)

    with tab_formatting:
        st.markdown("##### Parser Readability Check")
        if formatting_issues:
            for issue in formatting_issues:
                render_html(f"<span class='badge badge-missing'>Issue</span> {issue}")
        else:
            st.success("No parsing formatting anomalies detected. Your resume is completely clean.")

    with tab_recs:
        st.markdown("##### Step-by-Step Optimization Strategy")
        rec_index = 1
        if has_jd and missing_keywords:
            st.markdown(f"""
            **Revision {rec_index}: Integrate Missing Technical Competencies**
            - *Action*: Embed these missing skills naturally in your Experience and Projects description: `{', '.join(missing_keywords[:4])}`.
            """)
            rec_index += 1
            
        if not experience_found:
            st.markdown(f"""
            **Revision {rec_index}: Detail Professional Work History**
            - *Action*: Expand on project deliverables and outline clear business impacts for previous roles.
            """)
            rec_index += 1

        if formatting_issues:
            st.markdown(f"""
            **Revision {rec_index}: Refactor Complex Text Layouts**
            - *Action*: Simplify resume format to single-column layouts to ensure standard ATS readability.
            """)
            rec_index += 1
            
        if rec_index == 1:
            st.success("Excellent! Your resume matches all criteria without any further actions needed.")

    if has_jd:
        with tab_roadmap:
            render_skills_roadmap(missing_keywords)

    # Downloadable Markdown report button
    report_content = f"""# CareerCompass AI - Advanced Resume Match Report
Target Job Title: {target_role if target_role else 'General Audit'}
ATS Overall Fit Score: {ats_score}%
Placement Readiness Index: {readiness_score}%

"""
    if has_jd:
        report_content += f"""## Matched Keywords ({len(matched_keywords)}):
{', '.join(matched_keywords) if matched_keywords else 'None'}

## Missing Keywords ({len(missing_keywords)}):
{', '.join(missing_keywords) if missing_keywords else 'None'}
"""
    
    report_content += f"""## Structural Compliance Check:
- Education Section: {'Detected' if education_found else 'Missing'}
- Experience Section: {'Detected' if experience_found else 'Missing'}
- Projects Section: {'Detected' if projects_found else 'Missing'}
- Achievements Section: {'Detected' if achievements_found else 'Missing'}

## Strategic Suggestions:
""" + "\n".join([f"- {s}" for s in suggestions])

    st.download_button(
        label="📥 Download Detailed Match Report",
        data=report_content,
        file_name=f"CareerCompass_Match_Report_{target_role.replace(' ', '_') if target_role else 'General'}.txt",
        mime="text/plain"
    )

def main() -> None:
    # Ensure user is logged in
    check_login_status()

    init_page_config(
        page_title="CareerCompass AI - Resume Analyzer",
        page_icon="📄"
    )
    inject_custom_css()
    render_sidebar_nav()

    parser = get_resume_parser()
    extractor = get_skill_extractor()
    analyzer = get_ats_analyzer()
    readiness_evaluator = get_readiness_evaluator()
    repository = get_repository()

    st.title("📄 Advanced ATS Resume Analyzer & JD Match Engine")
    st.markdown("---")

    user_id = st.session_state.get("user_id", 1)

    # 1. Pasting Job Description Panel
    st.subheader("🎯 Target Job Specifications")
    
    target_role_val = st.session_state.get("target_role", "")
    target_role = st.text_input("Enter Target Job Title (Leave blank for basic resume audit):", value=target_role_val)
    st.session_state["target_role"] = target_role

    job_description = st.text_area("Paste the target Job Description (JD) here (Leave blank for basic resume audit):", value="", height=150)

    st.markdown("---")

    # 2. Upload Resume File
    st.markdown("### 📄 Upload Resume")
    st.markdown("<p style='color: var(--text-secondary); margin-bottom: 5px;'>Upload your resume to perform a comprehensive profile compatibility and skill gap audit.</p>", unsafe_allow_html=True)
    uploaded_file = st.file_uploader("Upload Resume", type=["pdf", "docx"], label_visibility="collapsed")

    st.markdown("<p style='font-size: 0.8rem; color: var(--text-secondary); margin-top: 5px; margin-bottom: 15px;'>Supported formats: <b>PDF, DOCX</b> | Max file size: <b>200MB</b></p>", unsafe_allow_html=True)


    # Load from database if exists
    use_prev = st.session_state.get("use_previous_insights", True)
    db_resume = repository.get_latest_resume_for_user(user_id) if use_prev else None

    # Check JD presence
    has_jd = (target_role.strip() != "") and (job_description.strip() != "")

    if uploaded_file is not None:
        file_bytes = uploaded_file.read()
        file_name = uploaded_file.name

        is_valid, err_msg = validate_uploaded_file(file_bytes, file_name)
        if not is_valid:
            st.error(err_msg)
            return

        with st.spinner("Executing advanced text parsing and semantic keyword analytics..."):
            try:
                # Write temporarily to disk for parsing
                with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file_name)[1]) as tmp_file:
                    tmp_file.write(file_bytes)
                    tmp_path = tmp_file.name

                try:
                    parsed_data = parser.parse_resume(tmp_path)
                finally:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)

                # Extract skills from Candidate Resume
                extracted_skills_tuples = extractor.extract_skills(parsed_data["raw_text"])
                extracted_skill_names = [s[0] for s in extracted_skills_tuples]

                # Extract skills dynamically from Pasted Job Description if provided
                target_skills = []
                if has_jd:
                    target_skills_tuples = extractor.extract_skills(job_description)
                    target_skills = list(set([s[0] for s in target_skills_tuples]))
                    if not target_skills:
                        target_skills = ["Python", "SQL", "Git"]

                # Run advanced ATS analysis
                ats_results = analyzer.analyze_resume(parsed_data, extracted_skill_names, target_skills)

                if not has_jd:
                    # Re-weight score to exclude keywords (50% structure, 50% formatting)
                    ats_score = (0.50 * ats_results["structure_score"]) + (0.50 * ats_results["formatting_score"])
                    ats_results["ats_score"] = round(ats_score, 1)

                # Save resume details to database
                simulated_path = f"data/resumes/{user_id}_{file_name}"
                resume_id = repository.save_resume(
                    user_id=user_id,
                    file_name=file_name,
                    file_path=simulated_path,
                    file_size=len(file_bytes),
                    mime_type=uploaded_file.type,
                    raw_text=parsed_data.get("raw_text", "")
                )
                
                # Save extracted skills
                repository.save_extracted_skills(resume_id, extracted_skills_tuples)
                
                # Save ATS report
                formatting_issues_dict = {"issues": ats_results.get("formatting_issues", [])}
                suggestions_dict = {"suggestions": ats_results.get("suggestions", [])}
                repository.save_ats_report(
                    resume_id=resume_id,
                    ats_score=ats_results["ats_score"],
                    structure=ats_results["structure_score"],
                    grammar=95.0,
                    keyword=ats_results["keyword_score"],
                    formatting_issues=formatting_issues_dict,
                    suggestions=suggestions_dict
                )

                if has_jd:
                    # Save dynamic recommendation for the target title
                    repository.save_career_recommendation(
                        user_id=user_id,
                        title=target_role,
                        score=ats_results["keyword_score"] / 100.0,
                        match_jobs=12,
                        demand="High",
                        skills=target_skills
                    )

                # Query GitHub profile for placement readiness score
                github_score = 0.0
                github_profile = repository.get_github_profile(user_id)
                if github_profile:
                    from pages.github_analyzer import calculate_extended_portfolio_score
                    github_score, _ = calculate_extended_portfolio_score(
                        repos=github_profile["public_repos_count"],
                        stars=github_profile["total_stars_count"],
                        contributions=github_profile["contributions_last_year"]
                    )

                readiness_results = readiness_evaluator.calculate_readiness_score(
                    candidate_skills=extracted_skill_names,
                    target_role_skills=target_skills if has_jd else ["Python", "SQL", "Git"],
                    github_score=github_score,
                    experience_years=2.0
                )
                
                # Set dynamic session state keys
                st.session_state["ats_score"] = ats_results["ats_score"]
                st.session_state["github_score"] = github_score
                st.session_state["readiness_score"] = readiness_results['placement_readiness_score']
                st.session_state["candidate_skills"] = extracted_skill_names
                st.session_state["use_previous_insights"] = True

                cand_email = parsed_data['contact_info'].get('email', '')
                cand_phone = parsed_data['contact_info'].get('phone', '')
                cand_github = parsed_data['contact_info'].get('github_profile', '')
                if not cand_github or cand_github.strip() == "":
                    github_profile = repository.get_github_profile(user_id)
                    if github_profile and github_profile.get("github_username"):
                        cand_github = f"github.com/{github_profile['github_username']}"

                st.success("Advanced Resume Parsing & Analytics Successful! Persisted to database.")

                render_analysis_results(
                    ats_score=ats_results["ats_score"],
                    structure_score=ats_results["structure_score"],
                    grammar_score=95.0,
                    keyword_score=ats_results["keyword_score"],
                    formatting_issues=ats_results.get("formatting_issues", []),
                    suggestions=ats_results.get("suggestions", []),
                    matched_keywords=ats_results.get("matched_keywords", []),
                    missing_keywords=ats_results.get("missing_keywords", []),
                    target_role=target_role,
                    email=cand_email,
                    phone=cand_phone,
                    github=cand_github,
                    raw_text=parsed_data.get("raw_text", ""),
                    has_jd=has_jd
                )

            except Exception as e:
                logger.error(f"Failed to analyze resume file: {e}")
                st.error("An error occurred during resume parsing. Please check the logs.")
    
    elif db_resume is not None:
        st.info(f"ℹ️ Loaded active resume: **{db_resume['file_name']}** from database.")
        
        # Pull matching details from DB
        ats_rep = repository.get_ats_report_by_resume(db_resume["id"])
        db_skills = repository.get_resume_skills(db_resume["id"])
        candidate_skills = [s["skill_name"] for s in db_skills]
        
        # Calculate keywords dynamically based on pasted Job Description if provided
        target_skills = []
        matched_keywords = []
        missing_keywords = []
        if has_jd:
            target_skills_tuples = extractor.extract_skills(job_description)
            target_skills = list(set([s[0] for s in target_skills_tuples]))
            if not target_skills:
                target_skills = ["Python", "SQL", "Git"]
                
            cand_skills_set = {s.lower().strip() for s in candidate_skills}
            matched_keywords = [s for s in target_skills if s.lower().strip() in cand_skills_set]
            missing_keywords = [s for s in target_skills if s.lower().strip() not in cand_skills_set]

        # Use saved parameters if available, else derive
        ats_score = ats_rep.get("ats_score", 70.0) if ats_rep else 70.0
        structure_score = ats_rep.get("structure_score", 80.0) if ats_rep else 80.0
        grammar_score = ats_rep.get("grammar_score", 95.0) if ats_rep else 95.0
        formatting_score = ats_rep.get("keyword_score", 75.0) if ats_rep else 75.0
        
        if not has_jd:
            ats_score = (0.50 * structure_score) + (0.50 * formatting_score)
            ats_score = round(ats_score, 1)
        
        raw_issues = ats_rep.get("formatting_issues", {}) if ats_rep else {}
        formatting_issues = raw_issues.get("issues", []) if isinstance(raw_issues, dict) else []
        
        raw_suggs = ats_rep.get("improvement_suggestions", {}) if ats_rep else {}
        suggestions = raw_suggs.get("suggestions", []) if isinstance(raw_suggs, dict) else []
        
        # Parse contact header details from DB resume raw text
        contact_info = parser._extract_contact_info(db_resume.get("raw_text", ""))
        db_email = contact_info.get("email", "")
        db_phone = contact_info.get("phone", "")
        db_github = contact_info.get("github_profile", "")
        if not db_github or db_github.strip() == "":
            github_profile = repository.get_github_profile(user_id)
            if github_profile and github_profile.get("github_username"):
                db_github = f"github.com/{github_profile['github_username']}"

        # Show analysis results
        render_analysis_results(
            ats_score=ats_score,
            structure_score=structure_score,
            grammar_score=grammar_score,
            keyword_score=formatting_score,
            formatting_issues=formatting_issues,
            suggestions=suggestions,
            matched_keywords=matched_keywords,
            missing_keywords=missing_keywords,
            target_role=target_role,
            email=db_email,
            phone=db_phone,
            github=db_github,
            raw_text=db_resume.get("raw_text", ""),
            has_jd=has_jd
        )

if __name__ == "__main__":
    main()
