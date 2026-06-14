import sqlite3
import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from src.database.connection import db_manager

logger = logging.getLogger("DatabaseRepository")

class CareerCompassRepository:
    """
    Data Access Object (DAO) implementing the Repository pattern.
    Provides parameterized interfaces to perform database CRUD operations.
    """

    # =========================================================================
    # USER OPERATIONS
    # =========================================================================

    def create_user(self, username: str, email: str, password_hash: str, role: str = "student") -> int:
        """Inserts a new user and returns the new user's ID."""
        query = """
            INSERT INTO users (username, email, password_hash, role)
            VALUES (?, ?, ?, ?);
        """
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(query, (username, email, password_hash, role))
                conn.commit()
                return cursor.lastrowid
            except sqlite3.IntegrityError as e:
                logger.error(f"Failed to create user (username={username}, email={email}): Integrity check failed - {e}")
                raise e

    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Retrieves a user profile by their username."""
        query = "SELECT id, username, email, password_hash, role, created_at FROM users WHERE username = ?;"
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (username,))
            row = cursor.fetchone()
            if row:
                return {
                    "id": row[0],
                    "username": row[1],
                    "email": row[2],
                    "password_hash": row[3],
                    "role": row[4],
                    "created_at": row[5]
                }
            return None

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Retrieves a user profile by their email address."""
        query = "SELECT id, username, email, password_hash, role, created_at FROM users WHERE email = ?;"
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (email,))
            row = cursor.fetchone()
            if row:
                return {
                    "id": row[0],
                    "username": row[1],
                    "email": row[2],
                    "password_hash": row[3],
                    "role": row[4],
                    "created_at": row[5]
                }
            return None

    # =========================================================================
    # RESUME & SKILLS OPERATIONS
    # =========================================================================

    def save_resume(self, user_id: int, file_name: str, file_path: str, file_size: int, mime_type: str, raw_text: Optional[str] = None) -> int:
        """Saves resume metadata and returns the generated resume ID."""
        query = """
            INSERT INTO uploaded_resumes (user_id, file_name, file_path, file_size, mime_type, raw_text)
            VALUES (?, ?, ?, ?, ?, ?);
        """
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (user_id, file_name, file_path, file_size, mime_type, raw_text))
            conn.commit()
            return cursor.lastrowid

    def save_extracted_skills(self, resume_id: int, skills: List[Tuple[str, str, float]]) -> None:
        """
        Saves parsed skills mapping to a specific resume.
        Accepts skills as a list of tuples: (skill_name, skill_type, confidence_score)
        """
        query = """
            INSERT OR IGNORE INTO extracted_skills (resume_id, skill_name, skill_type, confidence_score)
            VALUES (?, ?, ?, ?);
        """
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(query, [(resume_id, name, sk_type, conf) for name, sk_type, conf in skills])
            conn.commit()

    def get_resume_skills(self, resume_id: int) -> List[Dict[str, Any]]:
        """Retrieves all parsed skills associated with a resume ID."""
        query = "SELECT skill_name, skill_type, confidence_score FROM extracted_skills WHERE resume_id = ?;"
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (resume_id,))
            rows = cursor.fetchall()
            return [{"skill_name": r[0], "skill_type": r[1], "confidence_score": r[2]} for r in rows]

    # =========================================================================
    # ATS & RECOMMENDATION METRICS
    # =========================================================================

    def save_ats_report(self, resume_id: int, ats_score: float, structure: float, grammar: float, keyword: float, formatting_issues: Dict[str, Any], suggestions: Dict[str, Any]) -> int:
        """Saves calculated ATS metrics."""
        query = """
            INSERT INTO ats_reports (resume_id, ats_score, structure_score, grammar_score, keyword_score, formatting_issues, improvement_suggestions)
            VALUES (?, ?, ?, ?, ?, ?, ?);
        """
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (
                resume_id,
                ats_score,
                structure,
                grammar,
                keyword,
                json.dumps(formatting_issues),
                json.dumps(suggestions)
            ))
            conn.commit()
            return cursor.lastrowid

    def save_career_recommendation(self, user_id: int, title: str, score: float, match_jobs: int, demand: str, skills: List[str]) -> int:
        """Saves career recommendations metrics."""
        # Clamp score between 0.0 and 1.0 to satisfy the database check constraint
        clamped_score = max(0.0, min(1.0, float(score)))
        query = """
            INSERT INTO career_recommendations (user_id, target_title, similarity_score, matching_jobs_count, demand_level, recommended_skills)
            VALUES (?, ?, ?, ?, ?, ?);
        """
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (
                user_id,
                title,
                clamped_score,
                match_jobs,
                demand,
                json.dumps(skills)
            ))
            conn.commit()
            return cursor.lastrowid

    # =========================================================================
    # LOGGING OPERATIONS
    # =========================================================================

    def log_activity(self, user_id: Optional[int], action: str, details: Dict[str, Any], ip_hash: Optional[str] = None, user_agent: Optional[str] = None) -> None:
        """Appends a track log to the activity logs table for audibility."""
        query = """
            INSERT INTO user_activity_logs (user_id, action, details, ip_hash, user_agent)
            VALUES (?, ?, ?, ?, ?);
        """
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (
                user_id,
                action,
                json.dumps(details),
                ip_hash,
                user_agent
            ))
            conn.commit()

    def get_recent_activity_count(self, ip_hash: str, seconds_window: int) -> int:
        """Returns action counts within a specific window to manage rate limits."""
        query = """
            SELECT COUNT(*) FROM user_activity_logs
            WHERE ip_hash = ? AND created_at >= datetime('now', '-' || ? || ' seconds');
        """
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (ip_hash, seconds_window))
            row = cursor.fetchone()
            return row[0] if row else 0

    # =========================================================================
    # EXTRA DATA INTEGRITY HELPER OPERATIONS
    # =========================================================================

    def get_latest_resume_for_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Retrieves the latest uploaded resume metadata and raw text for a user."""
        query = """
            SELECT id, file_name, file_path, file_size, mime_type, raw_text, parsed_at 
            FROM uploaded_resumes 
            WHERE user_id = ? 
            ORDER BY parsed_at DESC LIMIT 1;
        """
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (user_id,))
            row = cursor.fetchone()
            if row:
                return {
                    "id": row[0],
                    "file_name": row[1],
                    "file_path": row[2],
                    "file_size": row[3],
                    "mime_type": row[4],
                    "raw_text": row[5],
                    "parsed_at": row[6]
                }
            return None

    def get_ats_report_by_resume(self, resume_id: int) -> Optional[Dict[str, Any]]:
        """Retrieves the ATS report for a specific resume ID."""
        query = """
            SELECT id, ats_score, structure_score, grammar_score, keyword_score, formatting_issues, improvement_suggestions, analyzed_at 
            FROM ats_reports 
            WHERE resume_id = ? LIMIT 1;
        """
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (resume_id,))
            row = cursor.fetchone()
            if row:
                return {
                    "id": row[0],
                    "ats_score": row[1],
                    "structure_score": row[2],
                    "grammar_score": row[3],
                    "keyword_score": row[4],
                    "formatting_issues": json.loads(row[5]) if row[5] else {},
                    "improvement_suggestions": json.loads(row[6]) if row[6] else {},
                    "analyzed_at": row[7]
                }
            return None

    def get_github_profile(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Retrieves the persisted GitHub profile for a user."""
        query = """
            SELECT id, github_username, public_repos_count, total_stars_count, contributions_last_year, languages_json, last_fetched_at 
            FROM github_profiles 
            WHERE user_id = ? LIMIT 1;
        """
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (user_id,))
            row = cursor.fetchone()
            if row:
                return {
                    "id": row[0],
                    "github_username": row[1],
                    "public_repos_count": row[2],
                    "total_stars_count": row[3],
                    "contributions_last_year": row[4],
                    "languages_json": json.loads(row[5]) if row[5] else {},
                    "last_fetched_at": row[6]
                }
            return None

    def save_github_profile(self, user_id: int, github_username: str, repos: int, stars: int, contributions: int, languages_json: Dict[str, float]) -> int:
        """Inserts or replaces a user's GitHub profile metrics."""
        query = """
            INSERT OR REPLACE INTO github_profiles 
            (user_id, github_username, public_repos_count, total_stars_count, contributions_last_year, languages_json, last_fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'));
        """
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (
                user_id,
                github_username,
                repos,
                stars,
                contributions,
                json.dumps(languages_json)
            ))
            conn.commit()
            return cursor.lastrowid

    def get_latest_salary_prediction(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Retrieves the latest salary prediction for a user."""
        query = """
            SELECT id, job_title, years_experience, location, skills_json, predicted_annual_salary, confidence_interval_min, confidence_interval_max, predicted_at 
            FROM salary_predictions 
            WHERE user_id = ? 
            ORDER BY predicted_at DESC LIMIT 1;
        """
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (user_id,))
            row = cursor.fetchone()
            if row:
                return {
                    "id": row[0],
                    "job_title": row[1],
                    "years_experience": row[2],
                    "location": row[3],
                    "skills_json": json.loads(row[4]) if row[4] else [],
                    "predicted_annual_salary": row[5],
                    "confidence_interval_min": row[6],
                    "confidence_interval_max": row[7],
                    "predicted_at": row[8]
                }
            return None

    def save_salary_prediction(self, user_id: int, job_title: str, years_experience: float, location: str, skills_json: List[str], salary: float, ci_min: float, ci_max: float) -> int:
        """Saves a salary prediction run to the database."""
        query = """
            INSERT INTO salary_predictions 
            (user_id, job_title, years_experience, location, skills_json, predicted_annual_salary, confidence_interval_min, confidence_interval_max)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (
                user_id,
                job_title,
                years_experience,
                location,
                json.dumps(skills_json),
                salary,
                ci_min,
                ci_max
            ))
            conn.commit()
            return cursor.lastrowid

    def get_latest_recommendations(self, user_id: int) -> List[Dict[str, Any]]:
        """Retrieves the user's latest career recommendations."""
        query = """
            SELECT id, target_title, similarity_score, matching_jobs_count, demand_level, recommended_skills, created_at 
            FROM career_recommendations 
            WHERE user_id = ? 
            ORDER BY created_at DESC LIMIT 5;
        """
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (user_id,))
            rows = cursor.fetchall()
            return [
                {
                    "id": r[0],
                    "target_title": r[1],
                    "similarity_score": r[2],
                    "matching_jobs_count": r[3],
                    "demand_level": r[4],
                    "recommended_skills": json.loads(r[5]) if r[5] else [],
                    "created_at": r[6]
                }
                for r in rows
            ]

