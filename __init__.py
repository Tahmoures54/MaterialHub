try:
    from .app import app
except ImportError:
    from app import app

__all__ = ['app']
