import streamlit as st
from pathlib import Path
from src.core.config import settings
from src.database.repository import CareerCompassRepository
from src.database.connection import db_manager

repository = CareerCompassRepository()


def init_page_config(page_title: str, page_icon: str) -> None:
    """Initializes Streamlit page configuration with default sidebar state."""
    st.set_page_config(
        page_title=page_title,
        page_icon=page_icon,
        layout="wide",
        initial_sidebar_state="expanded"
    )

def inject_custom_css() -> None:
    """Injects custom CSS overrides to apply a modern glassmorphic dark theme."""
    css_file = settings.BASE_DIR / "assets" / "css" / "custom.css"
    if css_file.exists():
        try:
            with open(css_file, "r", encoding="utf-8") as f:
                st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
        except Exception:
            pass

def check_login_status() -> None:
    """Verifies user session is logged in, otherwise redirects to home page."""
    if "logged_in" not in st.session_state or not st.session_state["logged_in"]:
        st.switch_page("app.py")

def render_sidebar_nav() -> None:
    """Renders a structured, premium sidebar with navigation groupings and profile card."""
    inject_custom_css()
    
    st.sidebar.markdown("""
    <div style='text-align: center; padding: 10px 0;'>
        <h2 style='margin: 0; font-family: "Outfit", sans-serif; font-weight: 700; color: #F8FAFC; letter-spacing: -0.03em;'>
            🧭 CareerCompass <span style='color: #6366f1;'>AI</span>
        </h2>
        <span style='font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.1em; color: #94A3B8;'>SaaS Talent Suite</span>
    </div>
    """, unsafe_allow_html=True)
    
    # Retrieve dynamic database metrics for the user
    user_id = st.session_state.get("user_id", 1)
    
    # Query database user by id
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT username, role FROM users WHERE id = ?;", (user_id,))
        user_row = cursor.fetchone()
    
    if user_row:
        username = user_row[0]
        role = user_row[1]
    else:
        username = "jane_smith"
        role = "student"
        
    student_name = username.replace("_", " ").title()
    
    # Retrieve latest resume
    resume = repository.get_latest_resume_for_user(user_id)
    ats_score = 0.0
    skills = []
    if resume:
        resume_id = resume["id"]
        ats_rep = repository.get_ats_report_by_resume(resume_id)
        if ats_rep:
            ats_score = ats_rep["ats_score"]
        db_skills = repository.get_resume_skills(resume_id)
        skills = [s["skill_name"] for s in db_skills]
    
    # Retrieve github profile
    github_score = 0.0
    github_profile = repository.get_github_profile(user_id)
    if github_profile:
        from pages.github_analyzer import calculate_extended_portfolio_score
        github_score, _ = calculate_extended_portfolio_score(
            repos=github_profile["public_repos_count"],
            stars=github_profile["total_stars_count"],
            contributions=github_profile["contributions_last_year"]
        )

    # Calculate placement readiness score
    from src.ml.placement_readiness import PlacementReadinessEvaluator
    readiness_evaluator = PlacementReadinessEvaluator()
    
    target_role = st.session_state.get("target_role", "")
    role_skills_map = {
        "Software Engineer": ["Python", "SQL", "Git", "Postgres", "Docker"],
        "Data Scientist": ["Python", "scikit-learn", "spaCy", "SQL"],
        "Frontend Developer": ["JavaScript", "React", "HTML", "CSS"]
    }
    target_skills = role_skills_map.get(target_role, ["Python"]) if target_role else ["Python"]
    
    readiness_results = readiness_evaluator.calculate_readiness_score(
        candidate_skills=skills,
        target_role_skills=target_skills,
        github_score=github_score,
        experience_years=2.0
    )
    readiness_score = readiness_results["placement_readiness_score"]
    
    # Set to session state
    st.session_state["ats_score"] = ats_score
    st.session_state["github_score"] = github_score
    st.session_state["readiness_score"] = readiness_score
    st.session_state["candidate_skills"] = skills
    st.session_state["username"] = username

    if resume:
        target_role_display = target_role if target_role else "General Audit"
        st.sidebar.markdown(f"""
        <div class='profile-card'>
            <div class='profile-title'>👤 {student_name}</div>
            <div style='font-size: 0.8rem; color: #3B82F6; font-weight: 600; margin-bottom: 12px;'>🎯 {target_role_display}</div>
            <div class='profile-detail'>
                <span>ATS Compatibility</span>
                <span style='color: #60A5FA; font-weight: 600;'>{ats_score}%</span>
            </div>
            <div class='profile-detail'>
                <span>Recruiter Readiness</span>
                <span style='color: #34D399; font-weight: 600;'>{readiness_score}%</span>
            </div>
            <div class='profile-detail'>
                <span>GitHub Portfolio</span>
                <span style='color: #7C3AED; font-weight: 600;'>{github_score}%</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.sidebar.markdown(f"""
        <div class='profile-card'>
            <div class='profile-title'>👤 {student_name}</div>
            <div style='font-size: 0.75rem; color: #94A3B8; margin-top: 8px; font-style: italic;'>Upload resume to activate insights</div>
        </div>
        """, unsafe_allow_html=True)
    
    # Navigation Groups
    st.sidebar.markdown("<p style='font-size:0.75rem; text-transform:uppercase; font-weight:bold; letter-spacing:0.05em; color:#475569; margin: 10px 0 5px 0;'>Core Platform</p>", unsafe_allow_html=True)
    st.sidebar.page_link("app.py", label="Home / Overview", icon="🏠")
    st.sidebar.page_link("pages/dashboard.py", label="Career Dashboard", icon="🧭")
    
    st.sidebar.markdown("<p style='font-size:0.75rem; text-transform:uppercase; font-weight:bold; letter-spacing:0.05em; color:#475569; margin: 15px 0 5px 0;'>Profile & Analysis</p>", unsafe_allow_html=True)
    st.sidebar.page_link("pages/resume_analyzer.py", label="ATS Resume Analyzer", icon="📄")
    st.sidebar.page_link("pages/github_analyzer.py", label="GitHub Portfolio Analyzer", icon="🐙")
    
    st.sidebar.markdown("<p style='font-size:0.75rem; text-transform:uppercase; font-weight:bold; letter-spacing:0.05em; color:#475569; margin: 15px 0 5px 0;'>Career Planning</p>", unsafe_allow_html=True)
    st.sidebar.page_link("pages/recommendations.py", label="AI Role Recommendations", icon="💼")
    st.sidebar.page_link("pages/job_explorer.py", label="Job Market Explorer", icon="🔍")



