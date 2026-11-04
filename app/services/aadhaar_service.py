"""
Aadhaar security service.
Handles validation, encryption at rest using cryptography/AES, and safe display masking.
Ensures full Aadhaar numbers are never displayed in normal UI views or stored in plaintext.
"""
import base64
import os
import re
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from flask import current_app


class AadhaarSecurityService:
    """Service for securing and managing sensitive Aadhaar identification data."""

    @staticmethod
    def _get_key() -> bytes:
        """Derive or load a 256-bit encryption key from application configuration."""
        key_str = current_app.config.get('AADHAAR_ENCRYPTION_KEY', 'miracle-default-dev-key-32-bytes!!')
        # Ensure 32 bytes (256-bit)
        key_bytes = key_str.encode('utf-8')
        if len(key_bytes) < 32:
            key_bytes = key_bytes.ljust(32, b'#')
        else:
            key_bytes = key_bytes[:32]
        return key_bytes

    @classmethod
    def validate_format(cls, aadhaar_number: str) -> bool:
        """
        Validate standard 12-digit Indian Aadhaar format.
        Must consist of 12 digits, cannot start with 0 or 1.
        """
        if not aadhaar_number:
            return False
        clean = re.sub(r'[\s\-]', '', aadhaar_number)
        if len(clean) != 12 or not clean.isdigit():
            return False
        if clean[0] in ('0', '1'):
            return False
        return True

    @classmethod
    def extract_last_four(cls, aadhaar_number: str) -> str:
        """Extract only the last 4 digits for indexing and UI display."""
        clean = re.sub(r'[\s\-]', '', aadhaar_number)
        return clean[-4:] if len(clean) >= 4 else "0000"

    @classmethod
    def encrypt_aadhaar(cls, aadhaar_number: str) -> str:
        """
        Encrypt a 12-digit Aadhaar number using AES-GCM (Authenticated Encryption).
        Returns URL-safe base64 encoded ciphertext.
        """
        clean = re.sub(r'[\s\-]', '', aadhaar_number)
        key = cls._get_key()
        aesgcm = AESGCM(key)
        nonce = os.urandom(12)  # Standard 96-bit nonce for AES-GCM
        encrypted_data = aesgcm.encrypt(nonce, clean.encode('utf-8'), None)
        # Combine nonce and ciphertext
        payload = nonce + encrypted_data
        return base64.urlsafe_b64encode(payload).decode('utf-8')

    @classmethod
    def decrypt_aadhaar(cls, encrypted_str: str) -> str:
        """
        Decrypt encrypted Aadhaar ciphertext back to plaintext.
        Intended strictly for authorized admin verification workflows.
        """
        try:
            payload = base64.urlsafe_b64decode(encrypted_str.encode('utf-8'))
            nonce = payload[:12]
            ciphertext = payload[12:]
            key = cls._get_key()
            aesgcm = AESGCM(key)
            decrypted_bytes = aesgcm.decrypt(nonce, ciphertext, None)
            return decrypted_bytes.decode('utf-8')
        except Exception:
            return "DECRYPTION_ERROR"

    @classmethod
    def mask_aadhaar(cls, last_four: str) -> str:
        """Format masked presentation string for safe UI tables and profiles."""
        return f"XXXX-XXXX-{last_four}"

