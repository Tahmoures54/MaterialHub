from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

db = SQLAlchemy()
# Tables may be re-registered when a model module is re-executed (e.g. under
# coverage.py, which re-imports source modules while resolving its matchers).
# `extend_existing=True` on the declarative base makes every model class
# (that does not override `__table_args__`) merge into the existing Table
# instead of raising "Table ... is already defined".
db.Model.__table_args__ = {"extend_existing": True}  # type: ignore[attr-defined]
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()
limiter = Limiter(get_remote_address)

login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'warning'
