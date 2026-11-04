"""
Miracle Hostel Flask Application Factory.
Integrated with Flask-Login, Flask-WTF CSRF protection, and security headers.
"""
import os
from datetime import datetime
from flask import Flask, redirect, url_for, render_template, flash, request
from flask_wtf.csrf import CSRFError
from config import config
from app.extensions import db, login_manager, csrf
from app.utils.helpers import format_currency, format_date, calculate_retention_info


def create_app(config_name=None):
    """Factory function to configure and initialize the Flask application."""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    app = Flask(__name__)
    config_cls = config.get(config_name, config['default'])
    
    # In production, enforce strict security configuration validation
    if config_name == 'production' or getattr(config_cls, 'ENV', '') == 'production':
        if hasattr(config_cls, 'validate_production'):
            config_cls.validate_production()

    app.config.from_object(config_cls)

    # Initialize extensions
    db.init_app(app)
    csrf.init_app(app)

    # Initialize Flask-Login
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = "Please sign in with administrator credentials to access this page."
    login_manager.login_message_category = "warning"
    login_manager.session_protection = "strong"

    from app.models.admin import Admin

    @login_manager.user_loader
    def load_user(user_id):
        """Flask-Login user loader."""
        try:
            return db.session.get(Admin, int(user_id))
        except (ValueError, TypeError):
            return None

    # Register custom Jinja template filters
    app.jinja_env.filters['currency'] = format_currency
    app.jinja_env.filters['format_date'] = format_date

    # Register global template context processors
    @app.context_processor
    def inject_global_context():
        """Provide global variables accessible across all Jinja templates."""
        try:
            from app.models.branch import Branch
            branches = Branch.query.filter_by(is_active=True).order_by(Branch.branch_name.asc()).all()
        except Exception:
            branches = []

        return {
            'app_name': app.config.get('APP_NAME', 'Miracle Hostel'),
            'current_year': datetime.now().year,
            'header_active_branches': branches,
            'retention_policy_days': app.config.get('RESIDENT_RETENTION_DAYS', 30)
        }

    # Security Headers Response Hook
    @app.after_request
    def set_security_headers(response):
        """Enforce standard HTTP security headers across all responses."""
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        if not app.debug:
            # Enforce HSTS in production
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        return response

    # CSRF Error Handler
    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        flash("CSRF security token validation failed or expired. Please try again.", "danger")
        return render_template('auth/csrf_error.html', reason=e.description), 400

    # Custom 404 Not Found Handler
    @app.errorhandler(404)
    def handle_not_found(e):
        return render_template('errors/404.html'), 404

    # Custom 500 Internal Server Error Handler (Protects against stack trace leaks)
    @app.errorhandler(500)
    def handle_server_error(e):
        db.session.rollback()
        return render_template('errors/500.html'), 500

    # Register Blueprints
    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.residents import residents_bp
    from app.routes.payments import payments_bp
    from app.routes.branches import branches_bp
    from app.routes.settings import settings_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(residents_bp)
    app.register_blueprint(payments_bp)
    app.register_blueprint(branches_bp)
    app.register_blueprint(settings_bp)

    # Global convenience route for /login
    @app.route('/login')
    def login_redirect():
        return redirect(url_for('auth.login'))

    # Register custom CLI commands
    from app.cli import register_cli_commands
    register_cli_commands(app)

    return app


if __name__ == '__main__':
    import sys
    _root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if _root not in sys.path:
        sys.path.insert(0, _root)
    from run import run_server
    run_server()
