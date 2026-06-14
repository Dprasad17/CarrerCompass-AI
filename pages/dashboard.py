import json
import logging
from typing import List, Dict, Any, Optional
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from src.core.config import settings
from src.database.repository import CareerCompassRepository
from src.database.connection import db_manager
from src.utils.navigation import render_sidebar_nav, inject_custom_css, check_login_status, init_page_config

logger = logging.getLogger("DashboardView")

@st.cache_resource(show_spinner=False)
def get_repository():
    return CareerCompassRepository()


repository = get_repository()

def render_html(html_str: str) -> None:
    """Cleans leading indentation from HTML lines and renders to Streamlit safely."""
    cleaned = "\n".join([line.strip() for line in html_str.split("\n") if line.strip()])
    st.markdown(cleaned, unsafe_allow_html=True)

def render_match_radar_chart(matched_count: int, total_count: int) -> go.Figure:
    """Renders a simple Gauge/Radar indicator for keyword match coverage."""
    coverage = (matched_count / max(total_count, 1)) * 100.0
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=coverage,
        title={'text': "Skill Coverage %", 'font': {'color': '#94A3B8', 'size': 14}},
        gauge={
            'axis': {'range': [0, 100], 'tickcolor': "#475569"},
            'bar': {'color': "#3B82F6"},
            'bgcolor': "#0F172A",
            'steps': [
                {'range': [0, 50], 'color': 'rgba(239, 68, 68, 0.1)'},
                {'range': [50, 75], 'color': 'rgba(245, 158, 11, 0.1)'},
                {'range': [75, 100], 'color': 'rgba(16, 185, 129, 0.1)'}
            ]
        }
    ))
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font={'color': "#F8FAFC", 'family': "Inter"},
        height=180,
        margin=dict(l=20, r=20, t=30, b=20)
    )
    return fig

def main() -> None:
    # Ensure user is logged in
    check_login_status()

    init_page_config(
        page_title="CareerCompass AI - Career Intelligence Hub",
        page_icon="🧭"
    )
    inject_custom_css()
    render_sidebar_nav()


    user_id = st.session_state.get("user_id", 1)

    # =========================================================================
    # 1. READ PERSISTED RECORDS ONLY (NO REAL-TIME ML CALCULATIONS IN VIEW)
    # =========================================================================
    
    # User profile name
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT username FROM users WHERE id = ?;", (user_id,))
        user_row = cursor.fetchone()
    username = user_row[0].replace("_", " ").title() if user_row else "Durga Prasad A"

    # A. Fetch latest resume
    use_prev = st.session_state.get("use_previous_insights", True)
    resume = repository.get_latest_resume_for_user(user_id) if use_prev else None
    
    # Fetch github profile
    github_profile = repository.get_github_profile(user_id)

    if not resume or not github_profile:
        st.title("🧭 Career Intelligence Command Center")
        st.markdown("---")
        st.info("ℹ️ Your personalized career dashboard is currently empty.")
        st.markdown("""
        ### 🚀 Setup Your Profile
        Please navigate to the **ATS Resume Analyzer** section to upload your resume and the **GitHub Portfolio Analyzer** to sync your GitHub profile.
        
        The dashboard will be available once the user uploads the resume and the GitHub username.
        """)
        return

    ats_score = 0.0
    structure_score = 0.0
    grammar_score = 0.0
    keyword_score = 0.0
    formatting_issues = []
    improvement_suggestions = []


    if resume:
        ats_rep = repository.get_ats_report_by_resume(resume["id"])
        if ats_rep:
            ats_score = ats_rep.get("ats_score", 0.0)
            structure_score = ats_rep.get("structure_score", 0.0)
            grammar_score = ats_rep.get("grammar_score", 0.0)
            keyword_score = ats_rep.get("keyword_score", 0.0)
            
            # Extract lists from stored json
            raw_issues = ats_rep.get("formatting_issues", {})
            formatting_issues = raw_issues.get("issues", []) if isinstance(raw_issues, dict) else []
            
            raw_suggs = ats_rep.get("improvement_suggestions", {})
            improvement_suggestions = raw_suggs.get("suggestions", []) if isinstance(raw_suggs, dict) else []

    # B. Fetch candidate skills from database instead of skill_gap_reports
    candidate_skills = []
    if resume:
        db_skills = repository.get_resume_skills(resume["id"])
        candidate_skills = [s["skill_name"] for s in db_skills]

    # Calculate matching and missing skills for target roles dynamically using normalized comparison
    readiness_score = st.session_state.get("readiness_score", 0.0)
    
    # Determine default skills comparison targets
    target_role = st.session_state.get("target_role", "Software Engineer")
    role_skills_map = {
        "Software Engineer": ["Python", "SQL", "Git", "Postgres", "Docker"],
        "Data Scientist": ["Python", "scikit-learn", "spaCy", "SQL"],
        "Frontend Developer": ["JavaScript", "React", "HTML", "CSS"]
    }
    target_role_skills = role_skills_map.get(target_role, ["Python", "SQL", "Git"])
    
    cand_skills_set = {s.lower().strip() for s in candidate_skills}
    matching_skills = [s for s in target_role_skills if s.lower().strip() in cand_skills_set]
    missing_skills = [s for s in target_role_skills if s.lower().strip() not in cand_skills_set]

    # C. Fetch latest GitHub profile and portfolio scores
    github_username = ""
    public_repos = 0
    total_stars = 0
    contributions = 0
    languages = {}
    portfolio_score = 0.0
    code_quality_index = 0.0
    activity_index = 0.0
    diversity_index = 0.0

    gp = repository.get_github_profile(user_id) if use_prev else None
    if gp:
        github_username = gp.get("github_username", "")
        public_repos = gp.get("public_repos_count", 0)
        total_stars = gp.get("total_stars_count", 0)
        contributions = gp.get("contributions_last_year", 0)
        languages = gp.get("languages_json", {})
        
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT portfolio_score, code_quality_index, activity_index, diversity_index 
                FROM portfolio_scores 
                WHERE github_profile_id = ? LIMIT 1;
            """, (gp["id"],))
            ps_row = cursor.fetchone()
            if ps_row:
                portfolio_score = ps_row[0]
                code_quality_index = ps_row[1]
                activity_index = ps_row[2]
                diversity_index = ps_row[3]

    # D. Fetch latest career recommendations
    recs = repository.get_latest_recommendations(user_id)
    top_matches = []
    target_role = st.session_state.get("target_role", "Software Engineer")
    
    if recs:
        recs.sort(key=lambda x: x["similarity_score"], reverse=True)
        target_role = recs[0]["target_title"]
        st.session_state["target_role"] = target_role
        
        for r in recs[:3]:
            # Derive matching vs missing skills dynamically from recommendations matching user skills
            req_skills = r["recommended_skills"]
            cand_skills_set = {s.lower().strip() for s in matching_skills}
            
            r_matched = [s for s in req_skills if s.lower().strip() in cand_skills_set]
            r_missing = [s for s in req_skills if s.lower().strip() not in cand_skills_set]
            
            top_matches.append({
                "title": r["target_title"],
                "score": r["similarity_score"] * 100.0,
                "matched_skills": r_matched,
                "missing_skills": r_missing,
                "demand": r["demand_level"],
                "difficulty": "Advanced" if r["similarity_score"] < 0.5 else "Intermediate" if r["similarity_score"] < 0.75 else "Beginner"
            })
    else:
        # Static baseline recommendations fallback if database recommendations are unpopulated
        top_matches = [
            {
                "title": "Software Engineer",
                "score": 75.0 if matching_skills else 45.0,
                "matched_skills": [s for s in ["Python", "SQL", "Git"] if s in matching_skills],
                "missing_skills": [s for s in ["Postgres", "Docker"] if s not in matching_skills],
                "demand": "High",
                "difficulty": "Intermediate"
            }
        ]

    # E. Fetch Market Demand Statistics
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM job_listings;")
        market_jobs_count = cursor.fetchone()[0]

    # Compute overall Career Health Score (weighted average of components)
    career_health_score = round((0.40 * ats_score) + (0.40 * readiness_score) + (0.20 * portfolio_score), 1)

    # Define strengths and weaknesses based on rules
    strengths = []
    weaknesses = []

    if ats_score >= 75:
        strengths.append("Strong ATS optimization & keyword density")
    else:
        weaknesses.append("Low ATS score - missing critical resume formatting guidelines")

    if readiness_score >= 70:
        strengths.append("High skills coverage matching target market role requirements")
    else:
        weaknesses.append("Significant technical skills gap detected")

    if portfolio_score >= 50:
        strengths.append("Active open source activity & code profile diversity")
    else:
        weaknesses.append("Low open-source contributions & project repository activity")

    if not strengths:
        strengths.append("Basic candidate contact details provided")
    if not weaknesses:
        weaknesses.append("Fully aligned profile, no immediate critical weaknesses found")

    # =========================================================================
    # RENDER SECTION 1: CAREER HEALTH HERO COMMAND CENTER
    # =========================================================================
    render_html(f"""
    <div style='background: linear-gradient(135deg, rgba(13,20,38,0.95) 0%, rgba(37,99,235,0.2) 100%); border: 1px solid rgba(255,255,255,0.06); border-radius: 12px; padding: 24px; margin-bottom: 20px;'>
        <div style='display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; margin-bottom: 15px;'>
            <div>
                <h1 style='margin:0; font-family:"Outfit", sans-serif; color:#F8FAFC; font-weight:800; font-size:1.8rem; letter-spacing:-0.03em;'>🧭 AI Career Intelligence Command Center</h1>
                <p style='color:#94A3B8; margin-top:4px; margin-bottom:0; font-size:0.95rem;'>Where am I now? Real-time analysis of your persisted profile health, gaps, and roadmap milestones.</p>
            </div>
            <div style='background:rgba(16, 185, 129, 0.1); border:1px solid rgba(16, 185, 129, 0.3); padding:6px 14px; border-radius:20px;'>
                <span style='color:#34D399; font-weight:600; font-size:0.85rem;'>Ready Status: Recruiter Visualized</span>
            </div>
        </div>
        <div style='display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 14px; margin-bottom: 20px;'>
            <div style='background: rgba(255,255,255,0.02); padding: 16px; border-radius: 8px; text-align: center; border: 1px solid rgba(255,255,255,0.04);'>
                <div style='font-size: 0.75rem; text-transform: uppercase; color: #94A3B8;'>Health Score</div>
                <div style='font-size: 1.6rem; font-weight: 800; color: #3B82F6; margin-top: 4px;'>{career_health_score}%</div>
            </div>
            <div style='background: rgba(255,255,255,0.02); padding: 16px; border-radius: 8px; text-align: center; border: 1px solid rgba(255,255,255,0.04);'>
                <div style='font-size: 0.75rem; text-transform: uppercase; color: #94A3B8;'>ATS Score</div>
                <div style='font-size: 1.6rem; font-weight: 800; color: #60A5FA; margin-top: 4px;'>{ats_score}%</div>
            </div>
            <div style='background: rgba(255,255,255,0.02); padding: 16px; border-radius: 8px; text-align: center; border: 1px solid rgba(255,255,255,0.04);'>
                <div style='font-size: 0.75rem; text-transform: uppercase; color: #94A3B8;'>Readiness Index</div>
                <div style='font-size: 1.6rem; font-weight: 800; color: #34D399; margin-top: 4px;'>{readiness_score}%</div>
            </div>
            <div style='background: rgba(255,255,255,0.02); padding: 16px; border-radius: 8px; text-align: center; border: 1px solid rgba(255,255,255,0.04);'>
                <div style='font-size: 0.75rem; text-transform: uppercase; color: #94A3B8;'>GitHub Score</div>
                <div style='font-size: 1.6rem; font-weight: 800; color: #A78BFA; margin-top: 4px;'>{portfolio_score}%</div>
            </div>
            <div style='background: rgba(255,255,255,0.02); padding: 16px; border-radius: 8px; text-align: center; border: 1px solid rgba(255,255,255,0.04);'>
                <div style='font-size: 0.75rem; text-transform: uppercase; color: #94A3B8;'>Top Role Match</div>
                <div style='font-size: 1.1rem; font-weight: 700; color: #F8FAFC; margin-top: 8px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;'>{target_role}</div>
            </div>
        </div>
        
        <div style='display: grid; grid-template-columns: 1fr 1fr; gap: 20px; border-top: 1px solid rgba(255,255,255,0.06); padding-top: 15px;'>
            <div>
                <span style='font-size: 0.8rem; font-weight: 700; text-transform: uppercase; color: #34D399; letter-spacing: 0.05em;'>✓ Strengths</span>
                <ul style='margin: 8px 0 0 0; padding-left: 20px; color: #CBD5E1; font-size: 0.85rem; line-height: 1.6;'>
                    {"".join([f"<li>{s}</li>" for s in strengths])}
                </ul>
            </div>
            <div>
                <span style='font-size: 0.8rem; font-weight: 700; text-transform: uppercase; color: #F87171; letter-spacing: 0.05em;'>✗ Weaknesses</span>
                <ul style='margin: 8px 0 0 0; padding-left: 20px; color: #CBD5E1; font-size: 0.85rem; line-height: 1.6;'>
                    {"".join([f"<li>{w}</li>" for w in weaknesses])}
                </ul>
            </div>
        </div>
    </div>
    """)

    # Onboarding instructions if newly logged in with missing details
    if not resume and not github_username:
        st.warning("🚀 **Welcome to CareerCompass AI!** Please upload your resume and sync your GitHub profile link to display personalized career metrics, ATS reviews, and role matches.")
        col_res, col_git = st.columns(2)
        with col_res:
            st.page_link("pages/resume_analyzer.py", label="Upload Resume 📄", icon="📄")
        with col_git:
            st.page_link("pages/github_analyzer.py", label="Sync GitHub Profile 🐙", icon="🐙")
        st.info("💡 Once uploaded, the dashboard will dynamically calculate and display your scores.")
    elif not resume:
        st.warning("⚠️ **Resume missing**: Please upload your resume in the **ATS Resume Analyzer** to view compatibility scores and role fit recommendations.")
        st.page_link("pages/resume_analyzer.py", label="Go to ATS Resume Analyzer 📄", icon="📄")
    elif not github_username:
        st.warning("⚠️ **GitHub profile link missing**: Please sync your profile in the **GitHub Portfolio Analyzer** to view open-source portfolio metrics.")
        st.page_link("pages/github_analyzer.py", label="Go to GitHub Portfolio Analyzer 🐙", icon="🐙")

    # Main Grid Layout (2 columns: Left for Resume/Skills, Right for Career matches/GitHub)
    col_left, col_right = st.columns([1, 1])

    # =========================================================================
    # LEFT COLUMN: RESUME INTELLIGENCE & GITHUB DEVELOPER PORTFOLIO
    # =========================================================================
    with col_left:
        # A. SECTION 2: RESUME INTELLIGENCE
        st.markdown("""<h3 style='font-family:"Outfit", sans-serif; font-size:1.2rem; color:#F8FAFC; margin-bottom:12px;'>📄 Resume Intelligence Audit</h3>""", unsafe_allow_html=True)
        
        completeness = 100.0 if (structure_score > 0 and grammar_score > 0 and ats_score > 0) else 0.0
        if completeness > 0:
            completeness = structure_score
            
        keyword_coverage = keyword_score
        
        render_html(f"""<div class='saas-card' style='padding: 20px; margin-bottom: 20px;'>
            <div style='display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px;'>
                <div>
                    <div style='font-size:0.75rem; color:#94A3B8;'>ATS Score</div>
                    <div style='font-size:1.3rem; font-weight:700; color:#3B82F6;'>{ats_score}%</div>
                </div>
                <div>
                    <div style='font-size:0.75rem; color:#94A3B8;'>Resume Completeness</div>
                    <div style='font-size:1.3rem; font-weight:700; color:#10B981;'>{completeness}%</div>
                </div>
            </div>
            
            <div style='margin-bottom: 12px;'>
                <div style='display:flex; justify-content:space-between; font-size:0.8rem; color:#94A3B8; margin-bottom:4px;'>
                    <span>Keyword Match Depth</span>
                    <span>{keyword_coverage}%</span>
                </div>
                <div style='background:#1E293B; height:8px; border-radius:4px;'>
                    <div style='background:#3B82F6; width:{keyword_coverage}%; height:8px; border-radius:4px;'></div>
                </div>
            </div>
            
            <div style='margin-bottom: 12px;'>
                <div style='display:flex; justify-content:space-between; font-size:0.8rem; color:#94A3B8; margin-bottom:4px;'>
                    <span>Structure Quality Index</span>
                    <span>{structure_score}%</span>
                </div>
                <div style='background:#1E293B; height:8px; border-radius:4px;'>
                    <div style='background:#10B981; width:{structure_score}%; height:8px; border-radius:4px;'></div>
                </div>
            </div>
            
            <div style='margin-bottom: 4px;'>
                <div style='display:flex; justify-content:space-between; font-size:0.8rem; color:#94A3B8; margin-bottom:4px;'>
                    <span>Language & Grammar Correctness</span>
                    <span>{grammar_score}%</span>
                </div>
                <div style='background:#1E293B; height:8px; border-radius:4px;'>
                    <div style='background:#A78BFA; width:{grammar_score}%; height:8px; border-radius:4px;'></div>
                </div>
            </div>
        </div>""")

        # B. SECTION 5: GITHUB PORTFOLIO INSIGHTS (moved to left column)
        st.markdown("""<h3 style='font-family:"Outfit", sans-serif; font-size:1.2rem; color:#F8FAFC; margin-bottom:12px;'>🐙 GitHub Developer Analytics</h3>""", unsafe_allow_html=True)
        
        if github_username:
            lang_badges = " ".join([f"<span class='badge badge-neutral'>{lang} ({pct:.1f}%)</span>" for lang, pct in list(languages.items())[:4]])
            render_html(f"""<div class='saas-card' style='padding: 16px; margin-bottom: 15px;'>
                <div style='display:grid; grid-template-columns: 1fr 1fr; gap:12px; margin-bottom:12px; border-bottom:1px solid rgba(255,255,255,0.04); padding-bottom:10px;'>
                    <div>
                        <div style='font-size:0.75rem; color:#94A3B8;'>Developer Profile</div>
                        <div style='font-size:1.1rem; font-weight:700; color:#F8FAFC;'>@{github_username}</div>
                    </div>
                    <div>
                        <div style='font-size:0.75rem; color:#94A3B8;'>Portfolio Score</div>
                        <div style='font-size:1.3rem; font-weight:700; color:#A78BFA;'>{portfolio_score}%</div>
                    </div>
                </div>
                <div style='display:grid; grid-template-columns: repeat(3, 1fr); gap:10px; margin-bottom:12px; text-align:center;'>
                    <div style='background:rgba(255,255,255,0.01); border:1px solid rgba(255,255,255,0.03); padding:8px; border-radius:6px;'>
                        <div style='font-size:0.7rem; color:#94A3B8;'>Repositories</div>
                        <div style='font-size:1rem; font-weight:700; color:#F8FAFC;'>{public_repos}</div>
                    </div>
                    <div style='background:rgba(255,255,255,0.01); border:1px solid rgba(255,255,255,0.03); padding:8px; border-radius:6px;'>
                        <div style='font-size:0.7rem; color:#94A3B8;'>Stars</div>
                        <div style='font-size:1rem; font-weight:700; color:#F8FAFC;'>{total_stars}</div>
                    </div>
                    <div style='background:rgba(255,255,255,0.01); border:1px solid rgba(255,255,255,0.03); padding:8px; border-radius:6px;'>
                        <div style='font-size:0.7rem; color:#94A3B8;'>Contributions</div>
                        <div style='font-size:1rem; font-weight:700; color:#F8FAFC;'>{contributions}</div>
                    </div>
                </div>
                
                <div style='margin-bottom:8px;'>
                    <div style='font-size:0.75rem; color:#94A3B8; margin-bottom:4px;'>Primary Languages:</div>
                    <div>{lang_badges if languages else 'Not Indexed'}</div>
                </div>
            </div>""")
        else:
            render_html("""<div class='saas-card' style='padding:16px; margin-bottom:15px; text-align:center;'>
                <div style='color:#94A3B8; font-size:0.85rem; margin-bottom:10px;'>No GitHub profile synced yet. Navigate to <b>GitHub Portfolio Analyzer</b> to index your public repository activity.</div>
            </div>""")

    # =========================================================================
    # RIGHT COLUMN: CAREER MATCHES
    # =========================================================================
    with col_right:
        # A. SECTION 4: CAREER MATCH ENGINE
        st.markdown("""<h3 style='font-family:"Outfit", sans-serif; font-size:1.2rem; color:#F8FAFC; margin-bottom:12px;'>💼 Top Career Matches</h3>""", unsafe_allow_html=True)
        
        for idx, match in enumerate(top_matches):
            role_name = match["title"]
            pct = match["score"]
            m_skills = match["matched_skills"][:3]
            miss_skills = match["missing_skills"][:3]
            diff = match["difficulty"]
            
            m_html = " ".join([f"<span class='badge badge-recruiter' style='font-size:0.7rem; padding:2px 6px;'>{s}</span>" for s in m_skills]) if m_skills else "None"
            miss_html = " ".join([f"<span class='badge badge-missing' style='font-size:0.7rem; padding:2px 6px;'>{s}</span>" for s in miss_skills]) if miss_skills else "None"
            
            fit_badge = "badge-recruiter" if pct >= 70.0 else "badge-ats"
            
            render_html(f"""<div class='saas-card' style='padding: 16px; margin-bottom: 12px;'>
                <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;'>
                    <span style='font-weight:700; color:#F8FAFC; font-size:0.95rem;'>{idx+1}. {role_name}</span>
                    <span class='badge {fit_badge}'>{pct:.1f}% Match</span>
                </div>
                <div style='font-size:0.75rem; color:#94A3B8; margin-bottom: 10px;'>
                    Difficulty: <b>{diff}</b> | Global Openings Indexed: <b>{market_jobs_count}</b>
                </div>
                <div style='margin-bottom: 6px;'>
                    <span style='color:#10B981; font-size:0.75rem; font-weight:600;'>Matched:</span> {m_html}
                </div>
                <div>
                    <span style='color:#EF4444; font-size:0.75rem; font-weight:600;'>Missing Gaps:</span> {miss_html}
                </div>
            </div>""")

    # =========================================================================
    # RENDER SECTION 7: AI PRIORITIZED ACTIONS
    # =========================================================================
    st.markdown("---")
    st.markdown("""<h3 style='font-family:"Outfit", sans-serif; font-size:1.2rem; color:#F8FAFC; margin-bottom:12px;'>📋 AI Prioritized Next-Step Actions</h3>""", unsafe_allow_html=True)
    
    # Rule-based priorities generator (100% read-only, dynamic logic)
    plan_actions = []
    
    if not resume:
        plan_actions.append("📄 **Upload Candidate Resume**: Go to ATS Resume Analyzer to import your skills and contact details.")
    else:
        if ats_score < 75.0:
            plan_actions.append("🔍 **Refactor Resume ATS Format**: Adjust structural sections to meet the 75%+ recruiter compliance scale.")
        if len(formatting_issues) > 0:
            plan_actions.append(f"⚠️ **Resolve formatting checks**: Fix structural alerts (e.g., {formatting_issues[0]}) in your resume layout.")
        if len(missing_skills) > 0:
            plan_actions.append(f"🎓 **Mitigate Skills Gap**: Prioritize learning **{missing_skills[0]}**, which is required for your target matches.")
    
    if not github_username:
        plan_actions.append("🐙 **Sync Developer Profile**: Sync your GitHub handle in the portfolio tab to index open-source repositories.")
    else:
        if portfolio_score < 50.0:
            plan_actions.append("📈 **Enhance Repository Activity**: Boost commits and add README headers to increase your activity index.")
            
    if len(top_matches) > 0:
        plan_actions.append(f"🔍 **Search Live Job Openings**: Explore active vacancies in the Job Explorer tab for **{target_role}**.")

    # Pad actions to 5 items using general timeline steps
    baseline_actions = [
        "🧠 **Incorporate Keywords**: Embed matched skills naturally in resume project descriptions.",
        "📚 **Build Project Portfolio**: Complete a capstone project using your missing skill gaps.",
        "📥 **Review Saved Bookmarks**: Track active recruitment timelines on your saved jobs list."
    ]
    
    for ba in baseline_actions:
        if len(plan_actions) < 5:
            plan_actions.append(ba)

    plan_html = "".join([f"""<div style='background:rgba(255,255,255,0.01); border:1px solid rgba(255,255,255,0.03); padding:10px; border-radius:6px; margin-bottom:8px; font-size:0.8rem; color:#CBD5E1;'>
        {action}
    </div>""" for action in plan_actions[:5]])

    render_html(f"""<div class='saas-card' style='padding:16px;'>
        {plan_html}
    </div>""")

if __name__ == "__main__":
    main()
