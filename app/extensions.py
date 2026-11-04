"""
Flask extensions initialization module.
"""
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect

# Initialize SQLAlchemy instance
db = SQLAlchemy()

# Initialize Flask-Login manager
login_manager = LoginManager()

# Initialize CSRF protection
csrf = CSRFProtect()
