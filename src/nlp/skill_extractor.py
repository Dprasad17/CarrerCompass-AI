import os
import logging
from typing import List, Dict, Tuple, Set
import spacy
from spacy.matcher import PhraseMatcher
import pandas as pd
from src.core.config import settings

logger = logging.getLogger("SkillExtractor")

class SkillExtractor:
    """
    NLP entity extractor utilizing spaCy to scan resumes for technical,
    soft, and tool skills based on a local dictionary mapping.
    """
    def __init__(self) -> None:
        # Load spaCy model
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            logger.warning("spaCy model 'en_core_web_sm' not found. Installing via downloader...")
            from spacy.cli import download
            download("en_core_web_sm")
            self.nlp = spacy.load("en_core_web_sm")

        self.matcher = PhraseMatcher(self.nlp.vocab, attr="LOWER")
        self.skills_taxonomy: Dict[str, str] = {} # maps lower skill -> category ('technical', 'soft')
        self._load_taxonomy()

    def _load_taxonomy(self) -> None:
        """Loads technical and soft skills vocabulary from CSV or fallback dictionary."""
        csv_path = settings.BASE_DIR / "datasets" / "skills_dataset.csv"
        
        # Default fallback skills dataset
        tech_skills = {"python", "sql", "javascript", "react", "html", "css", "git", "scikit-learn", "spacy", "postgres", "sqlite"}
        soft_skills = {"communication", "leadership", "problem solving", "critical thinking", "teamwork", "adaptability"}

        if csv_path.exists():
            try:
                df = pd.read_csv(csv_path)
                for _, row in df.iterrows():
                    name = str(row["skill_name"]).lower().strip()
                    category = str(row["category"]).lower().strip()
                    self.skills_taxonomy[name] = category
            except Exception as e:
                logger.error(f"Error loading taxonomy from CSV {csv_path}: {e}. Loading fallback list.")
        
        # Populate defaults if database list not loaded
        if not self.skills_taxonomy:
            for s in tech_skills:
                self.skills_taxonomy[s] = "technical"
            for s in soft_skills:
                self.skills_taxonomy[s] = "soft"

        # Register matching patterns in spaCy PhraseMatcher
        for skill_name in self.skills_taxonomy.keys():
            pattern = self.nlp.make_doc(skill_name)
            self.matcher.add(skill_name, [pattern])

    def extract_skills(self, text: str) -> List[Tuple[str, str, float]]:
        """
        Scans input text for skills.
        Returns a list of tuples containing: (skill_name, skill_category, confidence_score)
        """
        if not text:
            return []

        doc = self.nlp(text.lower())
        matches = self.matcher(doc)
        
        extracted: Set[Tuple[str, str, float]] = set()
        for match_id, start, end in matches:
            matched_span = doc[start:end].text.strip()
            # Retrieve category
            category = self.skills_taxonomy.get(matched_span, "technical")
            
            # Simple context confidence metric: exact matches have a high baseline
            confidence = 1.0 if len(matched_span.split()) > 1 else 0.9
            
            # Use original capitalization template if possible
            capitalized_name = matched_span.capitalize() if matched_span not in {"sql", "html", "css", "git", "nlp", "ats"} else matched_span.upper()
            extracted.add((capitalized_name, category, confidence))
            
        return list(extracted)
