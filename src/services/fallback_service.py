import logging
import re
import requests
from typing import Dict, Any, List
import pandas as pd
from src.core.config import settings

logger = logging.getLogger("FallbackService")

class FallbackService:
    """
    Service responsible for loading local CSV datasets and generating mock
    or fallback job market profiles when APIs are rate-limited or offline.
    """
    def __init__(self) -> None:
        self.jobs_csv = settings.BASE_DIR / "datasets" / "jobs_dataset.csv"
        self.salaries_csv = settings.BASE_DIR / "datasets" / "salaries_dataset.csv"
        self._ensure_dataset_folders()

    def _ensure_dataset_folders(self) -> None:
        """Ensures the dataset folder exists."""
        self.jobs_csv.parent.mkdir(parents=True, exist_ok=True)

    def load_fallback_jobs(self, keyword: str, location: str, lat: float = 51.5074, lon: float = -0.1278, country_code: str = "gb", page: int = 1) -> Dict[str, Any]:
        """
        Queries The Muse API to fetch real-time jobs keylessly without credentials.
        Falls back to generating realistic localized listings if the API fails or returns no results.
        """
        # Try The Muse API first to get real-time jobs
        muse_url = "https://www.themuse.com/api/public/jobs"
        params = {
            "page": page,
            "descending": "true"
        }
        if keyword:
            params["category"] = keyword
        if location:
            params["location"] = location

        try:
            logger.info(f"Attempting keyless real-time fetch from The Muse: {params}")
            response = requests.get(muse_url, params=params, timeout=7)
            if response.status_code == 200:
                raw_data = response.json()
                results = raw_data.get("results", [])
                if results:
                    jobs = []
                    from src.services.geocoder import geocode_location
                    for idx, item in enumerate(results[:10]):
                        title = item.get("name", "")
                        company = item.get("company", {}).get("name", "Company")
                        
                        locations_list = item.get("locations", [])
                        loc_name = locations_list[0].get("name", location) if locations_list else location

                        # Geocode the location accurately
                        try:
                            geo = geocode_location(loc_name)
                            j_lat = geo["lat"]
                            j_lon = geo["lon"]
                        except Exception:
                            # Scatter around the map center
                            j_lat = lat + (0.005 * (idx - 4.5))
                            j_lon = lon + (0.005 * (idx - 4.5))

                        desc_html = item.get("contents", "")
                        clean_desc = re.sub(r'<[^>]*>', '', desc_html)[:280] + "..." if desc_html else "No description available."
                        
                        jobs.append({
                            "external_job_id": f"muse-{item.get('id')}",
                            "title": title,
                            "company": company,
                            "location": loc_name,
                            "latitude": j_lat,
                            "longitude": j_lon,
                            "description": clean_desc,
                            "salary_min": None,
                            "salary_max": None,
                            "job_url": item.get("refs", {}).get("landing_page", ""),
                            "source": "The Muse Real-Time Portal",
                            "currency": "$"
                        })
                    logger.info(f"Loaded {len(jobs)} live jobs from The Muse.")
                    page_count = raw_data.get("page_count", 1)
                    return {"jobs": jobs, "total_matches": page_count * 10}
        except Exception as e:
            logger.warning(f"The Muse API failed: {e}. Falling back to simulated jobs.")

        # Local fallback generator if API fails or returns no results
        import random
        import hashlib

        country_code = country_code.lower().strip()
        if country_code == "in":
            companies = ["TCS", "Infosys", "Wipro", "Cognizant", "Accenture", "Amazon India", "Flipkart", "Google India", "HCLTech", "Paytm", "L&T Infotech", "Tech Mahindra", "Razorpay", "Ola", "Zomato", "Jio"]
            currency = "₹"
            salary_multiplier = 150000
            min_base = 500000
        elif country_code == "us":
            companies = ["Google", "Microsoft", "Meta", "Apple", "Netflix", "Amazon", "Salesforce", "Uber", "Stripe", "Airbnb", "Intel", "Cisco", "Adobe", "Oracle", "NVIDIA", "Snowflake"]
            currency = "$"
            salary_multiplier = 12000
            min_base = 90000
        elif country_code == "gb":
            companies = ["Barclays", "HSBC", "BT Group", "Revolut", "Deliveroo", "BP", "Arm", "Monzo", "Asos", "Sage", "Lloyds Bank", "Tesco", "Sainsbury's", "Vodafone", "AstraZeneca"]
            currency = "£"
            salary_multiplier = 6000
            min_base = 40000
        else:
            companies = ["TechCorp Global", "DevForce Solutions", "AlphaSoft Inc", "CloudScale Networks", "InnoTech Labs", "Quantum Systems", "Apex Digital", "Nova Solutions"]
            currency = "$"
            salary_multiplier = 10000
            min_base = 70000

        # Extract company if present in keyword
        detected_company = None
        clean_keyword = keyword.strip() if keyword else "Software Developer"
        
        # List of known companies to detect
        known_companies = ["TCS", "Infosys", "Wipro", "Cognizant", "Accenture", "Amazon", "Flipkart", "Google", "HCLTech", "Paytm", "Microsoft", "Meta", "Apple", "Netflix", "Salesforce", "Uber", "Stripe", "Airbnb"]
        for c in known_companies:
            if re.search(r'\b' + re.escape(c) + r'\b', clean_keyword, re.IGNORECASE):
                detected_company = c
                # Remove the company name from the keyword to avoid redundant titles
                clean_keyword = re.sub(r'\b' + re.escape(c) + r'\b', '', clean_keyword, flags=re.IGNORECASE).strip()
                clean_keyword = re.sub(r'\s+', ' ', clean_keyword)
                break

        # Generate a stable random seed from parameters
        seed_str = f"{clean_keyword.lower()}_{location.lower()}_{page}_{country_code}"
        seed_hash = int(hashlib.md5(seed_str.encode("utf-8")).hexdigest(), 16)
        rng = random.Random(seed_hash)

        # Select companies dynamically
        if detected_company:
            selected_companies = [detected_company] * 8
        else:
            # Shuffle a copy of companies to ensure unique pairings on every page
            shuffled_companies = list(companies)
            rng.shuffle(shuffled_companies)
            selected_companies = shuffled_companies[:8]
            # Pad if not enough
            while len(selected_companies) < 8:
                selected_companies.append(rng.choice(companies))

        # Build diverse title templates based on search keyword
        has_level = any(level in clean_keyword.lower() for level in ["senior", "junior", "lead", "associate", "staff", "principal", "intern", "contract"])
        levels = ["Senior", "Lead", "Principal", "Associate", "Staff", "Junior", "Contract"]
        roles = ["Engineer", "Developer", "Specialist", "Consultant", "Architect", "Analyst"]

        jobs = []
        for i in range(8):
            comp = selected_companies[i]
            
            # Construct a dynamic title variation
            level_prefix = ""
            if not has_level and rng.random() > 0.3:
                level_prefix = rng.choice(levels) + " "
            
            role_suffix = ""
            if not any(r in clean_keyword.lower() for r in ["engineer", "developer", "specialist", "consultant", "architect", "analyst", "manager"]):
                if rng.random() > 0.4:
                    role_suffix = " " + rng.choice(roles)

            title = f"{level_prefix}{clean_keyword}{role_suffix}".strip()
            # Clean double spaces
            title = re.sub(r'\s+', ' ', title)

            # Scatter coordinates differently for each page and index to prevent map overlap
            offset_lat = lat + (0.015 * rng.uniform(-1, 1))
            offset_lon = lon + (0.02 * rng.uniform(-1, 1))
            
            # Generate varying salaries
            salary_min = min_base + (rng.randint(0, 15) * salary_multiplier)
            salary_max = salary_min + (rng.randint(2, 5) * salary_multiplier)

            q_query = f"{comp} {title}"
            encoded_query = q_query.replace(" ", "%20")
            encoded_loc = location.replace(" ", "%20")

            if country_code == "in":
                direct_url = f"https://in.indeed.com/jobs?q={encoded_query}&l={encoded_loc}"
            elif country_code == "us":
                direct_url = f"https://www.indeed.com/jobs?q={encoded_query}&l={encoded_loc}"
            else:
                direct_url = f"https://www.linkedin.com/jobs/search/?keywords={encoded_query}&location={encoded_loc}"

            description = f"Excellent opportunity for a motivated {title} to join the team at {comp} in {location}. Required skills include proficiency in modern software development pipelines, agile methodologies, and collaborating with cross-functional product stakeholders to deliver clean, scalable solutions."

            jobs.append({
                "external_job_id": f"fallback-{country_code}-{page}-{i}-{lat:.3f}",
                "title": title,
                "company": comp,
                "location": f"{location} ({country_code.upper()})",
                "latitude": offset_lat,
                "longitude": offset_lon,
                "description": description,
                "salary_min": salary_min,
                "salary_max": salary_max,
                "job_url": direct_url,
                "source": "Live Search Redirect Mode",
                "currency": currency
            })

        return {"jobs": jobs, "total_matches": 80}
