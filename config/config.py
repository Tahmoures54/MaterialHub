import os
import secrets
import urllib.parse as _up

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def _is_serverless():
    """تشخیص اجرا روی Vercel / AWS Lambda و محیط‌های serverless مشابه."""
    return bool(
        os.getenv('VERCEL')
        or os.getenv('VERCEL_ENV')
        or os.getenv('AWS_LAMBDA_FUNCTION_NAME')
    )


def _get_instance_dir():
    """
    مسیر پوشه instance:
    - اگر INSTANCE_DIR تنظیم شده باشد، از همان استفاده می‌شود.
    - روی Vercel/Lambda فقط /tmp قابل نوشتن است.
    - در لوکال، پوشه instance کنار پروژه ساخته می‌شود.
    """
    custom_dir = os.getenv('INSTANCE_DIR')
    if custom_dir:
        return os.path.abspath(custom_dir)

    if _is_serverless():
        return '/tmp/instance'

    return os.path.join(BASE_DIR, 'instance')


def _get_bool_env(name, default=False):
    """تبدیل متغیر محیطی رشته‌ای به boolean."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in ('1', 'true', 'yes', 'on')


def _normalize_database_url(url):
    """
    نرمال‌سازی URL دیتابیس:
    - postgres://  -> postgresql://
    - حذف channel_binding که با بعضی درایورها سازگار نیست.
    """
    if not url:
        return url

    if url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql://', 1)

    if 'channel_binding=' in url:
        parsed = _up.urlparse(url)
        query = _up.parse_qs(parsed.query)
        query.pop('channel_binding', None)
        new_query = _up.urlencode(query, doseq=True)
        parsed = parsed._replace(query=new_query)
        url = _up.urlunparse(parsed)

    return url


def _get_database_url():
    """
    ترتیب اولویت برای پیدا کردن آدرس دیتابیس:
    1. DATABASE_URL
    2. material_DATABASE_URL   (Neon با Custom Prefix)
    3. POSTGRES_URL
    4. material_POSTGRES_URL
    5. POSTGRES_PRISMA_URL
    """
    return (
        os.getenv('DATABASE_URL')
        or os.getenv('material_DATABASE_URL')
        or os.getenv('POSTGRES_URL')
        or os.getenv('material_POSTGRES_URL')
        or os.getenv('POSTGRES_PRISMA_URL')
    )


# ---------------------------------------------------------------------------
# Base Config
# ---------------------------------------------------------------------------

class Config:
    """Base configuration."""

    # Flask environment
    FLASK_ENV = os.getenv('FLASK_ENV', 'development')
    IS_PRODUCTION = (
        FLASK_ENV.lower() == 'production'
        or os.getenv('VERCEL_ENV') == 'production'
    )

    # Secret key
    SECRET_KEY = os.getenv('SECRET_KEY')
    if not SECRET_KEY:
        if IS_PRODUCTION:
            raise ValueError(
                "SECRET_KEY environment variable is not set. "
                "Please set it in Vercel Environment Variables or .env file."
            )
        SECRET_KEY = secrets.token_urlsafe(48)

    # Paths
    BASE_DIR = BASE_DIR
    INSTANCE_DIR = _get_instance_dir()
    os.makedirs(INSTANCE_DIR, exist_ok=True)

    # Database
    DATABASE_URL = _normalize_database_url(_get_database_url())
    if DATABASE_URL:
        SQLALCHEMY_DATABASE_URI = DATABASE_URL
    else:
        # فقط برای توسعه محلی یا fallback موقت.
        # روی Vercel داده‌ها در /tmp موقتی هستند.
        SQLALCHEMY_DATABASE_URI = (
            f'sqlite:///{os.path.join(INSTANCE_DIR, "materialhub.db")}'
        )

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }

    # Misc
    MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', 10 * 1024 * 1024))
    JSON_SORT_KEYS = False
    PREFERRED_URL_SCHEME = os.getenv(
        'PREFERRED_URL_SCHEME',
        'https' if IS_PRODUCTION else 'http'
    )

    # CSRF
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600
    WTF_CSRF_CHECK_DEFAULT = True

    # Session / cookies
    SESSION_COOKIE_SECURE = _get_bool_env(
        'SESSION_COOKIE_SECURE',
        IS_PRODUCTION
    )
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = os.getenv('SESSION_COOKIE_SAMESITE', 'Lax')
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE

    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    SQLALCHEMY_ECHO = False


# ---------------------------------------------------------------------------
# Environment-specific configs
# ---------------------------------------------------------------------------

class DevelopmentConfig(Config):
    DEBUG = True
    SESSION_COOKIE_SECURE = False


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True


class TestingConfig(Config):
    TESTING = True
    DEBUG = True
    WTF_CSRF_ENABLED = False
    SECRET_KEY = 'materialhub-test-secret'
    SQLALCHEMY_DATABASE_URI = (
        'sqlite:///' + os.path.join(Config.INSTANCE_DIR, 'test.db')
    )
    SESSION_COOKIE_SECURE = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
    }


config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig,
}
