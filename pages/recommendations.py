import logging
from typing import List, Dict, Any
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from src.core.config import settings
from src.database.repository import CareerCompassRepository
from src.ml.recommender import Recommender
from src.utils.navigation import render_sidebar_nav, inject_custom_css, check_login_status, init_page_config
from src.database.connection import db_manager
from src.nlp.skill_extractor import SkillExtractor
from src.nlp.resume_parser import ResumeParser

logger = logging.getLogger("RecommendationsView")

# Initialize modules
@st.cache_resource(show_spinner=False)
def get_repository():
    return CareerCompassRepository()

@st.cache_resource(show_spinner=False)
def get_recommender():
    return Recommender()

@st.cache_resource(show_spinner=False)
def get_skill_extractor():
    return SkillExtractor()





def render_html(html_str: str) -> None:
    """Renders HTML after cleaning leading/trailing whitespace line by line to prevent Streamlit parsing errors."""
    cleaned = "\n".join(line.strip() for line in html_str.split("\n"))
    st.markdown(cleaned, unsafe_allow_html=True)

def get_dynamic_roles(candidate_skills: List[str]) -> List[Dict[str, Any]]:
    """
    Dynamically generates target roles based on candidate skills, 
    persisted job listings, and market demand opportunities.
    """
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT title, description, salary_max, salary_min FROM job_listings;")
        rows = cursor.fetchall()

    jobs = []
    for r in rows:
        jobs.append({
            "title": r[0],
            "description": r[1],
            "salary_max": r[2] or 75000.0,
            "salary_min": r[3] or 50000.0
        })

    # If database job listings are unpopulated, parse fallback CSV or default list
    if not jobs:
        csv_path = settings.BASE_DIR / "datasets" / "jobs_dataset.csv"
        if csv_path.exists():
            try:
                df = pd.read_csv(csv_path)
                for _, row in df.iterrows():
                    jobs.append({
                        "title": str(row.get("title", "Software Developer")),
                        "description": str(row.get("description", "")),
                        "salary_max": float(row.get("salary_max", 70000.0)),
                        "salary_min": float(row.get("salary_min", 45000.0))
                    })
            except Exception as e:
                logger.error(f"Failed to read jobs CSV: {e}")

    if not jobs:
        # Base fallback definitions matching taxonomy
        jobs = [
            {"title": "Backend Web Developer", "description": "Python, SQL, Postgres, Docker API development", "salary_max": 85000, "salary_min": 55000},
            {"title": "Data Systems Analyst", "description": "Python, SQL, scikit-learn, spaCy, machine learning data workflows", "salary_max": 95000, "salary_min": 60000},
            {"title": "Frontend UI Architect", "description": "JavaScript, HTML, CSS, React components development", "salary_max": 80000, "salary_min": 50000}
        ]

    # Perform semantic recommendations match for all listings
    recommender = get_recommender()
    recommendation_results = recommender.recommend_jobs(candidate_skills, jobs, top_n=len(jobs))

    candidate_skills_set = {s.lower().strip() for s in candidate_skills}
    extractor = get_skill_extractor()

    dynamic_roles = []
    for match in recommendation_results:
        job = match["job"]
        score = match["similarity_score"]
        
        # Dynamically extract target skills using the taxonomy extractor
        target_skills_tuples = extractor.extract_skills(f"{job['title']} {job['description']}")
        target_skills = list(set([s[0] for s in target_skills_tuples]))
        
        # Ensure at least some target skills
        if not target_skills:
            target_skills = ["Python", "SQL", "Git"]

        # Only recommend if at least one skill matches!
        matched_skills = [s for s in target_skills if s.lower().strip() in candidate_skills_set]
        if matched_skills:
            demand = "High" if (job["salary_max"] > 90000 or score > 0.70) else "Medium"
            dynamic_roles.append({
                "title": job["title"],
                "similarity_score": score,
                "target_skills": target_skills,
                "demand": demand,
                "salary_max": job["salary_max"],
                "salary_min": job["salary_min"],
                "description": job["description"]
            })

    return dynamic_roles


def render_match_chart(dynamic_roles: List[Dict[str, Any]]) -> go.Figure:
    """Renders a Plotly horizontal bar chart displaying match similarity scores."""
    # Show top 5 in the chart for clarity if there are many matches
    chart_roles = dynamic_roles[:5]
    titles = [r["title"] for r in chart_roles]
    scores = [r["similarity_score"] * 100.0 for r in chart_roles]

    fig = go.Figure(go.Bar(
        x=scores,
        y=titles,
        orientation='h',
        marker=dict(
            color='#3B82F6',
            line=dict(color='rgba(255,255,255,0.1)', width=1)
        ),
        text=[f"{s:.1f}%" for s in scores],
        textposition='auto'
    ))
    
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font={'color': "#F8FAFC", 'family': "Inter"},
        xaxis=dict(range=[0, 100], showgrid=False),
        yaxis=dict(showgrid=False),
        height=240,
        margin=dict(l=10, r=10, t=10, b=10)
    )
    return fig

def main() -> None:
    # Ensure user is logged in
    check_login_status()

    init_page_config(
        page_title="CareerCompass AI - Recommendations",
        page_icon="💼"
    )
    inject_custom_css()
    render_sidebar_nav()

    repository = get_repository()

    st.title("💼 AI Career Recommendations & Skill Match")
    st.markdown("---")

    user_id = st.session_state.get("user_id", 1)

    # 1. RETRIEVE CANDIDATE SKILLS FROM DATABASE
    use_prev = st.session_state.get("use_previous_insights", True)
    resume = repository.get_latest_resume_for_user(user_id) if use_prev else None
    
    if not resume:
        st.info("ℹ️ Please upload your resume inside the ATS Resume Analyzer to view career recommendations.")
        return

    db_skills = repository.get_resume_skills(resume["id"])
    candidate_skills = [s["skill_name"] for s in db_skills]

    if not candidate_skills:
        st.info("ℹ️ Please upload your resume inside the ATS Resume Analyzer to view career recommendations.")
        return

    # 2. RUN DYNAMIC RECOMMENDATIONS
    with st.spinner("Analyzing candidate profile against market options..."):
        dynamic_roles = get_dynamic_roles(candidate_skills)

    if not dynamic_roles:
        st.warning("No career pathways match your current skill set. Try expanding your resume profile.")
        return

    # Parse sections from resume raw text to show detailed analysis of skills and projects
    parser = ResumeParser()
    extractor = get_skill_extractor()
    parsed_sections = parser.parse_resume_text(resume.get("raw_text", ""))
    
    skills_section_text = parsed_sections.get("skills_section", "")
    projects_section_text = parsed_sections.get("projects", "")
    
    skills_section_tuples = extractor.extract_skills(skills_section_text)
    projects_section_tuples = extractor.extract_skills(projects_section_text)
    
    skills_section_skills = list(set([s[0] for s in skills_section_tuples]))
    projects_section_skills = list(set([s[0] for s in projects_section_tuples]))
    
    # Filter other extracted skills to avoid duplicate display
    other_skills = [
        s for s in candidate_skills 
        if s.lower().strip() not in {sk.lower().strip() for sk in skills_section_skills} 
        and s.lower().strip() not in {sk.lower().strip() for sk in projects_section_skills}
    ]

    # Persist recommendations to database
    for role in dynamic_roles:
        repository.save_career_recommendation(
            user_id=user_id,
            title=role["title"],
            score=role["similarity_score"],
            match_jobs=10,
            demand=role["demand"],
            skills=role["target_skills"]
        )

    # Render Match Index Layout
    col_profile, col_chart = st.columns([1, 2])
    
    with col_profile:
        skills_pills = " ".join([f"<span class='badge badge-recruiter'>{s}</span>" for s in skills_section_skills]) if skills_section_skills else "<span style='font-size:0.75rem; color:#94A3B8;'>None detected</span>"
        projects_pills = " ".join([f"<span class='badge badge-ats'>{s}</span>" for s in projects_section_skills]) if projects_section_skills else "<span style='font-size:0.75rem; color:#94A3B8;'>None detected</span>"
        other_pills = " ".join([f"<span class='badge badge-neutral'>{s}</span>" for s in other_skills]) if other_skills else "<span style='font-size:0.75rem; color:#94A3B8;'>None</span>"

        render_html(f"""
        <div class='saas-card' style='min-height: 240px; overflow-y: auto;'>
            <div style='font-size:0.85rem; text-transform:uppercase; color:#94A3B8; margin-bottom: 12px;'>Resume Analysis Breakdown</div>
            <div style='margin-bottom: 10px;'>
                <div style='font-size:0.75rem; color:#10B981; font-weight:600; margin-bottom:4px;'>🛡️ Parsed Skills Section:</div>
                <div>{skills_pills}</div>
            </div>
            <div style='margin-bottom: 10px;'>
                <div style='font-size:0.75rem; color:#3B82F6; font-weight:600; margin-bottom:4px;'>📁 Parsed Projects Section:</div>
                <div>{projects_pills}</div>
            </div>
            <div>
                <div style='font-size:0.75rem; color:#CBD5E1; font-weight:600; margin-bottom:4px;'>🔍 Other Extracted Skills:</div>
                <div>{other_pills}</div>
            </div>
        </div>
        """)

    with col_chart:
        st.markdown("""
        <div style='font-family: "Outfit", sans-serif; font-size: 0.95rem; font-weight: 600; color: #F8FAFC; margin-bottom: 4px;'>
            🎯 Dynamic Role Match Index (Top 5 matches)
        </div>
        """, unsafe_allow_html=True)
        st.plotly_chart(render_match_chart(dynamic_roles), width="stretch")

    st.markdown("---")

    # 3. DISPLAY CARDS IN ROWS OF 3
    st.subheader("🎯 Real-Time Recommended Pathways")
    
    candidate_skills_set = {s.lower().strip() for s in candidate_skills}
    
    for i in range(0, len(dynamic_roles), 3):
        cols_rec = st.columns(3)
        for j in range(3):
            if i + j < len(dynamic_roles):
                role = dynamic_roles[i + j]
                title = role["title"]
                score = role["similarity_score"] * 100.0
                target_skills = role["target_skills"]
                
                # Calculate matched and missing skills in real time
                matched_skills = [s for s in target_skills if s.lower().strip() in candidate_skills_set]
                missing_skills = [s for s in target_skills if s.lower().strip() not in candidate_skills_set]
                
                # Tag location of matched skills (Skills section, Projects section, or General)
                tagged_matched_pills = []
                for s in matched_skills:
                    locations = []
                    if s.lower().strip() in {sk.lower().strip() for sk in skills_section_skills}:
                        locations.append("Skills")
                    if s.lower().strip() in {sk.lower().strip() for sk in projects_section_skills}:
                        locations.append("Projects")
                        
                    loc_str = f" ({'+'.join(locations)})" if locations else ""
                    tagged_matched_pills.append(f"<span class='badge badge-recruiter'>{s}{loc_str}</span>")

                with cols_rec[j]:
                    fit_badge = "badge-recruiter" if score >= 70.0 else "badge-ats"

                    render_html(f"""
                    <div class='saas-card' style='min-height: 340px; display: flex; flex-direction: column; justify-content: space-between; margin-bottom: 16px;'>
                        <div>
                            <div style='display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px;'>
                                <h3 style='margin:0; font-size: 1.15rem; color:#F8FAFC;'>{title}</h3>
                                <span class='badge {fit_badge}'>{score:.1f}% Match</span>
                            </div>
                            <p style='font-size: 0.8rem; color:#94A3B8; margin-bottom: 16px;'>{role['description']}</p>
                            <div style='margin-bottom: 12px;'>
                                <div style='font-size: 0.75rem; text-transform: uppercase; color:#10B981; font-weight: 600; margin-bottom: 6px;'>✅ Matched Skills:</div>
                                {" ".join(tagged_matched_pills) if tagged_matched_pills else "<span class='badge badge-neutral' style='color:#94A3B8;'>None matched yet</span>"}
                            </div>
                            <div style='margin-bottom: 16px;'>
                                <div style='font-size: 0.75rem; text-transform: uppercase; color:#EF4444; font-weight: 600; margin-bottom: 6px;'>❌ Skills Gap (Need to Learn):</div>
                                {" ".join([f"<span class='badge badge-missing'>{s}</span>" for s in missing_skills]) if missing_skills else "<span class='badge badge-recruiter'>Fully Matched!</span>"}
                            </div>
                        </div>
                    </div>
                    """)


if __name__ == "__main__":
    main()
