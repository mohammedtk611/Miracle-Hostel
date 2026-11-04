"""
File upload validation and security utilities.
Enforces extension whitelisting, file size constraints, and MIME type magic-byte inspection.
"""
import os
import uuid
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


def get_file_extension(filename: str) -> str:
    """Extract lowercase file extension."""
    if '.' in filename:
        return filename.rsplit('.', 1)[1].lower()
    return ''


def verify_image_magic_bytes(header_bytes: bytes) -> str | None:
    """
    Inspect magic byte signatures of binary header to verify actual image MIME type.
    Returns MIME type string or None if unrecognized.
    """
    if len(header_bytes) < 12:
        return None

    # JPEG signature: FF D8 FF
    if header_bytes.startswith(b'\xff\xd8\xff'):
        return 'image/jpeg'

    # PNG signature: 89 50 4E 47 0D 0A 1A 0A
    if header_bytes.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image/png'

    # WEBP signature: RIFF....WEBP
    if header_bytes.startswith(b'RIFF') and header_bytes[8:12] == b'WEBP':
        return 'image/webp'

    return None


def validate_image_upload(file: FileStorage, max_size: int = MAX_FILE_SIZE) -> tuple[bool, str]:
    """
    Validate uploaded image by extension, size, and binary magic bytes.
    Returns: (is_valid: bool, error_message: str)
    """
    if not file or not file.filename:
        return False, "No file was selected for upload."

    # 1. Extension Check
    ext = get_file_extension(file.filename)
    if ext not in ALLOWED_EXTENSIONS:
        return False, f"File extension '.{ext}' is not permitted. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}."

    # 2. Size Check
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)  # Reset pointer

    if size > max_size:
        return False, f"File size ({size / (1024 * 1024):.1f}MB) exceeds maximum permitted limit (5MB)."

    if size == 0:
        return False, "Uploaded file is empty (0 bytes)."

    # 3. Magic Byte & MIME Inspection
    header = file.read(64)
    file.seek(0)  # Reset pointer for subsequent processing

    detected_mime = verify_image_magic_bytes(header)
    if not detected_mime:
        return False, "File failed binary content inspection. File contents do not match a valid image format."

    return True, ""


def save_secure_image(file: FileStorage, upload_dir: str, prefix: str = "img") -> str:
    """
    Safely save an uploaded image file with a unique non-predictable filename.
    Returns relative URL path suitable for web serving.
    """
    os.makedirs(upload_dir, exist_ok=True)
    ext = get_file_extension(file.filename)
    unique_name = f"{prefix}_{uuid.uuid4().hex[:16]}.{ext}"
    safe_name = secure_filename(unique_name)
    destination_path = os.path.join(upload_dir, safe_name)

    file.seek(0)
    file.save(destination_path)

    return f"/static/uploads/{safe_name}"

