import time
import logging
from typing import Dict, Any, List, Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
from src.core.config import settings

logger = logging.getLogger("AdzunaClient")

class AdzunaClient:
    """
    Client interface for Adzuna Job Search API.
    Handles rate-limiting, request retries, and connection pooling.
    """
    def __init__(self) -> None:
        self.app_id = settings.adzuna_app_id
        self.app_key = settings.adzuna_app_key
        self.base_url = "https://api.adzuna.com/v1/api/jobs/gb/search" # Default to GB or US search context
        
        # Configure requests session with connection pool and automatic retries
        self.session = requests.Session()
        retries = Retry(
            total=3,
            backoff_factor=1.5,
            status_forcelist=[429, 500, 502, 503, 504],
            raise_on_status=False
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retries))

    def search_jobs(self, keyword: str, location: str, country_code: str = "gb", app_id: str = "", app_key: str = "", page: int = 1) -> Optional[Dict[str, Any]]:
        """
        Queries Adzuna API for job postings.
        """
        active_app_id = app_id if app_id.strip() else self.app_id
        active_app_key = app_key if app_key.strip() else self.app_key

        if not active_app_id or not active_app_key:
            logger.warning("Adzuna API credentials missing. Aborting API request.")
            return None

        # Build query parameters according to Adzuna schema specs
        params = {
            "app_id": active_app_id,
            "app_key": active_app_key,
            "what": keyword,
            "where": location,
            "results_per_page": 10,
            "content-type": "application/json"
        }

        url = f"https://api.adzuna.com/v1/api/jobs/{country_code.strip().lower()}/search/{page}"
        
        try:
            logger.info(f"Calling Adzuna API: search for '{keyword}' in '{location}' ({country_code}) (Page {page})")
            response = self.session.get(url, params=params, timeout=10)
            
            # Handle rate limits
            if response.status_code == 429:
                logger.error("Adzuna API rate limit (429) reached.")
                return None
                
            response.raise_for_status()
            
            raw_data = response.json()
            return self._parse_response(raw_data)

        except requests.exceptions.RequestException as e:
            logger.error(f"Adzuna API query failed with exception: {e}")
            return None

    def _parse_response(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Maps Adzuna response items to standard internal schema format."""
        results = []
        for item in raw_data.get("results", []):
            results.append({
                "external_job_id": str(item.get("id")),
                "title": item.get("title", ""),
                "company": item.get("company", {}).get("display_name", ""),
                "location": item.get("location", {}).get("display_name", ""),
                "latitude": item.get("latitude"),
                "longitude": item.get("longitude"),
                "description": item.get("description", ""),
                "salary_min": item.get("salary_min"),
                "salary_max": item.get("salary_max"),
                "job_url": item.get("redirect_url", ""),
                "source": "Adzuna"
            })
        return {
            "jobs": results,
            "total_matches": raw_data.get("count", 0)
        }
