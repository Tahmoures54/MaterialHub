import logging
from flask import render_template

logger = logging.getLogger(__name__)

def register_error_handlers(app):
    @app.errorhandler(404)
    def page_not_found(error):
        logger.error(f"Not found error: {str(error)}")
        return render_template('404.html'), 404

    @app.errorhandler(500)
    def server_error(error):
        logger.error(f"Server error: {str(error)}")
        return render_template('500.html'), 500