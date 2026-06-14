import re
import hashlib
import logging
from typing import Set, Tuple

logger = logging.getLogger("SecurityService")

# Global Security Constants
ALLOWED_EXTENSIONS: Set[str] = {"pdf", "docx"}
MAX_FILE_SIZE_BYTES: int = 5 * 1024 * 1024  # 5MB
# Standard PDF magic number (header) starts with %PDF-
PDF_MAGIC_BYTES: bytes = b"%PDF"

def validate_uploaded_file(file_bytes: bytes, file_name: str) -> Tuple[bool, str]:
    """
    Validates a file upload based on extension, size, and header magic numbers.
    Returns (is_valid, error_message).
    """
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        logger.error(f"File {file_name} rejected: exceeds 5MB size limit.")
        return False, "File exceeds maximum size limit of 5MB."

    ext = file_name.split(".")[-1].lower() if "." in file_name else ""
    if ext not in ALLOWED_EXTENSIONS:
        logger.error(f"File {file_name} rejected: disallowed extension '{ext}'.")
        return False, "Unsupported file extension. Only PDF and DOCX files are allowed."

    # Perform magic number check for PDF
    if ext == "pdf":
        if not file_bytes.startswith(PDF_MAGIC_BYTES):
            logger.error(f"File {file_name} rejected: failed PDF magic number validation.")
            return False, "Corrupted PDF file validation failed."

    return True, "File is valid."

def sanitize_input_text(text: str) -> str:
    """
    Cleans user input to prevent injection attacks and script insertions.
    """
    if not text:
        return ""
    # Strip HTML tags
    cleaned = re.sub(r"<[^>]*>", "", text)
    # Remove characters often used in command or scripting injections
    cleaned = re.sub(r"[;`$|]", "", cleaned)
    return cleaned.strip()

def hash_client_ip(ip_address: str) -> str:
    """
    Hashes an IP address using SHA256 to protect student privacy while enabling rate limiting.
    """
    if not ip_address:
        return ""
    return hashlib.sha256(ip_address.encode("utf-8")).hexdigest()
