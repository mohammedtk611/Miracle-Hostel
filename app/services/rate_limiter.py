"""
Rate limiting service for administrator authentication.
Leverages the LoginLog database table to enforce sliding-window attempt restrictions.
"""
from datetime import datetime, timedelta
from flask import current_app
from app.extensions import db
from app.models.login_log import LoginLog, LoginStatus


class LoginRateLimiter:
    """Database-backed sliding-window rate limiter for administrative login."""

    @classmethod
    def get_config(cls):
        """Retrieve rate limit threshold and window from current app config."""
        max_attempts = current_app.config.get('LOGIN_RATE_LIMIT_ATTEMPTS', 5)
        window_minutes = current_app.config.get('LOGIN_RATE_LIMIT_WINDOW_MINUTES', 15)
        return max_attempts, window_minutes

    @classmethod
    def is_rate_limited(cls, ip_address: str, email: str) -> tuple[bool, int]:
        """
        Check if an IP address or email has exceeded the maximum allowed failed attempts.
        Returns: (is_limited: bool, remaining_lockout_seconds: int)
        """
        max_attempts, window_minutes = cls.get_config()
        cutoff_time = datetime.utcnow() - timedelta(minutes=window_minutes)

        # Count recent failed attempts from this IP or for this specific email
        recent_failures = LoginLog.query.filter(
            (LoginLog.ip_address == ip_address) | (LoginLog.email_attempted == email),
            LoginLog.status == LoginStatus.FAILED,
            LoginLog.created_at >= cutoff_time
        ).order_by(LoginLog.created_at.desc()).all()

        if len(recent_failures) >= max_attempts:
            # Calculate remaining lockout time based on newest failure
            newest_failure = recent_failures[0]
            elapsed = (datetime.utcnow() - newest_failure.created_at).total_seconds()
            lockout_total = window_minutes * 60
            remaining = max(0, int(lockout_total - elapsed))
            return True, remaining

        return False, 0

    @classmethod
    def record_attempt(
        cls,
        ip_address: str,
        email: str,
        status: str,
        failure_reason: str = None,
        admin_id: int = None,
        user_agent: str = None
    ) -> LoginLog:
        """Record an authentication event into LoginLog."""
        log = LoginLog(
            admin_id=admin_id,
            email_attempted=email,
            ip_address=ip_address,
            user_agent=user_agent[:250] if user_agent else None,
            status=status,
            failure_reason=failure_reason
        )
        db.session.add(log)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
        return log

