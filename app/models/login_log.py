"""
LoginLog model for tracking authentication attempts and enforcing rate limiting.
"""
from datetime import datetime
from app.extensions import db


class LoginStatus:
    SUCCESS = 'SUCCESS'
    FAILED = 'FAILED'
    RATE_LIMITED = 'RATE_LIMITED'
    CHOICES = [SUCCESS, FAILED, RATE_LIMITED]


class LoginLog(db.Model):
    """
    LoginLog model.
    Records every administrative authentication attempt for security audits
    and sliding-window rate limiting.
    """
    __tablename__ = 'login_logs'

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(
        db.Integer,
        db.ForeignKey('admins.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )
    email_attempted = db.Column(db.String(120), nullable=True, index=True)
    ip_address = db.Column(db.String(45), nullable=False, index=True)
    user_agent = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(20), nullable=False, index=True)  # SUCCESS, FAILED, RATE_LIMITED
    failure_reason = db.Column(db.String(150), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    admin = db.relationship('Admin', back_populates='login_logs')

    def to_dict(self):
        return {
            'id': self.id,
            'admin_id': self.admin_id,
            'email_attempted': self.email_attempted,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'status': self.status,
            'failure_reason': self.failure_reason,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }

    def __repr__(self):
        return f"<LoginLog ip='{self.ip_address}' status='{self.status}' at='{self.created_at}'>"

