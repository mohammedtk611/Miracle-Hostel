"""
Admin model representing the single administrator account.
Integrated with Flask-Login UserMixin and Argon2id cryptographic hashing.
"""
from datetime import datetime
import argon2
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
from flask_login import UserMixin
from app.extensions import db

# Argon2id password hasher instance
_argon2id_hasher = argon2.PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    type=argon2.Type.ID
)


class Admin(UserMixin, db.Model):
    """
    Administrator model.
    System architecture supports strictly ONE administrator account.
    Uses Argon2id for password hashing and Flask-Login for session management.
    """
    __tablename__ = 'admins'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_login = db.Column(db.DateTime, nullable=True)
    last_login_ip = db.Column(db.String(45), nullable=True)

    # Relationships
    audit_logs = db.relationship('AuditLog', back_populates='admin', lazy='dynamic')
    login_logs = db.relationship('LoginLog', back_populates='admin', lazy='dynamic')
    reset_tokens = db.relationship('PasswordResetToken', back_populates='admin', cascade='all, delete-orphan', lazy='dynamic')

    def set_password(self, password: str) -> None:
        """Hash and store password securely using Argon2id."""
        self.password_hash = _argon2id_hasher.hash(password)

    def check_password(self, password: str) -> bool:
        """
        Verify password against stored cryptographic hash.
        Supports Argon2id natively with automatic legacy upgrade path.
        """
        if not self.password_hash:
            return False

        if self.password_hash.startswith('$argon2'):
            try:
                return _argon2id_hasher.verify(self.password_hash, password)
            except (VerifyMismatchError, VerificationError, InvalidHashError):
                return False

        # Graceful fallback for legacy hashes with automatic upgrade to Argon2id
        from werkzeug.security import check_password_hash
        try:
            if check_password_hash(self.password_hash, password):
                # Upgrade hash to Argon2id
                self.set_password(password)
                try:
                    db.session.commit()
                except Exception:
                    db.session.rollback()
                return True
        except Exception:
            pass

        return False

    def to_dict(self):
        """Serialize admin data safely (excluding password hash)."""
        return {
            'id': self.id,
            'email': self.email,
            'username': self.username,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'last_login_ip': self.last_login_ip
        }

    def __repr__(self):
        return f"<Admin email='{self.email}' username='{self.username}'>"
