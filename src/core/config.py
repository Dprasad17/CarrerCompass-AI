import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# Initialize path constants
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Set up logging configuration helper
def setup_logging(level_name: str = "INFO") -> None:
    level = getattr(logging, level_name.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler()
        ]
    )

class Settings:
    def __init__(self) -> None:
        self.BASE_DIR = BASE_DIR
        # Load environment file
        env_path = BASE_DIR / ".env"
        if env_path.exists():
            load_dotenv(dotenv_path=env_path)
        else:
            load_dotenv() # fallback to standard OS variables

        # Application config validation
        self.app_env: str = os.getenv("APP_ENV", "development").lower()
        self.log_level: str = os.getenv("LOG_LEVEL", "INFO")
        setup_logging(self.log_level)
        self.logger = logging.getLogger(self.__class__.__name__)

        # DB Setup config
        self.db_path: Path = BASE_DIR / os.getenv("DATABASE_URL", "data/careercompass.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # API Keys Validation
        self.adzuna_app_id: str = os.getenv("ADZUNA_APP_ID", "")
        self.adzuna_app_key: str = os.getenv("ADZUNA_APP_KEY", "")
        self.github_token: str = os.getenv("GITHUB_TOKEN", "")
        self.encryption_key: str = os.getenv("ENCRYPTION_KEY", "")

        # Verify API configuration warnings for local debugging
        if not self.adzuna_app_id or not self.adzuna_app_key:
            self.logger.warning("Adzuna API keys missing. Fallback client mode will be engaged automatically.")
        if not self.github_token:
            self.logger.warning("GitHub API token missing. Profiler will fall back to local mock data.")

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

# Instantiate global settings singleton
settings = Settings()
