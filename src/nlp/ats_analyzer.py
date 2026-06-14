import re
import logging
from typing import Dict, Any, List

logger = logging.getLogger("ATSAnalyzer")

# Industry standard strong action verbs expected by ATS systems
ACTION_VERBS = {
    "achieved", "acquired", "addressed", "administered", "advised", "analyzed",
    "architected", "assembled", "assessed", "budgeted", "built", "calculated",
    "collaborated", "communicated", "conceptualized", "conducted", "coordinated",
    "created", "debugged", "delegated", "designed", "developed", "directed",
    "documented", "engineered", "established", "evaluated", "executed",
    "expanded", "facilitated", "formulated", "generated", "guided",
    "implemented", "improved", "increased", "initiated", "inspected",
    "installed", "instituted", "integrated", "launched", "led", "managed",
    "mentored", "negotiated", "optimized", "organized", "oversaw",
    "performed", "planned", "programmed", "redesigned", "reduced",
    "reorganized", "researched", "resolved", "restructured", "reviewed",
    "scheduled", "solved", "spearheaded", "streamlined", "supervised",
    "supported", "systematized", "tested", "trained", "transformed",
    "updated", "utilized", "validated", "wrote"
}

# Cliché buzzwords that professional ATS filters penalize
CLICHE_BUZZWORDS = {
    "hardworking", "detail-oriented", "results-driven", "synergy",
    "team player", "self-starter", "go-getter", "think outside the box",
    "motivated", "strategic thinker", "passionate"
}

class ATSAnalyzer:
    """
    Evaluates resume text and extracted skills to produce ATS compatibility scores
    and suggestions for resume optimization using industry-aligned criteria.
    """

    def analyze_resume(self, parsed_resume: Dict[str, Any], extracted_skills: List[str], target_keywords: List[str]) -> Dict[str, Any]:
        """
        Runs complete ATS analysis checking structural components, keyword density, and formatting.
        Returns detailed scores and advice.
        """
        raw_text = parsed_resume.get("raw_text", "")
        has_jd = len(target_keywords) > 0
        
        # 1. Calculate Structure Score (0 - 100)
        structure_score, missing_sections, structural_issues = self._evaluate_structure(parsed_resume)

        # 2. Calculate Keyword Score (0 - 100)
        keyword_score, matched_keywords, missing_keywords, keyword_suggestions = self._evaluate_keywords(raw_text, extracted_skills, target_keywords)

        # 3. Calculate Formatting & Readability Score (0 - 100)
        format_score, format_issues, metrics_count, verbs_count, cliches_found = self._evaluate_formatting(raw_text, parsed_resume)

        # Calculate Overall ATS Score (weighted average)
        # Weighting: 45% Keyword Match, 30% Structure, 25% Formatting & Compliance
        if has_jd:
            ats_score = (0.45 * keyword_score) + (0.30 * structure_score) + (0.25 * format_score)
        else:
            # Without JD, keyword score is irrelevant (structure and formatting are 50/50)
            ats_score = (0.50 * structure_score) + (0.50 * format_score)

        # APPLY STRICT REAL-WORLD ATS CAPS
        # 1. Without a target JD, it is impossible to be highly optimized. Cap at 78.0%.
        if not has_jd:
            if ats_score > 78.0:
                ats_score = 78.0
        else:
            # 2. With JD, cap at 88.0% unless the candidate has outstanding formatting and content.
            # To pass the 88.0% threshold, the candidate must have:
            # - At least 5+ quantified impact metrics/numbers
            # - At least 12+ unique action verbs
            # - Zero cliché buzzwords
            # - All core sections (education, experience, contact) present
            has_core_sections = len(missing_sections) == 0
            if (metrics_count < 5 or verbs_count < 12 or len(cliches_found) > 0 or not has_core_sections):
                if ats_score > 88.0:
                    ats_score = 88.0 - (ats_score - 88.0) * 0.2
                    ats_score = min(88.0, ats_score)
            
            # Absolute maximum cap for any resume on a strict modern parser is 96.5%
            if ats_score > 96.5:
                ats_score = 96.5

        ats_score = max(0.0, round(ats_score, 1))

        # 4. Generate suggestions
        suggestions = self._compile_suggestions(missing_sections, structural_issues, missing_keywords, format_issues, keyword_suggestions)

        return {
            "ats_score": ats_score,
            "structure_score": structure_score,
            "keyword_score": keyword_score,
            "formatting_score": format_score,
            "matched_keywords": matched_keywords,
            "missing_keywords": missing_keywords,
            "formatting_issues": format_issues,
            "suggestions": suggestions,
            "placement_readiness_contribution": round(ats_score * 0.5, 1)
        }

    def _evaluate_structure(self, parsed_resume: Dict[str, Any]) -> tuple[float, List[str], List[str]]:
        """Evaluates whether all vital resume blocks exist and are sufficiently detailed."""
        sections = {
            "contact_info": parsed_resume.get("contact_info", {}),
            "education": parsed_resume.get("education", ""),
            "experience": parsed_resume.get("experience", ""),
            "projects": parsed_resume.get("projects", ""),
            "achievements": parsed_resume.get("achievements", "")
        }

        score = 0.0
        missing = []
        issues = []
        
        # Check contact details
        contact = sections["contact_info"]
        if contact.get("email") and contact.get("phone"):
            score += 20.0
        else:
            missing.append("Contact Information (Email/Phone)")
            issues.append("Contact information header is missing either a valid email address or phone number.")

        # Check other sections and check if they have substance (not just 1-2 words)
        section_weights = {
            "education": 20.0,
            "experience": 35.0,
            "projects": 15.0,
            "achievements": 10.0
        }

        for sec, weight in section_weights.items():
            content = sections[sec]
            if content and len(content.strip()) > 50:
                score += weight
                # If experience is present but brief (< 400 chars), penalize strictly
                if sec == "experience" and len(content.strip()) < 400:
                    score -= 20.0
                    issues.append("Work Experience section is too brief. Expand on deliverables, tech stacks, and quantifiable outcomes.")
                # If projects section is too short, penalize
                if sec == "projects" and len(content.strip()) < 200:
                    score -= 8.0
                    issues.append("Projects section lacks detail. Elaborate on the tech stack used, architectural decisions, and measurable outcomes.")
            else:
                missing.append(sec.capitalize())
                issues.append(f"Missing or extremely brief '{sec.capitalize()}' section.")

        return max(0.0, score), missing, issues

    def _evaluate_keywords(self, raw_text: str, extracted_skills: List[str], target_keywords: List[str]) -> tuple[float, List[str], List[str], List[str]]:
        """Calculates matched skills density and presence in context against target criteria."""
        if not target_keywords:
            return 80.0, [], [], []  # Without JD, default keyword alignment starts at 80% baseline

        raw_text_lower = raw_text.lower()
        candidate_set = {s.lower().strip() for s in extracted_skills}
        target_set = {k.lower().strip() for k in target_keywords}

        matched = list(candidate_set.intersection(target_set))
        missing = list(target_set.difference(candidate_set))

        if not target_set:
            return 80.0, [], [], []

        keyword_depth_scores = []
        keyword_suggestions = []

        for kw in target_set:
            if kw in candidate_set:
                # Count occurrences in raw text
                escaped_kw = re.escape(kw)
                occurrences = len(re.findall(r'\b' + escaped_kw + r'\b', raw_text_lower))
                
                # Contextual density check: ATS requires keywords to be integrated into work details (2+ occurrences)
                if occurrences >= 2:
                    keyword_depth_scores.append(1.0)
                else:
                    keyword_depth_scores.append(0.6) # Deduct for keyword stuffing/flat listing
                    keyword_suggestions.append(f"Describe your hands-on achievements using '{kw}' inside your experience or projects instead of just listing it.")
            else:
                keyword_depth_scores.append(0.0)

        # Score is the average of depth scores
        score = (sum(keyword_depth_scores) / len(target_set)) * 100.0
        
        # Format names back to capitalized/original
        matched_formatted = []
        for kw in target_keywords:
            if kw.lower().strip() in candidate_set:
                matched_formatted.append(kw)
        
        missing_formatted = []
        for kw in target_keywords:
            if kw.lower().strip() not in candidate_set:
                missing_formatted.append(kw)

        return round(score, 1), matched_formatted, missing_formatted, keyword_suggestions

    def _evaluate_formatting(self, raw_text: str, parsed_resume: Dict[str, Any]) -> tuple[float, List[str], int, int, List[str]]:
        """Scans raw text for characters, lengths, metrics, and layout issues that throw off ATS parsers."""
        score = 100.0
        issues = []

        # 1. Page Length / Word Count Check
        words = raw_text.split()
        word_count = len(words)
        if word_count < 350:
            score -= 25.0
            issues.append(f"Resume content is extremely short ({word_count} words). A professional resume requires 450-900 words to score high on modern parser systems.")
        elif word_count > 1200:
            score -= 15.0
            issues.append(f"Resume is too wordy ({word_count} words). Keep details focused, ideally under 1000 words.")

        # 2. Strong Action Verbs Density Check
        raw_text_lower = raw_text.lower()
        found_verbs = [verb for verb in ACTION_VERBS if re.search(r'\b' + re.escape(verb) + r'\b', raw_text_lower)]
        verbs_count = len(found_verbs)
        if verbs_count < 6:
            score -= 20.0
            issues.append(f"Lacks action verbs (only {verbs_count} found). Begin resume bullet points with strong, result-driven verbs (e.g. 'Architected', 'Optimized').")
        elif verbs_count < 12:
            score -= 10.0
            issues.append(f"Action verb density is moderate ({verbs_count} found). Replace passive descriptors like 'responsible for' with actionable outcomes.")

        # 3. Quantifiable Results & Metrics Check (Crucial for recruiter compliance)
        # Search for percentages, dollar figures, or numbers indicating metrics
        metrics = re.findall(r'(?:\d+(?:\.\d+)?\s*(?:%|\s*percent|x|\s*million|billion|k|usd|dollars))|(?:\$\s*\d+)', raw_text_lower)
        metrics_count = len(metrics)
        if metrics_count < 3:
            score -= 25.0
            issues.append(f"Insufficient quantifiable achievements (only {metrics_count} metrics found). ATS algorithms prioritize resumes containing metrics (e.g., 'reduced latency by 40%', 'managed $10k budget').")
        elif metrics_count < 5:
            score -= 10.0
            issues.append(f"Quantifiable results are moderate ({metrics_count} metrics found). Try to back up every project milestone with a metric or percentage.")

        # 4. Buzzwords / Clichés Penalties
        found_cliches = [buzz for buzz in CLICHE_BUZZWORDS if re.search(r'\b' + re.escape(buzz) + r'\b', raw_text_lower)]
        if found_cliches:
            deduction = min(len(found_cliches) * 5, 20)
            score -= deduction
            issues.append(f"Deduction for generic buzzwords: {', '.join(found_cliches)}. Swap clichés with actionable details.")

        # 5. Complex Layout / Tabular structure markers
        if len(re.findall(r"\|", raw_text)) > 8:
            score -= 12.0
            issues.append("Detected excessive vertical piping indicating tables. Simple single-column layouts prevent parsing errors.")

        return max(0.0, min(100.0, score)), issues, metrics_count, verbs_count, found_cliches

    def _compile_suggestions(
        self,
        missing_sections: List[str],
        structural_issues: List[str],
        missing_keywords: List[str],
        format_issues: List[str],
        keyword_suggestions: List[str]
    ) -> List[str]:
        """Assembles list of actions to enhance scores."""
        suggestions = []
        
        if missing_sections:
            suggestions.append(f"Add the following missing or critical sections: {', '.join(missing_sections)}.")
            
        for issue in structural_issues:
            if issue not in suggestions:
                suggestions.append(issue)
  
        for issue in format_issues:
            if issue not in suggestions:
                suggestions.append(issue)

        if missing_keywords:
            suggestions.append(f"Incorporate missing target keywords to align with job description: {', '.join(missing_keywords[:8])}.")
            
        suggestions.extend(keyword_suggestions[:3])
        
        return suggestions


