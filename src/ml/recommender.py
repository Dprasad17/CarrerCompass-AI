import logging
from typing import List, Dict, Any
import numpy as np

logger = logging.getLogger("Recommender")

class Recommender:
    """
    ML Matcher mapping candidate skill lists to job descriptions
    using sentence embedding similarity or local token intersections.
    """
    def __init__(self) -> None:
        self.model = None
        self._load_transformer()

    def _load_transformer(self) -> None:
        """Attempts to load sentence-transformers in a thread-safe manner."""
        try:
            from sentence_transformers import SentenceTransformer
            # Load local model (will look in cache directory first)
            self.model = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("SentenceTransformer model loaded successfully.")
        except Exception as e:
            logger.warning(f"Could not initialize SentenceTransformer offline: {e}. Falling back to token intersection similarity.")

    def recommend_jobs(self, candidate_skills: List[str], jobs: List[Dict[str, Any]], top_n: int = 5) -> List[Dict[str, Any]]:
        """
        Matches candidate skills against a list of job listings.
        Returns a sorted list of matched jobs with matching scores.
        """
        results = []
        if not candidate_skills or not jobs:
            return []

        # If transformer model is loaded, run semantic embedding similarity
        if self.model:
            try:
                candidate_text = " ".join(candidate_skills)
                candidate_emb = self.model.encode(candidate_text, convert_to_numpy=True)

                for job in jobs:
                    desc = job.get("description", "")
                    title = job.get("title", "")
                    job_text = f"{title} {desc}"
                    
                    job_emb = self.model.encode(job_text, convert_to_numpy=True)
                    
                    # Compute Cosine Similarity
                    dot_product = np.dot(candidate_emb, job_emb)
                    norm_a = np.linalg.norm(candidate_emb)
                    norm_b = np.linalg.norm(job_emb)
                    similarity = float(dot_product / (norm_a * norm_b)) if norm_a > 0 and norm_b > 0 else 0.0

                    results.append({
                        "job": job,
                        "similarity_score": round(similarity, 3),
                        "match_method": "semantic_embedding"
                    })
            except Exception as e:
                logger.error(f"Semantic match processing failed: {e}. Rolling back to token overlap.")
                results = []

        # Fallback keyword overlap matcher (if transformer is not loaded or fails)
        if not results:
            cand_set = {s.lower().strip() for s in candidate_skills}
            for job in jobs:
                desc = job.get("description", "").lower()
                title = job.get("title", "").lower()
                combined_text = f"{title} {desc}"

                # Calculate how many candidate skills exist in the job listing text
                matched_count = sum(1 for skill in cand_set if skill in combined_text)
                similarity = (matched_count / len(cand_set)) if cand_set else 0.0

                results.append({
                    "job": job,
                    "similarity_score": round(similarity, 3),
                    "match_method": "token_intersection"
                })

        # Sort results descending by score
        results.sort(key=lambda x: x["similarity_score"], reverse=True)
        return results[:top_n]
