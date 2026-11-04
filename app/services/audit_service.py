"""
Audit service for tracking administrative operations across Miracle Hostel.
Enforces that no sensitive credentials or tokens are ever logged.
"""
from flask import request, has_request_context
from flask_login import current_user
from app.extensions import db
from app.models.audit_log import AuditLog


class AuditService:
    """Central service for logging administrative actions to PostgreSQL."""

    @staticmethod
    def get_client_ip() -> str:
        """Extract the client IP address considering proxy forwarding headers."""
        if not has_request_context():
            return "127.0.0.1"
        x_forwarded_for = request.headers.get('X-Forwarded-For')
        if x_forwarded_for:
            # First IP in the comma-separated chain
            return x_forwarded_for.split(',')[0].strip()
        return request.remote_addr or "127.0.0.1"

    @classmethod
    def log(
        cls,
        action: str,
        entity_type: str,
        entity_id: int = None,
        description: str = "",
        admin_id: int = None,
        ip_address: str = None
    ) -> AuditLog:
        """
        Record an administrative audit log entry.
        Automatically attaches admin_id from current_user if not explicitly passed.
        Enforces sanitization against passwords and tokens.
        """
        if admin_id is None and has_request_context():
            if current_user and current_user.is_authenticated:
                admin_id = current_user.id

        if ip_address is None:
            ip_address = cls.get_client_ip()

        # Sanitize description
        safe_description = AuditLog.sanitize_description(description)

        entry = AuditLog(
            admin_id=admin_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            description=safe_description,
            ip_address=ip_address
        )

        db.session.add(entry)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

        return entry

