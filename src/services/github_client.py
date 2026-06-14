import logging
from typing import Dict, Any, List, Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
from src.core.config import settings

logger = logging.getLogger("GitHubClient")

class GitHubClient:
    """
    Client interface for GitHub REST API.
    Fetches developer repositories, language weights, and commits indicators.
    """
    def __init__(self) -> None:
        self.token = settings.github_token
        self.base_url = "https://api.github.com"
        
        # Configure requests session with connection pool and automatic retries
        self.session = requests.Session()
        retries = Retry(
            total=3,
            backoff_factor=1.0,
            status_forcelist=[500, 502, 503, 504],
            raise_on_status=False
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retries))
        
        # Inject authorization header if token exists
        if self.token:
            self.session.headers.update({"Authorization": f"token {self.token}"})
        self.session.headers.update({"Accept": "application/vnd.github.v3+json"})

    def fetch_user_profile(self, username: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves main GitHub user statistics.
        """
        url = f"{self.base_url}/users/{username}"
        try:
            logger.info(f"Fetching GitHub profile for: {username}")
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 404:
                logger.warning(f"GitHub user {username} not found.")
                return None
                
            response.raise_for_status()
            user_data = response.json()

            # Retrieve repo statistics
            repos_url = user_data.get("repos_url")
            repos = self._fetch_user_repos(repos_url) if repos_url else []
            
            # Calculate language weights
            languages = self._calculate_languages(repos)

            return {
                "github_username": username,
                "public_repos_count": user_data.get("public_repos", 0),
                "total_stars_count": sum(r.get("stargazers_count", 0) for r in repos),
                "contributions_last_year": user_data.get("public_gists", 0) * 5 + len(repos) * 10, # Mock index based on gists/repos if graphql isn't loaded
                "languages_json": languages
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"GitHub profile retrieval failed: {e}")
            return None

    def _fetch_user_repos(self, repos_url: str) -> List[Dict[str, Any]]:
        """Retrieves listing of user repositories (max 100)."""
        try:
            response = self.session.get(f"{repos_url}?per_page=100", timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch repositories: {e}")
            return []

    def _calculate_languages(self, repos: List[Dict[str, Any]]) -> Dict[str, float]:
        """Aggregates primary languages weight percentages across repositories."""
        lang_counts: Dict[str, int] = {}
        total_repos = len(repos)

        if total_repos == 0:
            return {}

        for repo in repos:
            lang = repo.get("language")
            if lang:
                lang_counts[lang] = lang_counts.get(lang, 0) + 1

        # Calculate percentages
        return {lang: round((count / total_repos) * 100.0, 1) for lang, count in lang_counts.items()}
