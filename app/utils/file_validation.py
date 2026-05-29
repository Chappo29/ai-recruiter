"""File validation utilities with MIME type checking."""

import logging
from typing import Literal

from fastapi import HTTPException, status

from app.core.config import (
    MAX_AVATAR_SIZE_BYTES,
    MAX_RESUME_SIZE_BYTES,
    MAX_RESUME_SIZE_MB,
)

logger = logging.getLogger(__name__)

# MIME type validation
ALLOWED_PDF_MIMES = {"application/pdf"}
ALLOWED_IMAGE_MIMES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}


class ResumeFileTooLargeError(Exception):
    """Raised when a resume PDF exceeds the configured size limit."""

    def __init__(self, size_bytes: int, max_bytes: int = MAX_RESUME_SIZE_BYTES):
        self.size_bytes = size_bytes
        self.max_bytes = max_bytes
        super().__init__(f"Resume file too large: {size_bytes} > {max_bytes}")


def format_file_size_mb(size_bytes: int) -> str:
    """Human-readable size for user messages."""
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.0f} КБ"
    return f"{size_bytes / (1024 * 1024):.1f} МБ"


def resume_size_limit_message(*, actual_bytes: int | None = None) -> str:
    """Russian message when resume PDF exceeds the limit."""
    lines = ["❌ Файл слишком большой."]
    if actual_bytes is not None and actual_bytes > 0:
        lines.append(
            f"Ваш файл: {format_file_size_mb(actual_bytes)}. "
            f"Максимум: {MAX_RESUME_SIZE_MB} МБ."
        )
    else:
        lines.append(f"Максимальный размер резюме: {MAX_RESUME_SIZE_MB} МБ.")
    lines.extend(
        [
            "",
            "Обычно PDF с hh.ru весит 200–500 КБ.",
            "Если больше — возможно, в файле сканы или лишние страницы.",
            "Скачайте резюме с hh.ru заново (PDF) или уберите тяжёлые картинки.",
        ]
    )
    return "\n".join(lines)


def validate_resume_file_size(size_bytes: int) -> None:
    """Validate resume size for bot/non-HTTP callers."""
    if size_bytes > MAX_RESUME_SIZE_BYTES:
        raise ResumeFileTooLargeError(size_bytes)


def validate_file_size(
    file_bytes: bytes,
    file_type: Literal["resume", "avatar"],
) -> None:
    """Validate file size against configured limits."""
    if file_type == "resume":
        max_size = MAX_RESUME_SIZE_BYTES
        max_mb = max_size / (1024 * 1024)
    else:  # avatar
        max_size = MAX_AVATAR_SIZE_BYTES
        max_mb = max_size / (1024 * 1024)

    if len(file_bytes) > max_size:
        if file_type == "resume":
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=resume_size_limit_message(actual_bytes=len(file_bytes)),
            )
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size: {max_mb:.0f} MB",
        )


def detect_mime_type(file_bytes: bytes) -> str:
    """
    Detect MIME type from file content using magic numbers.
    
    Falls back to basic detection if python-magic is not available.
    """
    try:
        import magic
        mime = magic.from_buffer(file_bytes[:2048], mime=True)
        return str(mime)
    except ImportError:
        logger.warning(
            "python-magic not installed — using fallback MIME detection. "
            "Install: pip install python-magic python-magic-bin (Windows)"
        )
        return _fallback_mime_detection(file_bytes)


def _fallback_mime_detection(file_bytes: bytes) -> str:
    """Basic MIME detection using magic numbers without python-magic."""
    if len(file_bytes) < 4:
        return "application/octet-stream"

    # PDF: %PDF
    if file_bytes[:4] == b'%PDF':
        return "application/pdf"

    # JPEG: FF D8 FF
    if file_bytes[:3] == b'\xff\xd8\xff':
        return "image/jpeg"

    # PNG: 89 50 4E 47
    if file_bytes[:4] == b'\x89PNG':
        return "image/png"

    # WebP: RIFF....WEBP
    if file_bytes[:4] == b'RIFF' and len(file_bytes) >= 12 and file_bytes[8:12] == b'WEBP':
        return "image/webp"

    return "application/octet-stream"


def validate_pdf_file(file_bytes: bytes) -> None:
    """Validate that file is a PDF by MIME type."""
    validate_file_size(file_bytes, "resume")
    
    mime_type = detect_mime_type(file_bytes)
    if mime_type not in ALLOWED_PDF_MIMES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Expected PDF, got {mime_type}",
        )


def validate_image_file(file_bytes: bytes) -> None:
    """Validate that file is an allowed image by MIME type."""
    validate_file_size(file_bytes, "avatar")
    
    mime_type = detect_mime_type(file_bytes)
    if mime_type not in ALLOWED_IMAGE_MIMES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Expected image (JPEG/PNG/WebP), got {mime_type}",
        )
