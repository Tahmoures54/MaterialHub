import os

def production_config():
    return {
        "SECRET_KEY": os.environ.get("SECRET_KEY"),
        "SQLALCHEMY_DATABASE_URI": os.environ.get("DATABASE_URL"),
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "SESSION_COOKIE_SECURE": os.environ.get("SESSION_COOKIE_SECURE","true").lower() == "true",
        "SESSION_COOKIE_HTTPONLY": os.environ.get("SESSION_COOKIE_HTTPONLY","true").lower() == "true",
        "SESSION_COOKIE_SAMESITE": os.environ.get("SESSION_COOKIE_SAMESITE","Lax"),
    }
