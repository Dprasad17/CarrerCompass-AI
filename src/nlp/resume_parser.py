import re
import logging
from typing import Dict, Any, Optional
import pdfplumber
from docx import Document

logger = logging.getLogger("ResumeParser")

class ResumeParser:
    """
    Parser that extracts structured fields (Contact info, Education, Experience, Projects, Achievements)
    from PDF and DOCX resume documents.
    """

    def extract_text_from_pdf(self, file_path: str) -> str:
        """Extracts raw text from a PDF document."""
        text = ""
        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
        except Exception as e:
            logger.error(f"Error parsing PDF file {file_path}: {e}")
            raise e
        return text

    def extract_text_from_docx(self, file_path: str) -> str:
        """Extracts raw text from a DOCX document."""
        text = ""
        try:
            doc = Document(file_path)
            for para in doc.paragraphs:
                text += para.text + "\n"
        except Exception as e:
            logger.error(f"Error parsing DOCX file {file_path}: {e}")
            raise e
        return text

    def parse_resume(self, file_path: str) -> Dict[str, Any]:
        """Parses a resume file and structures its content."""
        ext = file_path.split(".")[-1].lower()
        if ext == "pdf":
            raw_text = self.extract_text_from_pdf(file_path)
        elif ext == "docx":
            raw_text = self.extract_text_from_docx(file_path)
        else:
            raise ValueError(f"Unsupported file format: {ext}")

        return self.parse_resume_text(raw_text)

    def parse_resume_text(self, raw_text: str) -> Dict[str, Any]:
        """Parses raw text of a resume and structures its content."""
        return {
            "raw_text": raw_text,
            "contact_info": self._extract_contact_info(raw_text),
            "education": self._extract_education(raw_text),
            "experience": self._extract_experience(raw_text),
            "projects": self._extract_projects(raw_text),
            "achievements": self._extract_achievements(raw_text),
            "skills_section": self._extract_skills_section(raw_text)
        }


    # =========================================================================
    # NLP / REGEX SECTION EXTRACTIONS
    # =========================================================================

    def _extract_contact_info(self, text: str) -> Dict[str, str]:
        """Extracts email, phone number, and links using regex patterns."""
        email_pattern = r"[\w\.-]+@[\w\.-]+\.\w+"
        phone_pattern = r"\+?\d[\d\-\s\(\)]{8,14}\d"
        github_pattern = r"github\.com/[\w-]+"

        email = re.search(email_pattern, text)
        phone = re.search(phone_pattern, text)
        github = re.search(github_pattern, text)

        return {
            "email": email.group(0) if email else "",
            "phone": phone.group(0) if phone else "",
            "github_profile": github.group(0) if github else ""
        }

    def _extract_education(self, text: str) -> str:
        """Helper to isolate education sections using header anchors."""
        pattern = r"(?i)(?:education|academic|studies|university)[\s\S]*?(?=(?:experience|employment|projects|skills|certifications|achievements|$))"
        match = re.search(pattern, text)
        return match.group(0).strip() if match else ""

    def _extract_experience(self, text: str) -> str:
        """Helper to isolate work experience sections using header anchors."""
        pattern = r"(?i)(?:experience|employment|work history|professional history)[\s\S]*?(?=(?:education|projects|skills|certifications|achievements|$))"
        match = re.search(pattern, text)
        return match.group(0).strip() if match else ""

    def _extract_projects(self, text: str) -> str:
        """Helper to isolate project details."""
        pattern = r"(?i)(?:projects|academic projects|personal projects)[\s\S]*?(?=(?:experience|education|skills|certifications|achievements|$))"
        match = re.search(pattern, text)
        return match.group(0).strip() if match else ""

    def _extract_achievements(self, text: str) -> str:
        """Helper to isolate achievements, awards, and certifications details."""
        pattern = r"(?i)(?:achievements|awards|certifications|honors)[\s\S]*?(?=(?:experience|education|projects|skills|$))"
        match = re.search(pattern, text)
        return match.group(0).strip() if match else ""

    def _extract_skills_section(self, text: str) -> str:
        """Helper to isolate technical/soft skills sections using header anchors."""
        pattern = r"(?i)(?:technical skills|skills|technologies|proficiencies|core competencies|expertise)[\s\S]*?(?=(?:experience|employment|work history|education|projects|achievements|certifications|$))"
        match = re.search(pattern, text)
        return match.group(0).strip() if match else ""

