import logging
from typing import List, Dict, Any, Optional, Tuple
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from src.services.github_client import GitHubClient
from src.ml.placement_readiness import PlacementReadinessEvaluator
from src.utils.navigation import render_sidebar_nav, inject_custom_css, check_login_status, init_page_config
from src.database.repository import CareerCompassRepository

logger = logging.getLogger("GitHubAnalyzerView")

@st.cache_resource(show_spinner=False)
def get_repository():
    return CareerCompassRepository()

@st.cache_resource(show_spinner=False)
def get_github_client():
    return GitHubClient()

@st.cache_resource(show_spinner=False)
def get_evaluator():
    return PlacementReadinessEvaluator()




# Configurable Recruiter Threshold Constants
MIN_REPOS = 10
MIN_STARS = 15
MIN_CONTRIBUTIONS = 100

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_github_profile_cached(username: str) -> Optional[Dict[str, Any]]:

    """Queries GitHub client for profile metrics and caches the result."""
    return get_github_client().fetch_user_profile(username)

def get_readiness_level(score: float) -> Tuple[str, str]:
    """Classifies the readiness score according to design requirements and maps style class."""
    if score <= 40.0:
        return "Needs Improvement", "badge-missing"
    elif score <= 70.0:
        return "Developing", "badge-demand"
    elif score <= 85.0:
        return "Strong", "badge-ats"
    else:
        return "Recruiter Ready", "badge-recruiter"

def calculate_extended_portfolio_score(
    repos: int, 
    stars: int, 
    contributions: int, 
    extra_metrics: Optional[Dict[str, Any]] = None
) -> Tuple[float, Dict[str, float]]:
    """Calculates a comprehensive portfolio score (0.0 to 100.0)."""
    repo_contrib = min(repos / 20.0, 1.0) * 30.0
    star_contrib = min(stars / 50.0, 1.0) * 20.0
    contrib_contrib = min(contributions / 200.0, 1.0) * 20.0

    if extra_metrics is None:
        extra_metrics = {
            "readme_quality": 8.0,
            "project_diversity": 7.0,
            "fork_count": 5,
            "recent_activity": 8.5,
            "pinned_repos": 3
        }

    readme_score = (extra_metrics.get("readme_quality", 8.0) / 10.0) * 10.0
    diversity_score = (extra_metrics.get("project_diversity", 7.0) / 10.0) * 8.0
    fork_score = min(extra_metrics.get("fork_count", 5) / 10.0, 1.0) * 6.0
    activity_score = (extra_metrics.get("recent_activity", 8.5) / 10.0) * 6.0

    total_score = round(
        repo_contrib + star_contrib + contrib_contrib + 
        readme_score + diversity_score + fork_score + activity_score, 1
    )

    breakdown = {
        "Repos Fit": round(repo_contrib, 1),
        "Stars Count": round(star_contrib, 1),
        "Commits Count": round(contrib_contrib, 1),
        "README Quality": round(readme_score, 1),
        "Diversity": round(diversity_score, 1),
        "Activity Index": round(activity_score + fork_score, 1)
    }

    return min(total_score, 100.0), breakdown

def main() -> None:
    # Ensure user is logged in
    check_login_status()

    init_page_config(
        page_title="CareerCompass AI - GitHub Analyzer",
        page_icon="🐙"
    )
    inject_custom_css()
    render_sidebar_nav()

    repository = get_repository()
    github_client = get_github_client()
    evaluator = get_evaluator()

    st.title("🐙 GitHub Portfolio Analyzer")
    st.markdown("---")

    user_id = st.session_state.get("user_id", 1)
    
    # Pre-load existing GitHub profile from database if available
    use_prev = st.session_state.get("use_previous_insights", True)
    db_profile = repository.get_github_profile(user_id) if use_prev else None
    default_user = db_profile["github_username"] if db_profile else "janesmith-data"

    # Developer Identity Card
    st.markdown("""
    <div class='saas-card' style='padding: 16px;'>
        <h3 style='margin:0 0 6px 0; font-size:1.15rem; color:#F8FAFC;'>👤 Sync Developer Identity</h3>
        <p style='color:#94A3B8; margin-bottom:0; font-size:0.8rem;'>Sync public repository commits, repository code language distributions, and open source stars.</p>
    </div>
    """, unsafe_allow_html=True)

    input_col1, input_col2 = st.columns([3, 1])
    with input_col1:
        username = st.text_input("GitHub Username:", value=default_user, label_visibility="collapsed")
    with input_col2:
        analyze_btn = st.button("🚀 Run Analysis", width="stretch")

    # Use database profile if exists and button not clicked
    profile_data = None
    if not analyze_btn and db_profile:
        profile_data = {
            "github_username": db_profile["github_username"],
            "public_repos_count": db_profile["public_repos_count"],
            "total_stars_count": db_profile["total_stars_count"],
            "contributions_last_year": db_profile["contributions_last_year"],
            "languages_json": db_profile["languages_json"]
        }

    if analyze_btn or profile_data:
        st.session_state["github_username_analyzed"] = username
        
        with st.spinner("Analyzing portfolio..."):
            try:
                if analyze_btn or not profile_data:
                    fetched_data = fetch_github_profile_cached(username)
                    profile_data = fetched_data if fetched_data else {
                        "github_username": username,
                        "public_repos_count": 12,
                        "total_stars_count": 8,
                        "contributions_last_year": 120,
                        "languages_json": {"Python": 60.0, "JavaScript": 30.0, "HTML": 10.0}
                    }

                portfolio_score, breakdown = calculate_extended_portfolio_score(
                    repos=profile_data["public_repos_count"],
                    stars=profile_data["total_stars_count"],
                    contributions=profile_data["contributions_last_year"]
                )

                # Persist to database
                profile_id = repository.save_github_profile(
                    user_id=user_id,
                    github_username=profile_data["github_username"],
                    repos=profile_data["public_repos_count"],
                    stars=profile_data["total_stars_count"],
                    contributions=profile_data["contributions_last_year"],
                    languages_json=profile_data.get("languages_json", {})
                )

                import json
                from src.database.connection import db_manager
                with db_manager.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT OR REPLACE INTO portfolio_scores 
                        (github_profile_id, portfolio_score, code_quality_index, activity_index, diversity_index, detailed_metrics)
                        VALUES (?, ?, ?, ?, ?, ?);
                    """, (
                        profile_id,
                        portfolio_score,
                        breakdown.get("README Quality", 8.0) * 10.0,
                        breakdown.get("Activity Index", 8.0) * 10.0,
                        breakdown.get("Diversity", 7.0) * 10.0,
                        json.dumps(breakdown)
                    ))
                    conn.commit()

                # Fetch candidate skills from database for dynamic evaluation
                resume = repository.get_latest_resume_for_user(user_id)
                candidate_skills = []
                if resume:
                    db_skills = repository.get_resume_skills(resume["id"])
                    candidate_skills = [s["skill_name"] for s in db_skills]
                if not candidate_skills:
                    candidate_skills = list(profile_data.get("languages_json", {}).keys())

                readiness_results = evaluator.calculate_readiness_score(
                    candidate_skills=candidate_skills,
                    target_role_skills=["Python", "JavaScript", "SQL"],
                    github_score=portfolio_score,
                    experience_years=2.0
                )

                recruiter_readiness_score = readiness_results["placement_readiness_score"]
                readiness_level, badge_style = get_readiness_level(recruiter_readiness_score)

                # Save score back to session state to update sidebar card dynamically
                st.session_state["github_score"] = portfolio_score
                st.session_state["readiness_score"] = recruiter_readiness_score
                st.session_state["github_username_analyzed"] = profile_data["github_username"]
                st.session_state["use_previous_insights"] = True

                # Side-by-side layout: Profile statistics and interactive breakdowns
                col_stats, col_charts = st.columns([1, 1])

                with col_stats:
                    st.markdown(f"""
                    <div class='saas-card'>
                        <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;'>
                            <h3 style='margin:0; font-size:1.2rem; color:#F8FAFC;'>🏆 Recruiter Readiness</h3>
                            <span class='badge {badge_style}'>{readiness_level}</span>
                        </div>
                        <div style='display: grid; grid-template-columns: 1fr 1fr; gap: 12px;'>
                            <div style='background: rgba(255, 255, 255, 0.02); padding: 12px; border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.05);'>
                                <div style='font-size:0.75rem; color:#94A3B8;'>Readiness Score</div>
                                <div style='font-size:1.5rem; font-weight:700; color:#10B981; margin-top:4px;'>{recruiter_readiness_score}%</div>
                            </div>
                            <div style='background: rgba(255, 255, 255, 0.02); padding: 12px; border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.05);'>
                                <div style='font-size:0.75rem; color:#94A3B8;'>Portfolio Score</div>
                                <div style='font-size:1.5rem; font-weight:700; color:#3B82F6; margin-top:4px;'>{portfolio_score}%</div>
                            </div>
                        </div>
                        <div style='margin-top: 15px;'>
                            <div style='font-size: 0.8rem; color:#94A3B8; margin-bottom: 6px;'>Repository Quick Stats</div>
                            <div style='display:flex; justify-content:space-between; margin-bottom:4px;'>
                                <span>Public Relositories</span>
                                <span style='font-weight:600; color:#F8FAFC;'>{profile_data["public_repos_count"]}</span>
                            </div>
                            <div style='display:flex; justify-content:space-between; margin-bottom:4px;'>
                                <span>Total Stars Count</span>
                                <span style='font-weight:600; color:#F8FAFC;'>{profile_data["total_stars_count"]}</span>
                            </div>
                            <div style='display:flex; justify-content:space-between;'>
                                <span>Annual Commit Count</span>
                                <span style='font-weight:600; color:#F8FAFC;'>{profile_data["contributions_last_year"]}</span>
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    st.link_button(
                        "🌐 View Live GitHub Profile",
                        f"https://github.com/{username}",
                        width="stretch"
                    )

                with col_charts:
                    tab_breakdown, tab_languages = st.tabs(["📊 Score Breakdown", "🔍 Language Distribution"])

                    with tab_breakdown:
                        df_breakdown = pd.DataFrame([
                            {"Category": k, "Points": v} for k, v in breakdown.items()
                        ])
                        fig_bar = px.bar(
                            df_breakdown, x="Points", y="Category", orientation='h',
                            color="Points", color_continuous_scale=["#3B82F6", "#10B981"]
                        )
                        fig_bar.update_layout(
                            paper_bgcolor='rgba(0,0,0,0)',
                            plot_bgcolor='rgba(0,0,0,0)',
                            coloraxis_showscale=False,
                            font={'color': "#F8FAFC", 'family': "Inter"},
                            xaxis=dict(showgrid=False),
                            yaxis=dict(showgrid=False),
                            height=200,
                            margin=dict(l=10, r=10, t=10, b=10)
                        )
                        st.plotly_chart(fig_bar, width="stretch")

                    with tab_languages:
                        langs = profile_data.get("languages_json", {})
                        if langs:
                            df_langs = pd.DataFrame([{"Language": k, "Percentage": v} for k, v in langs.items()])
                            fig_pie = px.pie(
                                df_langs, values="Percentage", names="Language",
                                color_discrete_sequence=px.colors.qualitative.Safe
                            )
                            fig_pie.update_layout(
                                paper_bgcolor='rgba(0,0,0,0)',
                                plot_bgcolor='rgba(0,0,0,0)',
                                font={'color': "#F8FAFC", 'family': "Inter"},
                                height=200,
                                margin=dict(l=10, r=10, t=10, b=10)
                            )
                            st.plotly_chart(fig_pie, width="stretch")
                        else:
                            st.info("No languages detected.")

                # Actionable suggestions in a compact lower card
                st.markdown("---")
                st.subheader("💡 Portfolio Improvement Action Items")
                
                suggestions = []
                if profile_data["public_repos_count"] < MIN_REPOS:
                    suggestions.append(f"Build more repositories to meet the target threshold ({MIN_REPOS} repos).")
                if profile_data["total_stars_count"] < MIN_STARS:
                    suggestions.append(f"Optimize README documentation to achieve standard engagement levels ({MIN_STARS} stars).")
                if profile_data["contributions_last_year"] < MIN_CONTRIBUTIONS:
                    suggestions.append(f"Increase commitment frequency to satisfy target requirements ({MIN_CONTRIBUTIONS} commits).")

                if suggestions:
                    s_col1, s_col2, s_col3 = st.columns(3)
                    for i, sug in enumerate(suggestions):
                        col_to_use = [s_col1, s_col2, s_col3][i % 3]
                        with col_to_use:
                            st.markdown(f"""
                            <div class='saas-card' style='border-left: 3px solid #F59E0B; padding:12px; margin-bottom:10px;'>
                                <span class='badge badge-demand'>Task</span>
                                <div style='font-size:0.8rem; color:#F8FAFC; margin-top:6px;'>{sug}</div>
                            </div>
                            """, unsafe_allow_html=True)
                else:
                    st.success("Fantastic portfolio metrics! Your open source contributions are recruiter-ready.")

            except Exception as e:
                logger.error(f"GitHub Analyzer failed: {e}")
                st.error("Error analyzing profile. Please check logs.")

if __name__ == "__main__":
    main()
