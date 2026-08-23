"""WSGI entry point for production servers (Gunicorn, uWSGI, etc.)."""
from app import create_app

app = create_app()
