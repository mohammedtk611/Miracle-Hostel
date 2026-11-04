"""
AuditLog model for tracking administrative changes and security events.
Strictly prohibits storing plaintext passwords, password hashes, or reset tokens.
"""
import re
from datetime import datetime
from app.extensions import db


class AuditAction:
    LOGIN = 'LOGIN'
    LOGOUT = 'LOGOUT'
    PASSWORD_CHANGE = 'PASSWORD_CHANGE'
    PASSWORD_RESET_REQUEST = 'PASSWORD_RESET_REQUEST'
    PASSWORD_RESET_SUCCESS = 'PASSWORD_RESET_SUCCESS'
    
    BRANCH_CREATE = 'BRANCH_CREATE'
    BRANCH_UPDATE = 'BRANCH_UPDATE'
    BRANCH_DEACTIVATE = 'BRANCH_DEACTIVATE'
    BRANCH_ACTIVATE = 'BRANCH_ACTIVATE'

    RESIDENT_CREATE = 'RESIDENT_CREATE'
    RESIDENT_UPDATE = 'RESIDENT_UPDATE'
    RESIDENT_DEPARTURE = 'RESIDENT_DEPARTURE'
    RESIDENT_REACTIVATE = 'RESIDENT_REACTIVATE'
    RESIDENT_DELETE = 'RESIDENT_DELETE'

    PAYMENT_CREATE = 'PAYMENT_CREATE'
    PAYMENT_UPDATE = 'PAYMENT_UPDATE'


class AuditLog(db.Model):
    """
    AuditLog model.
    Records administrative actions across system entities.
    Enforces that sensitive credentials and tokens are scrubbed from log descriptions.
    """
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(
        db.Integer,
        db.ForeignKey('admins.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )
    action = db.Column(db.String(50), nullable=False, index=True)
    entity_type = db.Column(db.String(50), nullable=False, index=True)
    entity_id = db.Column(db.Integer, nullable=True)
    description = db.Column(db.Text, nullable=False)
    ip_address = db.Column(db.String(45), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    admin = db.relationship('Admin', back_populates='audit_logs')

    @classmethod
    def sanitize_description(cls, text: str) -> str:
        """
        Sanitize log descriptions to ensure no passwords, hashes,
        or reset tokens are inadvertently recorded.
        """
        if not text:
            return ""
        # Scrub potential token or password patterns
        sanitized = re.sub(r'(?i)(password|passwd|hash|token)\s*[:=]\s*[^\s,;]+', r'\1=[REDACTED]', text)
        return sanitized

    def to_dict(self):
        return {
            'id': self.id,
            'admin_id': self.admin_id,
            'admin_username': self.admin.username if self.admin else 'System',
            'action': self.action,
            'entity_type': self.entity_type,
            'entity_id': self.entity_id,
            'description': self.description,
            'ip_address': self.ip_address,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }

    def __repr__(self):
        return f"<AuditLog action='{self.action}' entity='{self.entity_type}:{self.entity_id}' at='{self.created_at}'>"
