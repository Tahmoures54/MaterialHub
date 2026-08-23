"""Shared utility helpers for MaterialHub."""

from functools import wraps
from flask import flash, redirect, url_for
from flask_login import current_user
from models import AccessLevel


def role_required(*roles):
    """
    Decorator to restrict access to specific AccessLevel values.

    Usage:
        @role_required(AccessLevel.purchase, AccessLevel.project_manager)
        def some_view():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Please log in to access this page.', 'warning')
                return redirect(url_for('auth.login'))

            if current_user.is_admin:
                return f(*args, **kwargs)

            if current_user.access_level not in roles:
                flash('You do not have permission to access this page.', 'danger')
                return redirect(url_for('index'))

            return f(*args, **kwargs)
        return decorated_function
    return decorator


def generate_document_number(prefix: str, last_number: int = 0) -> str:
    """
    Generate sequential document numbers like MR-0001, PO-0001, etc.

    Args:
        prefix: Document prefix (e.g. 'MR', 'PO', 'DLV', 'WH')
        last_number: The last used numeric part (default 0)

    Returns:
        Formatted document number string
    """
    next_num = last_number + 1
    return f"{prefix}-{next_num:04d}"
