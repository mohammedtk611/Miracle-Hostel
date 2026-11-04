"""
Application routes package.
"""
from app.routes.auth import auth_bp
from app.routes.dashboard import dashboard_bp
from app.routes.residents import residents_bp
from app.routes.payments import payments_bp
from app.routes.branches import branches_bp
from app.routes.settings import settings_bp

__all__ = [
    'auth_bp',
    'dashboard_bp',
    'residents_bp',
    'payments_bp',
    'branches_bp',
    'settings_bp',
]

