import os
from pathlib import Path
from dotenv import load_dotenv

# Base directory of the application
basedir = Path(__file__).resolve().parent

# Load environment variables from .env file if it exists
load_dotenv(basedir / '.env')


class Config:
    """Base application configuration."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'miracle-hostel-dev-secret-key-change-in-production')
    
    # Database Configuration
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        f"sqlite:///{basedir / 'miracle_hostel_dev.db'}"
    )
    if SQLALCHEMY_DATABASE_URI and SQLALCHEMY_DATABASE_URI.startswith("postgres://"):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace("postgres://", "postgresql://", 1)

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
    }

    # Storage settings
    # Resident photographs are kept in private storage outside app/static/
    # to prevent direct or public web exposure.
    PRIVATE_STORAGE_FOLDER = basedir / 'storage' / 'private' / 'residents'
    STORAGE_BACKEND = os.environ.get('STORAGE_BACKEND', 'local_private')  # 'local_private' or 's3'
    S3_BUCKET_NAME = os.environ.get('S3_BUCKET_NAME', '')
    S3_REGION = os.environ.get('S3_REGION', 'ap-south-1')
    S3_ENDPOINT_URL = os.environ.get('S3_ENDPOINT_URL', None)
    AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID', '')
    AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY', '')

    UPLOAD_FOLDER = basedir / 'app' / 'static' / 'uploads'
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB max upload size
    ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
    ALLOWED_IMAGE_MIMETYPES = {'image/jpeg', 'image/png', 'image/webp'}

    # Security & Encryption keys
    AADHAAR_ENCRYPTION_KEY = os.environ.get(
        'AADHAAR_ENCRYPTION_KEY',
        'miracle-secret-aadhaar-key-32-chars!!'
    )

    # CSRF Protection
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600  # 1 hour validity

    # Session & Cookie Security:
    # SESSION_PERMANENT = False ensures the cookie has no Expires/Max-Age timestamp.
    # The browser automatically discards the session cookie when the browser/website is closed.
    SESSION_PERMANENT = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'false').lower() in ('true', '1')

    # Rate Limiting Configuration
    LOGIN_RATE_LIMIT_ATTEMPTS = int(os.environ.get('LOGIN_RATE_LIMIT_ATTEMPTS', 5))
    LOGIN_RATE_LIMIT_WINDOW_MINUTES = int(os.environ.get('LOGIN_RATE_LIMIT_WINDOW_MINUTES', 15))

    # Password Reset Token Settings
    PASSWORD_RESET_TOKEN_EXPIRE_HOURS = int(os.environ.get('PASSWORD_RESET_TOKEN_EXPIRE_HOURS', 1))

    # Business Rules & Admin Defaults
    RESIDENT_RETENTION_DAYS = int(os.environ.get('RESIDENT_RETENTION_DAYS', 30))
    APP_NAME = "Miracle Hostel"
    ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
    ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'admin@123')


class DevelopmentConfig(Config):
    """Development configuration with debugging enabled."""
    DEBUG = True
    ENV = 'development'


class ProductionConfig(Config):
    """Production configuration with strict security defaults."""
    DEBUG = False
    ENV = 'production'
    SESSION_COOKIE_SECURE = True
    if not os.environ.get('SECRET_KEY'):
        SECRET_KEY = 'must-set-random-secret-key-in-production'


class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    SESSION_PERMANENT = False
    LOGIN_RATE_LIMIT_ATTEMPTS = 5
    LOGIN_RATE_LIMIT_WINDOW_MINUTES = 15


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
