"""
PasswordResetToken model for secure administrative password recovery.
"""
import hashlib
import secrets
from datetime import datetime, timedelta
from app.extensions import db


class PasswordResetToken(db.Model):
    """
    PasswordResetToken model.
    Stores cryptographically hashed, one-time, time-limited tokens for administrator password recovery.
    Raw tokens are never persisted in the database.
    """
    __tablename__ = 'password_reset_tokens'

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(
        db.Integer,
        db.ForeignKey('admins.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    token_hash = db.Column(db.String(128), unique=True, nullable=False, index=True)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    used = db.Column(db.Boolean, default=False, nullable=False, index=True)
    ip_address = db.Column(db.String(45), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    admin = db.relationship('Admin', back_populates='reset_tokens')

    @staticmethod
    def hash_token(raw_token: str) -> str:
        """Produce a SHA-256 hex digest of the raw recovery token."""
        return hashlib.sha256(raw_token.encode('utf-8')).hexdigest()

    @classmethod
    def create_for_admin(cls, admin_id: int, ip_address: str = None, hours_valid: int = 1):
        """
        Generate a cryptographically random token, compute its hash,
        and construct an uncommitted instance with expiration.
        Returns tuple: (instance, raw_token)
        """
        raw_token = secrets.token_urlsafe(32)
        token_hash = cls.hash_token(raw_token)
        expires_at = datetime.utcnow() + timedelta(hours=hours_valid)

        instance = cls(
            admin_id=admin_id,
            token_hash=token_hash,
            expires_at=expires_at,
            used=False,
            ip_address=ip_address
        )
        return instance, raw_token

    def is_valid(self) -> bool:
        """Check if the token is unused and has not expired."""
        return (not self.used) and (datetime.utcnow() <= self.expires_at)

    def mark_used(self) -> None:
        """Invalidate the token upon successful password update."""
        self.used = True

    def __repr__(self):
        return f"<PasswordResetToken admin_id={self.admin_id} valid={self.is_valid()}>"

