-- CareerCompass AI - Production Schema (SQLite)
-- Database Architect: Senior DB Architect

PRAGMA foreign_keys = ON;

-- ============================================================================
-- 1. CORE TABLES
-- ============================================================================

-- Table 1: users
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT DEFAULT 'student' CHECK (role IN ('student', 'admin', 'recruiter')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table 2: uploaded_resumes
CREATE TABLE IF NOT EXISTS uploaded_resumes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_size INTEGER NOT NULL CHECK (file_size > 0),
    mime_type TEXT NOT NULL,
    raw_text TEXT,
    parsed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Table 3: extracted_skills
CREATE TABLE IF NOT EXISTS extracted_skills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    resume_id INTEGER NOT NULL,
    skill_name TEXT NOT NULL,
    skill_type TEXT NOT NULL CHECK (skill_type IN ('technical', 'soft', 'tool', 'domain')),
    confidence_score REAL DEFAULT 1.0 CHECK (confidence_score BETWEEN 0.0 AND 1.0),
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(resume_id) REFERENCES uploaded_resumes(id) ON DELETE CASCADE,
    UNIQUE(resume_id, skill_name)
);

-- Table 4: ats_reports
CREATE TABLE IF NOT EXISTS ats_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    resume_id INTEGER NOT NULL UNIQUE,
    ats_score REAL NOT NULL CHECK (ats_score BETWEEN 0.0 AND 100.0),
    structure_score REAL NOT NULL CHECK (structure_score BETWEEN 0.0 AND 100.0),
    grammar_score REAL NOT NULL CHECK (grammar_score BETWEEN 0.0 AND 100.0),
    keyword_score REAL NOT NULL CHECK (keyword_score BETWEEN 0.0 AND 100.0),
    formatting_issues TEXT, -- JSON string format
    improvement_suggestions TEXT, -- JSON string format
    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(resume_id) REFERENCES uploaded_resumes(id) ON DELETE CASCADE
);

-- Table 5: skill_gap_reports
CREATE TABLE IF NOT EXISTS skill_gap_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    resume_id INTEGER NOT NULL,
    target_role TEXT NOT NULL,
    matching_skills TEXT, -- JSON array
    missing_skills TEXT, -- JSON array
    readiness_score REAL NOT NULL CHECK (readiness_score BETWEEN 0.0 AND 100.0),
    recommendations TEXT, -- JSON array
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(resume_id) REFERENCES uploaded_resumes(id) ON DELETE CASCADE
);

-- Table 6: github_profiles
CREATE TABLE IF NOT EXISTS github_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    github_username TEXT UNIQUE NOT NULL,
    public_repos_count INTEGER DEFAULT 0 CHECK (public_repos_count >= 0),
    total_stars_count INTEGER DEFAULT 0 CHECK (total_stars_count >= 0),
    contributions_last_year INTEGER DEFAULT 0 CHECK (contributions_last_year >= 0),
    languages_json TEXT, -- JSON structure of languages percentage
    last_fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Table 7: portfolio_scores
CREATE TABLE IF NOT EXISTS portfolio_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    github_profile_id INTEGER NOT NULL UNIQUE,
    portfolio_score REAL NOT NULL CHECK (portfolio_score BETWEEN 0.0 AND 100.0),
    code_quality_index REAL NOT NULL CHECK (code_quality_index BETWEEN 0.0 AND 100.0),
    activity_index REAL NOT NULL CHECK (activity_index BETWEEN 0.0 AND 100.0),
    diversity_index REAL NOT NULL CHECK (diversity_index BETWEEN 0.0 AND 100.0),
    detailed_metrics TEXT, -- JSON string
    scored_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(github_profile_id) REFERENCES github_profiles(id) ON DELETE CASCADE
);

-- Table 8: career_recommendations
CREATE TABLE IF NOT EXISTS career_recommendations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    target_title TEXT NOT NULL,
    similarity_score REAL NOT NULL CHECK (similarity_score BETWEEN 0.0 AND 1.0),
    matching_jobs_count INTEGER DEFAULT 0,
    demand_level TEXT CHECK (demand_level IN ('High', 'Medium', 'Low')),
    recommended_skills TEXT, -- JSON list
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Table 9: career_roadmaps
CREATE TABLE IF NOT EXISTS career_roadmaps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recommendation_id INTEGER NOT NULL UNIQUE,
    roadmap_steps TEXT NOT NULL, -- JSON Representation of steps/DAG
    estimated_months INTEGER NOT NULL CHECK (estimated_months > 0),
    difficulty_level TEXT CHECK (difficulty_level IN ('Beginner', 'Intermediate', 'Advanced')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(recommendation_id) REFERENCES career_recommendations(id) ON DELETE CASCADE
);

-- Table 10: salary_predictions
CREATE TABLE IF NOT EXISTS salary_predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    job_title TEXT NOT NULL,
    years_experience REAL NOT NULL CHECK (years_experience >= 0.0),
    location TEXT NOT NULL,
    skills_json TEXT, -- Skills features used for prediction
    predicted_annual_salary REAL NOT NULL CHECK (predicted_annual_salary > 0),
    confidence_interval_min REAL NOT NULL,
    confidence_interval_max REAL NOT NULL,
    predicted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);


-- ============================================================================
-- 2. JOB MARKET TABLES
-- ============================================================================

-- Table 11: job_listings
CREATE TABLE IF NOT EXISTS job_listings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    external_job_id TEXT UNIQUE NOT NULL, -- Adzuna job ID or other source ID
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    location TEXT NOT NULL,
    latitude REAL,
    longitude REAL,
    description TEXT,
    salary_min REAL,
    salary_max REAL,
    contract_type TEXT CHECK (contract_type IN ('full_time', 'part_time', 'contract', 'permanent')),
    job_url TEXT NOT NULL,
    source TEXT NOT NULL,
    posted_at TIMESTAMP,
    inserted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table 12: saved_jobs
CREATE TABLE IF NOT EXISTS saved_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    job_listing_id INTEGER NOT NULL,
    saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'saved' CHECK (status IN ('saved', 'applied', 'interviewing', 'offered', 'rejected')),
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY(job_listing_id) REFERENCES job_listings(id) ON DELETE CASCADE,
    UNIQUE(user_id, job_listing_id)
);

-- Table 13: skill_trends
CREATE TABLE IF NOT EXISTS skill_trends (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_name TEXT UNIQUE NOT NULL,
    category TEXT CHECK (category IN ('technical', 'soft', 'tool')),
    frequency_count INTEGER DEFAULT 0 CHECK (frequency_count >= 0),
    average_salary REAL,
    growth_rate REAL, -- percentage
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table 14: salary_data
CREATE TABLE IF NOT EXISTS salary_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_title TEXT NOT NULL,
    location TEXT NOT NULL,
    percentile_25 REAL,
    percentile_50 REAL,
    percentile_75 REAL,
    data_source TEXT,
    sample_size INTEGER DEFAULT 1,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(job_title, location)
);


-- ============================================================================
-- 3. ANALYTICS TABLES
-- ============================================================================

-- Table 15: dashboard_metrics
CREATE TABLE IF NOT EXISTS dashboard_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    metric_key TEXT UNIQUE NOT NULL,
    metric_value REAL NOT NULL,
    description TEXT,
    last_calculated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table 16: model_predictions
CREATE TABLE IF NOT EXISTS model_predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_name TEXT NOT NULL,
    model_version TEXT NOT NULL,
    input_features TEXT NOT NULL, -- JSON format
    predicted_output TEXT NOT NULL, -- JSON format
    actual_output TEXT, -- For feedback loop mapping
    evaluation_score REAL,
    logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table 17: user_activity_logs
CREATE TABLE IF NOT EXISTS user_activity_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    action TEXT NOT NULL,
    details TEXT, -- JSON payload details
    ip_hash TEXT,
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL
);

-- Table 18: notifications
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    is_read INTEGER DEFAULT 0 CHECK (is_read IN (0, 1)),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);


-- ============================================================================
-- 4. OPTIONAL ADVANCED TABLES
-- ============================================================================

-- Table 19: interview_readiness
CREATE TABLE IF NOT EXISTS interview_readiness (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    mock_title TEXT NOT NULL,
    technical_score REAL CHECK (technical_score BETWEEN 0.0 AND 100.0),
    communication_score REAL CHECK (communication_score BETWEEN 0.0 AND 100.0),
    overall_readiness REAL CHECK (overall_readiness BETWEEN 0.0 AND 100.0),
    feedback_notes TEXT,
    evaluated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Table 20: learning_resources
CREATE TABLE IF NOT EXISTS learning_resources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_name TEXT NOT NULL,
    resource_title TEXT NOT NULL,
    resource_type TEXT NOT NULL CHECK (resource_type IN ('course', 'book', 'video', 'documentation')),
    url TEXT NOT NULL,
    difficulty TEXT CHECK (difficulty IN ('Beginner', 'Intermediate', 'Advanced')),
    rating REAL CHECK (rating BETWEEN 0.0 AND 5.0),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- ============================================================================
-- INDEXES FOR QUERY OPTIMIZATION
-- ============================================================================

-- Core Indexing
CREATE INDEX IF NOT EXISTS idx_resumes_user ON uploaded_resumes(user_id);
CREATE INDEX IF NOT EXISTS idx_skills_resume ON extracted_skills(resume_id);
CREATE INDEX IF NOT EXISTS idx_skills_name ON extracted_skills(skill_name);
CREATE INDEX IF NOT EXISTS idx_ats_reports_resume ON ats_reports(resume_id);
CREATE INDEX IF NOT EXISTS idx_github_user ON github_profiles(user_id);
CREATE INDEX IF NOT EXISTS idx_portfolio_profile ON portfolio_scores(github_profile_id);
CREATE INDEX IF NOT EXISTS idx_recommendations_user ON career_recommendations(user_id);
CREATE INDEX IF NOT EXISTS idx_roadmaps_recommendation ON career_roadmaps(recommendation_id);
CREATE INDEX IF NOT EXISTS idx_salary_predictions_user ON salary_predictions(user_id);

-- Job Market Indexing
CREATE INDEX IF NOT EXISTS idx_job_listings_title ON job_listings(title);
CREATE INDEX IF NOT EXISTS idx_job_listings_location ON job_listings(location);
CREATE INDEX IF NOT EXISTS idx_saved_jobs_user ON saved_jobs(user_id);

-- Analytics Indexing
CREATE INDEX IF NOT EXISTS idx_activity_user_action ON user_activity_logs(user_id, action);
CREATE INDEX IF NOT EXISTS idx_activity_created_at ON user_activity_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_notifications_unread ON notifications(user_id, is_read);


-- ============================================================================
-- SAMPLE DATA INSERT STATEMENTS
-- ============================================================================

-- 1. Users Sample Data
INSERT INTO users (username, email, password_hash, role) VALUES 
('john_doe', 'john.doe@example.com', 'scrypt:32768:8:1$hashvalue1', 'student'),
('jane_smith', 'jane.smith@example.com', 'scrypt:32768:8:1$hashvalue2', 'student'),
('dev_lead', 'dev.lead@example.com', 'scrypt:32768:8:1$hashvalue3', 'recruiter'),
('sys_admin', 'admin@careercompass.ai', 'scrypt:32768:8:1$hashvalue4', 'admin'),
('alice_wonder', 'alice@example.com', 'scrypt:32768:8:1$hashvalue5', 'student');

-- 2. Job Listings Sample Data
INSERT INTO job_listings (external_job_id, title, company, location, latitude, longitude, description, salary_min, salary_max, contract_type, job_url, source, posted_at) VALUES 
('adz-1001', 'Software Engineer', 'TechCorp', 'San Francisco, CA', 37.7749, -122.4194, 'Develop Python web services and manage relational databases.', 90000, 130000, 'full_time', 'https://example.com/job1', 'Adzuna', '2026-06-10 10:00:00'),
('adz-1002', 'Data Scientist', 'InsightAnalytics', 'New York, NY', 40.7128, -74.0060, 'Build machine learning pipelines and analyze customer behavior patterns.', 110000, 150000, 'full_time', 'https://example.com/job2', 'Adzuna', '2026-06-11 11:30:00'),
('adz-1003', 'Frontend Developer', 'DesignAgency', 'Austin, TX', 30.2672, -97.7431, 'React JS UI development with focus on state management and glassmorphism styling.', 80000, 110000, 'permanent', 'https://example.com/job3', 'Adzuna', '2026-06-12 09:15:00'),
('adz-1004', 'Machine Learning Engineer', 'AIVentures', 'Seattle, WA', 47.6062, -122.3321, 'Deploy NLP models using PyTorch, spaCy, and sentence-transformers.', 120000, 170000, 'full_time', 'https://example.com/job4', 'Adzuna', '2026-06-12 14:00:00'),
('adz-1005', 'Database Administrator', 'FinanceSystems', 'Chicago, IL', 41.8781, -87.6298, 'Tune query performance and handle schema migrations on PostgreSQL.', 95000, 135000, 'contract', 'https://example.com/job5', 'Adzuna', '2026-06-12 16:45:00');

-- 3. Resumes Sample Data
INSERT INTO uploaded_resumes (user_id, file_name, file_path, file_size, mime_type, raw_text) VALUES 
(1, 'John_Doe_Resume.pdf', '/uploads/resumes/1_John_Doe.pdf', 154320, 'application/pdf', 'John Doe - Software Engineer. Experience: 2 years. Skills: Python, SQL, Git, HTML, CSS, JavaScript.'),
(2, 'Jane_Smith_Data_Science.pdf', '/uploads/resumes/2_Jane_Smith.pdf', 189200, 'application/pdf', 'Jane Smith. Data Science Graduate. Skills: Python, R, SQL, scikit-learn, spaCy, machine learning.'),
(5, 'Alice_Wonder_Frontend.pdf', '/uploads/resumes/5_Alice_Wonder.pdf', 142100, 'application/pdf', 'Alice Wonder. UI Engineer. Skills: HTML, CSS, JavaScript, React, Tailwind CSS, Figma.');

-- 4. Extracted Skills Sample Data
INSERT INTO extracted_skills (resume_id, skill_name, skill_type, confidence_score) VALUES 
(1, 'Python', 'technical', 0.98),
(1, 'SQL', 'technical', 0.95),
(1, 'Git', 'tool', 0.90),
(1, 'HTML', 'technical', 0.85),
(2, 'Python', 'technical', 0.99),
(2, 'scikit-learn', 'tool', 0.96),
(2, 'spaCy', 'tool', 0.92),
(3, 'JavaScript', 'technical', 0.97),
(3, 'React', 'technical', 0.95);

-- 5. ATS Reports Sample Data
INSERT INTO ats_reports (resume_id, ats_score, structure_score, grammar_score, keyword_score, formatting_issues, improvement_suggestions) VALUES 
(1, 85.5, 90.0, 95.0, 75.0, '{"bullets_too_long": false, "tables_detected": false}', '{"add_keywords": ["Docker", "Kubernetes"], "clarify_experience": "Quantify outcomes"}'),
(2, 78.0, 80.0, 85.0, 70.0, '{"bullets_too_long": true, "tables_detected": false}', '{"add_keywords": ["Pandas", "PyTorch"], "clarify_experience": "Summarize thesis details"}'),
(3, 91.0, 95.0, 90.0, 88.0, '{"bullets_too_long": false, "tables_detected": false}', '{"add_keywords": ["TypeScript", "Next.js"], "clarify_experience": "Show link to portfolio"}');

-- 6. GitHub Profiles Sample Data
INSERT INTO github_profiles (user_id, github_username, public_repos_count, total_stars_count, contributions_last_year, languages_json) VALUES 
(1, 'johndoe-dev', 25, 45, 180, '{"Python": 65, "JavaScript": 25, "HTML": 10}'),
(2, 'janesmith-data', 18, 120, 310, '{"Python": 80, "Jupyter Notebook": 15, "R": 5}'),
(5, 'alicewonder-ui', 32, 280, 420, '{"JavaScript": 70, "CSS": 20, "HTML": 10}');

-- 7. Career Recommendations Sample Data
INSERT INTO career_recommendations (user_id, target_title, similarity_score, matching_jobs_count, demand_level, recommended_skills) VALUES 
(1, 'Software Engineer', 0.88, 142, 'High', '["Django", "Docker", "PostgreSQL", "Algorithms"]'),
(2, 'Data Scientist', 0.92, 98, 'High', '["Pandas", "PyTorch", "Tableau", "Statistics"]'),
(5, 'Frontend Developer', 0.90, 120, 'High', '["TypeScript", "Redux", "Sass", "Testing"]');

-- 8. Salary Predictions Sample Data
INSERT INTO salary_predictions (user_id, job_title, years_experience, location, skills_json, predicted_annual_salary, confidence_interval_min, confidence_interval_max) VALUES 
(1, 'Software Engineer', 2.0, 'San Francisco, CA', '["Python", "SQL", "Git"]', 105000.0, 98000.0, 112000.0),
(2, 'Data Scientist', 1.0, 'New York, NY', '["Python", "scikit-learn", "spaCy"]', 115000.0, 108000.0, 122000.0),
(5, 'Frontend Developer', 3.0, 'Austin, TX', '["JavaScript", "React", "HTML", "CSS"]', 98000.0, 92000.0, 104000.0);
