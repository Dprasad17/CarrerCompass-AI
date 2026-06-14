import streamlit as st
import logging
from pathlib import Path
from src.core.config import settings
from src.database.repository import CareerCompassRepository
from src.utils.navigation import render_sidebar_nav, inject_custom_css, init_page_config
from pages.resume_analyzer import get_resume_parser, get_skill_extractor, get_ats_analyzer

# Setup logging
logger = logging.getLogger("AppMain")
repository = CareerCompassRepository()

def main() -> None:
    init_page_config(
        page_title="CareerCompass AI - Career Navigator",
        page_icon="🧭"
    )
    inject_custom_css()
    
    import threading
    
    def pre_warm():
        try:
            get_resume_parser()
            get_skill_extractor()
            get_ats_analyzer()
        except Exception as e:
            logger.warning(f"Could not pre-warm startup cache: {e}")

    # Run pre-warming in a daemon thread to prevent blocking main UI thread
    threading.Thread(target=pre_warm, daemon=True).start()





    # Initialize default login state
    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False

    if not st.session_state["logged_in"]:
        # Premium Onboarding/Login View
        st.title("🧭 Welcome to CareerCompass AI")
        st.markdown("Please sign in or register with your name and email to initialize your dynamic talent dashboard.")

        st.markdown("""
        <div style='background: linear-gradient(135deg, rgba(13,20,38,0.85) 0%, rgba(37,99,235,0.15) 100%); border: 1px solid rgba(255,255,255,0.05); border-radius: 12px; padding: 24px; margin-bottom: 24px;'>
            <h3 style='margin-top:0; color:#F8FAFC; font-weight:700;'>🚀 Get Started</h3>
            <p style='color:#94A3B8; margin-bottom:0;'>Your profile, ATS matches, roadmap milestones, and salary insights will be calculated dynamically based on your uploaded resume.</p>
        </div>
        """, unsafe_allow_html=True)

        with st.form("onboarding_form"):
            col1, col2 = st.columns(2)
            with col1:
                name_input = st.text_input("Your Full Name:", placeholder="Jane Smith")
            with col2:
                email_input = st.text_input("Your Email Address:", placeholder="jane.smith@example.com")
            
            submit_btn = st.form_submit_button("Proceed to Platform ➡️")

            if submit_btn:
                if not name_input.strip() or not email_input.strip():
                    st.error("Please enter a valid name and email address.")
                    return

                username = name_input.strip().lower().replace(" ", "_")
                email = email_input.strip().lower()

                # Verify if user already exists
                user = repository.get_user_by_email(email)
                if user:
                    user_id = user["id"]
                    username = user["username"]
                    role = user["role"]
                    logger.info(f"User logged in: {username} (ID: {user_id})")
                else:
                    # Create new user profile in database
                    try:
                        user_id = repository.create_user(
                            username=username,
                            email=email,
                            password_hash="scrypt:32768:8:1$placeholder",
                            role="student"
                        )
                        role = "student"
                        logger.info(f"Created new user profile: {username} (ID: {user_id})")
                    except Exception as e:
                        st.error(f"Error creating user account: {e}")
                        return

                st.session_state["user_id"] = user_id
                st.session_state["username"] = username
                st.session_state["role"] = role
                st.session_state["logged_in"] = True
                st.rerun()
        return

    # Render custom navigation if logged in
    render_sidebar_nav()

    user_id = st.session_state.get("user_id")
    username_display = st.session_state.get("username").replace("_", " ").title()

    # Check if this user has uploaded a resume or synced github in the database
    resume = repository.get_latest_resume_for_user(user_id)
    github_profile = repository.get_github_profile(user_id)

    has_previous_data = (resume is not None) or (github_profile is not None)

    if has_previous_data:
        st.title(f"Welcome back, {username_display}! 🧭")
    else:
        st.title(f"Welcome to CareerCompass AI, {username_display}! 🚀")

    st.markdown("---")

    if has_previous_data and "use_previous_insights" not in st.session_state:
        st.subheader("💡 Previous Insights Detected")
        st.info("We found previous resume or GitHub insights for your profile. Would you like to load your previous data or start fresh?")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Display Previous Resume Insights ➡️", use_container_width=True):
                st.session_state["use_previous_insights"] = True
                st.rerun()
        with col2:
            if st.button("Upload New Resume & Start Fresh 🔄", use_container_width=True):
                st.session_state["use_previous_insights"] = False
                st.rerun()
        return

    # Filter based on the session state selection
    use_prev = st.session_state.get("use_previous_insights", True)
    active_resume = resume if use_prev else None
    active_github = github_profile if use_prev else None

    if active_resume and active_github:
        st.markdown(f"""
        <div class='saas-card'>
            <h3 style='margin-top:0; color:#F8FAFC;'>✅ All Profile Insights Loaded</h3>
            <p style='color:#94A3B8;'>Both your active resume (<b>{active_resume['file_name']}</b>) and GitHub profile (<b>@{active_github['github_username']}</b>) are synced. You can now access full analysis details on the dashboard.</p>
        </div>
        """, unsafe_allow_html=True)
        st.page_link("pages/dashboard.py", label="Go to Career Dashboard ➡️", icon="🧭")
        
        # Option to start fresh
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Start Fresh / Upload New Resume & GitHub", key="reset_insights"):
            st.session_state["use_previous_insights"] = False
            st.rerun()
    else:
        st.markdown("""
        <div class='saas-card' style='border-left: 4px solid #F59E0B;'>
            <h3 style='margin-top:0; color:#FBBF24;'>🚀 Setup Your Profile</h3>
            <p style='color:#94A3B8; margin-bottom: 15px;'>Please upload your resume and also enter your GitHub username to view insights. Once both are provided, your personalized career dashboard insights will be displayed.</p>
        </div>
        """, unsafe_allow_html=True)
        
        col_res, col_git = st.columns(2)
        with col_res:
            if active_resume:
                st.success(f"✅ Resume Loaded: {active_resume['file_name']}")
            else:
                st.page_link("pages/resume_analyzer.py", label="Step 1: Upload Your Resume 📄", icon="📄")
        with col_git:
            if active_github:
                st.success(f"✅ GitHub Synced: @{active_github['github_username']}")
            else:
                st.page_link("pages/github_analyzer.py", label="Step 2: Sync GitHub Username 🐙", icon="🐙")

if __name__ == "__main__":
    main()
