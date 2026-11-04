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

    # Connection pooling configured for PostgreSQL (Supabase / Render)
    # Using pool_pre_ping for stale connection resilience and pool_recycle for firewall timeouts
    if SQLALCHEMY_DATABASE_URI and not SQLALCHEMY_DATABASE_URI.startswith("sqlite"):
        SQLALCHEMY_ENGINE_OPTIONS = {
            'pool_pre_ping': True,
            'pool_recycle': 300,
            'pool_size': int(os.environ.get('DB_POOL_SIZE', 10)),
            'max_overflow': int(os.environ.get('DB_MAX_OVERFLOW', 20)),
            'pool_timeout': 30,
        }
    else:
        SQLALCHEMY_ENGINE_OPTIONS = {
            'pool_pre_ping': True,
        }

    # Storage settings
    # Resident photographs are kept in private storage outside app/static/
    # to prevent direct or public web exposure.
    PRIVATE_STORAGE_FOLDER = basedir / 'storage' / 'private' / 'residents'
    STORAGE_BACKEND = os.environ.get('STORAGE_BACKEND', 'local_private').lower()  # 'local_private', 'google_drive', or 's3'

    # Google Drive Storage Integration (OAuth 2.0 with Dedicated Google Account)
    GOOGLE_DRIVE_CLIENT_ID = os.environ.get('GOOGLE_DRIVE_CLIENT_ID', '')
    GOOGLE_DRIVE_CLIENT_SECRET = os.environ.get('GOOGLE_DRIVE_CLIENT_SECRET', '')
    GOOGLE_DRIVE_REFRESH_TOKEN = os.environ.get('GOOGLE_DRIVE_REFRESH_TOKEN', '')
    GOOGLE_DRIVE_FOLDER_ID = os.environ.get('GOOGLE_DRIVE_FOLDER_ID', '')

    # S3 Object Storage (Alternative)
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
    SECRET_KEY = os.environ.get('SECRET_KEY', '')

    @classmethod
    def validate_production(cls):
        """Validate critical production security variables."""
        secret_key = os.environ.get('SECRET_KEY')
        if not secret_key or secret_key == 'miracle-hostel-dev-secret-key-change-in-production':
            raise ValueError(
                "SECRET_KEY must be set to a cryptographically secure random value in production. "
                "Do not use default or empty keys."
            )

        db_url = os.environ.get('DATABASE_URL')
        if not db_url:
            raise ValueError(
                "DATABASE_URL is required in production. "
                "Provide a valid Supabase/PostgreSQL connection string."
            )
        if db_url.startswith('sqlite'):
            raise ValueError(
                "SQLite is not permitted in production. "
                "Please configure a PostgreSQL connection string in DATABASE_URL."
            )

        aadhaar_key = os.environ.get('AADHAAR_ENCRYPTION_KEY', '')
        if not aadhaar_key or aadhaar_key == 'miracle-secret-aadhaar-key-32-chars!!':
            raise ValueError(
                "AADHAAR_ENCRYPTION_KEY must be explicitly set to a custom 32-byte secret in production. "
                "Do not use default keys."
            )
        if len(aadhaar_key.encode('utf-8')) != 32:
            raise ValueError(
                f"AADHAAR_ENCRYPTION_KEY must be exactly 32 bytes (256 bits). Current length: {len(aadhaar_key.encode('utf-8'))} bytes."
            )


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
