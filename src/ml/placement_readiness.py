import logging
from typing import Dict, Any, List

logger = logging.getLogger("PlacementReadiness")

class PlacementReadinessEvaluator:
    """
    Computes global placement readiness index indicators based on
    skills matched, portfolio metrics, and work experience.
    """

    def calculate_readiness_score(self, candidate_skills: List[str], target_role_skills: List[str], github_score: float, experience_years: float) -> Dict[str, Any]:
        """
        Calculates a placement readiness index score (0.0 to 100.0).
        Formula: 50% Skill Match, 30% GitHub Portfolio, 20% Experience weighting.
        """
        # 1. Skill Match Component (50%)
        skill_score = 0.0
        if target_role_skills:
            cand_set = {s.lower().strip() for s in candidate_skills}
            target_set = {t.lower().strip() for t in target_role_skills}
            matches = cand_set.intersection(target_set)
            skill_score = (len(matches) / len(target_set)) * 100.0

        # 2. GitHub Portfolio Component (30%)
        # github_score expected in range [0, 100]
        clamped_github = max(0.0, min(github_score, 100.0))

        # 3. Experience Component (20%)
        # Assume 5 years of experience represents maximum entry-level readiness weighting
        exp_score = min(experience_years / 5.0, 1.0) * 100.0

        # Weighted calculation
        overall_readiness = (0.50 * skill_score) + (0.30 * clamped_github) + (0.20 * exp_score)
        overall_readiness = round(overall_readiness, 1)

        # Generate custom action points
        actions = []
        if skill_score < 70.0:
            actions.append("Acquire target technical skills required for this job title.")
        if clamped_github < 60.0:
            actions.append("Improve your GitHub score by pushing daily commits and writing clean Readmes.")
        if experience_years < 2.0:
            actions.append("Work on open source projects or seek internships to build industry experience.")

        # Determine confidence level
        confidence = 0.90 if len(candidate_skills) > 3 else 0.70

        return {
            "placement_readiness_score": overall_readiness,
            "skill_match_component": round(skill_score, 1),
            "portfolio_component": round(clamped_github, 1),
            "experience_component": round(exp_score, 1),
            "action_items": actions,
            "confidence_score": confidence
        }
