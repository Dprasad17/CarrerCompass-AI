import logging
from typing import List, Dict, Any, Optional
import streamlit as st
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
from src.services.adzuna_client import AdzunaClient
from src.services.fallback_service import FallbackService
from src.services.geocoder import geocode_location
from src.database.repository import CareerCompassRepository
from src.utils.navigation import render_sidebar_nav, inject_custom_css, check_login_status, init_page_config

logger = logging.getLogger("JobExplorerView")

from src.database.connection import db_manager

# Initialize modules
adzuna_client = AdzunaClient()
fallback_service = FallbackService()
repository = CareerCompassRepository()


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_adzuna_jobs_cached(keyword: str, location: str, country_code: str, app_id: str, app_key: str, page: int) -> Optional[Dict[str, Any]]:
    """Fetches job postings from Adzuna API and caches the result."""
    return adzuna_client.search_jobs(
        keyword=keyword,
        location=location,
        country_code=country_code,
        app_id=app_id,
        app_key=app_key,
        page=page
    )


def main() -> None:
    # Ensure user is logged in
    check_login_status()

    init_page_config(
        page_title="CareerCompass AI - Job Explorer",
        page_icon="🔍"
    )
    inject_custom_css()
    render_sidebar_nav()


    st.title("🗺️ Job Market Explorer & Interactive Map")
    st.markdown("---")

    # Search Filters inside Sidebar
    st.sidebar.header("🔍 Search Filters")
    
    # Retrieve user's target role dynamically to pre-fill search keyword
    user_id = st.session_state.get("user_id", 1)
    target_role = st.session_state.get("target_role", "Developer")
    
    keyword = st.sidebar.text_input("Job Title / Skill Keyword:", value=target_role)
    location_input = st.sidebar.text_input("City / Region / Country:", value="Bangalore")
    
    # Optional API key fields in the sidebar so the user doesn't need to touch .env files
    st.sidebar.markdown("---")
    st.sidebar.header("🔑 Adzuna Credentials (Optional)")
    
    saved_app_id = st.session_state.get("adzuna_app_id", "")
    saved_app_key = st.session_state.get("adzuna_app_key", "")
    
    app_id_input = st.sidebar.text_input("Adzuna App ID:", value=saved_app_id, type="password")
    app_key_input = st.sidebar.text_input("Adzuna App Key:", value=saved_app_key, type="password")
    
    with st.sidebar.expander("ℹ️ Know More: Adzuna Keys"):
        st.markdown("""
        **What is Adzuna?**
        Adzuna is a job search engine aggregating millions of job listings. This app uses Adzuna's live API to fetch real-time jobs.
        
        **How to get credentials:**
        1. **Register**: Visit the official [Adzuna Developer Portal](https://developer.adzuna.com/).
        2. **Create Account**: Click **"Get API Key"** / **"Sign Up"** and complete your registration.
        3. **Register App**: In your developer dashboard, click **"Register new application"**.
        4. **Copy App ID & Key**: Your unique **App ID** and **App Key** will be listed on your developer dashboard page immediately.
        5. **Paste**: Copy and paste them into the input fields above!
        
        *Note: The app will continue using a high-fidelity local mockup if keys are empty.*
        """)
        
    if app_id_input != saved_app_id or app_key_input != saved_app_key:
        st.session_state["adzuna_app_id"] = app_id_input
        st.session_state["adzuna_app_key"] = app_key_input
        st.rerun()

    # Pagination state management
    if "job_page" not in st.session_state:
        st.session_state["job_page"] = 1

    if "prev_keyword" not in st.session_state:
        st.session_state["prev_keyword"] = keyword
    if "prev_location" not in st.session_state:
        st.session_state["prev_location"] = location_input

    if keyword != st.session_state["prev_keyword"] or location_input != st.session_state["prev_location"]:
        st.session_state["job_page"] = 1
        st.session_state["prev_keyword"] = keyword
        st.session_state["prev_location"] = location_input

    page = st.session_state["job_page"]



    # Geocode query location dynamically
    geocoded = geocode_location(location_input)
    lat = geocoded["lat"]
    lon = geocoded["lon"]
    country_code = geocoded["country_code"]
    display_name = geocoded["display_name"]
    
    st.sidebar.info(f"📍 Mapped Location: **{display_name}** ({country_code.upper()})")

    # Query listings
    with st.spinner("Fetching job postings from Adzuna / Fallback datasets..."):
        try:
            app_id = st.session_state.get("adzuna_app_id", "").strip()
            app_key = st.session_state.get("adzuna_app_key", "").strip()
            
            data = None
            if app_id and app_key:
                data = fetch_adzuna_jobs_cached(
                    keyword=keyword,
                    location=location_input,
                    country_code=country_code,
                    app_id=app_id,
                    app_key=app_key,
                    page=page
                )
            
            # Fall back if API credentials fail or are absent
            if data is None:
                data = fallback_service.load_fallback_jobs(
                    keyword=keyword,
                    location=location_input,
                    lat=lat,
                    lon=lon,
                    country_code=country_code,
                    page=page
                )
                
            jobs_list = data.get("jobs", [])
            total_matches = data.get("total_matches", 0)
        except Exception as e:
            logger.error(f"Error loading job list in view: {e}")
            st.error("Could not fetch job postings.")
            data = fallback_service.load_fallback_jobs(keyword, location_input, lat, lon, country_code, page)
            jobs_list = data.get("jobs", [])
            total_matches = data.get("total_matches", 0)

    st.subheader(f"Found {total_matches} Matching Jobs in {location_input} (Page {page})")

    # 1. RENDER FOLIUM MAP WITH VALIDATIONS
    if jobs_list:
        # Filter and validate coordinates
        valid_coords = []
        for j in jobs_list:
            j_lat = j.get("latitude")
            j_lon = j.get("longitude")
            if j_lat is not None and j_lon is not None:
                try:
                    lat_f = float(j_lat)
                    lon_f = float(j_lon)
                    # Standard world boundary validation limits
                    if -90.0 <= lat_f <= 90.0 and -180.0 <= lon_f <= 180.0:
                        valid_coords.append((lat_f, lon_f, j))
                except (ValueError, TypeError):
                    continue

        # Auto-centering logic: Center directly on geocoded center of location
        center_lat = lat
        center_lon = lon

        # Create Map object
        m = folium.Map(location=[center_lat, center_lon], zoom_start=12, tiles="CartoDB dark_matter")
        
        # Instantiate Marker Cluster
        marker_cluster = MarkerCluster().add_to(m)
        
        # Populate validated markers to cluster
        for lat_f, lon_f, job in valid_coords:
            currency = job.get("currency", "£")
            max_val = job.get("salary_max")
            max_str = f"{float(max_val):,.0f}" if max_val is not None else "N/A"
            sal_display = f"{currency}{max_str}" if max_str != "N/A" else "Not Disclosed"
            
            popup_html = f"""
            <div style='font-family: "Inter", sans-serif; font-size: 0.85rem; width: 200px;'>
                <b>{job['company']}</b><br>
                <span style='color:#3B82F6;'>{job['title']}</span><br>
                Salary: {sal_display}<br>
                <a href='{job['job_url']}' target='_blank' style='color:#10B981; font-weight:600; text-decoration:none;'>View & Apply ➡️</a>
            </div>
            """
            folium.Marker(
                location=[lat_f, lon_f],
                popup=folium.Popup(popup_html, max_width=260),
                icon=folium.Icon(color="blue", icon="briefcase", prefix="fa")
            ).add_to(marker_cluster)

        st_folium(m, width=1100, height=400)
    else:
        st.warning("No job locations found to display on map.")

    st.markdown("---")

    # 2. RENDER JOB DETAILS & BOOKMARKS
    if jobs_list:
        for index, job in enumerate(jobs_list):
            currency = job.get("currency", "£")
            sal_min_val = job.get("salary_min")
            sal_max_val = job.get("salary_max")
            
            sal_min = f"{float(sal_min_val):,.0f}" if sal_min_val is not None else "N/A"
            sal_max = f"{float(sal_max_val):,.0f}" if sal_max_val is not None else "N/A"
            
            if sal_min == "N/A" and sal_max == "N/A":
                salary_text = "Not Disclosed"
            else:
                salary_text = f"{currency}{sal_min} - {currency}{sal_max}"

            st.markdown(f"""
            <div class='saas-card' style='padding: 20px; margin-bottom: 15px;'>
                <h3 style='margin-top:0; color:#F8FAFC;'>{job['title']}</h3>
                <p style='color:#10B981;'>🏢 <b>{job['company']}</b> | 📍 {job['location']}</p>
                <p style='color:#94A3B8;'>💰 <b>Salary:</b> {salary_text}</p>
                <p style='color:#94A3B8;'>📄 {job['description'][:250]}...</p>
                <p style='color:#3B82F6;'><a href='{job['job_url']}' target='_blank' style='color:#3B82F6; text-decoration:none; font-weight:600;'>Apply on official portal ➡️</a></p>
            </div>
            """, unsafe_allow_html=True)

            # Bookmarking logic
            if st.button(f"📥 Bookmark: {job['title']} ({job['company']})", key=f"bookmark_{index}"):
                try:
                    # Save bookmark transaction
                    with db_manager.get_connection() as conn:
                        cursor = conn.cursor()
                        # Ensure job listing is saved in job_listings first
                        cursor.execute("""
                            INSERT OR IGNORE INTO job_listings 
                            (external_job_id, title, company, location, latitude, longitude, description, salary_min, salary_max, job_url, source)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                        """, (
                            job.get("external_job_id", f"ext-{index}"),
                            job["title"],
                            job["company"],
                            job["location"],
                            job.get("latitude"),
                            job.get("longitude"),
                            job["description"],
                            job.get("salary_min"),
                            job.get("salary_max"),
                            job["job_url"],
                            job.get("source", "Adzuna")
                        ))
                        
                        # Get database ID of the job listing
                        cursor.execute("SELECT id FROM job_listings WHERE external_job_id = ?;", (job.get("external_job_id", f"ext-{index}"),))
                        job_row = cursor.fetchone()
                        if job_row:
                            job_listing_id = job_row[0]
                            # Insert saved_jobs link
                            cursor.execute("""
                                INSERT OR IGNORE INTO saved_jobs (user_id, job_listing_id, status)
                                VALUES (?, ?, 'saved');
                            """, (user_id, job_listing_id))
                            conn.commit()
                            st.success("Job bookmarked successfully!")
                except Exception as e:
                    logger.error(f"Failed to bookmark job: {e}")
                    st.error("Error bookmarking job details.")

        # Main content pagination block matching reference layout
        st.markdown("<br>", unsafe_allow_html=True)
        col_page_info, col_page_btns = st.columns([2, 1])
        with col_page_info:
            st.markdown(f"<p style='margin: 0; padding-top: 8px; font-weight: 500;'>Showing results page <b>{page}</b> of matching jobs</p>", unsafe_allow_html=True)
        with col_page_btns:
            col_btn_prev, col_btn_next = st.columns(2)
            with col_btn_prev:
                if st.button("⬅️ Prev", key="main_prev_page", disabled=(page == 1)):
                    st.session_state["job_page"] -= 1
                    st.rerun()
            with col_btn_next:
                if st.button("Next ➡️", key="main_next_page"):
                    st.session_state["job_page"] += 1
                    st.rerun()
    else:
        st.info("No job postings matched the filter criteria.")


if __name__ == "__main__":
    main()
