import logging
from flask import render_template

logger = logging.getLogger(__name__)


def page_not_found(error):
    """404 handler."""
    logger.warning(f"404 Not Found: {error}")
    return render_template('404.html'), 404


def internal_server_error(error):
    """500 handler."""
    logger.error(f"500 Internal Server Error: {error}")
    return render_template('500.html'), 500


def forbidden(error):
    """403 handler."""
    logger.warning(f"403 Forbidden: {error}")
    return render_template('404.html'), 403  # reuse 404 template for now
