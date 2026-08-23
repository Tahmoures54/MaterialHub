import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Base configuration."""
    SECRET_KEY = os.getenv('SECRET_KEY')
    if not SECRET_KEY:
        raise ValueError("SECRET_KEY environment variable is not set. Please set it in .env file.")

    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    INSTANCE_DIR = os.path.join(BASE_DIR, 'instance')
    os.makedirs(INSTANCE_DIR, exist_ok=True)

    # Database: prefer PostgreSQL if DATABASE_URL is set, otherwise SQLite for local dev
    DATABASE_URL = os.getenv('DATABASE_URL')
    if DATABASE_URL:
        # Handle Heroku-style postgres:// -> postgresql://
        if DATABASE_URL.startswith('postgres://'):
            DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
        SQLALCHEMY_DATABASE_URI = DATABASE_URL
    else:
        SQLALCHEMY_DATABASE_URI = f'sqlite:///{os.path.join(INSTANCE_DIR, "materialhub.db")}'

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }

    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10MB upload limit
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600

    # Session security
    SESSION_COOKIE_SECURE = os.getenv('FLASK_ENV') == 'production'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True


config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
