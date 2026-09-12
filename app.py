import logging
import os
import sys
import importlib.util
from flask import Flask, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from logging.handlers import RotatingFileHandler
from extensions import db, migrate, login_manager, csrf
from config.config import config_by_name
from data.country_codes import COUNTRY_NAMES_BY_CODE


def _load_sidecar(module_name, filename):
    """Load modules from the app/ directory without colliding with this app.py module."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app', filename)
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module



def create_app(config_name=None):
    """Application factory."""
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'development')

    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_by_name.get(config_name, config_by_name['default']))

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    @app.before_request
    def _csrf_token_from_json():
        if request.method in ('POST', 'PUT', 'PATCH', 'DELETE') and request.is_json:
            payload = request.get_json(silent=True) or {}
            token = payload.get('csrf_token')
            if token:
                request.environ['HTTP_X_CSRFTOKEN'] = str(token)

    csrf.init_app(app)

    log_level = getattr(logging, app.config.get('LOG_LEVEL', 'INFO'), logging.INFO)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    ))
    console_handler.setLevel(log_level)
    app.logger.handlers = [console_handler]

    try:
        os.makedirs(app.instance_path, exist_ok=True)
        log_handler = RotatingFileHandler(
            os.path.join(app.instance_path, 'warehouse.log'),
            maxBytes=10_000_000,
            backupCount=5,
            encoding='utf-8'
        )
        log_handler.setFormatter(logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        ))
        log_handler.setLevel(log_level)
        app.logger.addHandler(log_handler)
    except OSError:
        pass

    app.logger.setLevel(log_level)

    @app.after_request
    def add_security_headers(response):
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('X-Frame-Options', 'SAMEORIGIN')
        response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        response.headers.setdefault('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
        if app.config.get('SESSION_COOKIE_SECURE'):
            response.headers.setdefault('Strict-Transport-Security', 'max-age=31536000; includeSubDomains')
        return response

    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

    from forms.material_forms import MaterialMarketplaceForm, AddMaterialForm
    from models import SupplierMaterial, User, AccessLevel
    import models_intelligence  # register vNext intelligence tables

    from blueprints.auth import auth_bp
    from blueprints.supplier import supplier_bp
    from blueprints.help import help_bp
    from blueprints.material_requisition import material_requisition_bp
    from blueprints.purchase_order import purchase_order_bp
    from blueprints.quality_control import quality_control_bp
    from blueprints.delivery import delivery_bp
    from blueprints.warehouse import warehouse_bp
    from blueprints.project_dashboard import project_dashboard_bp
    from blueprints.report import report_bp
    from blueprints.admin import admin_bp
    from blueprints.control_center import control_center_bp
    from blueprints.intelligence import intelligence_bp
    from role_workspace import role_workspace_bp
    growth_bp = _load_sidecar('materialhub_growth', 'growth.py').growth_bp
    health_bp = _load_sidecar('materialhub_health', 'health.py').health_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(supplier_bp, url_prefix='/supplier')
    app.register_blueprint(help_bp, url_prefix='/help')
    app.register_blueprint(material_requisition_bp, url_prefix='/material_requisitions')
    app.register_blueprint(purchase_order_bp, url_prefix='/purchase_order')
    app.register_blueprint(quality_control_bp, url_prefix='/quality_control')
    app.register_blueprint(delivery_bp, url_prefix='/delivery')
    app.register_blueprint(warehouse_bp, url_prefix='/warehouse')
    app.register_blueprint(project_dashboard_bp, url_prefix='/project_dashboard')
    app.register_blueprint(report_bp, url_prefix='/report')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(control_center_bp)
    app.register_blueprint(intelligence_bp)
    app.register_blueprint(role_workspace_bp)
    app.register_blueprint(growth_bp)
    app.register_blueprint(health_bp)

    with app.app_context():
        try:
            db.create_all()
            app.logger.info("Database tables created successfully.")
        except Exception as e:
            app.logger.error(f"Error creating database tables: {e}")

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    @app.route('/')
    def index():
        if current_user.is_authenticated:
            return redirect(url_for('role_workspace.my_workspace'))
        return render_template('marketing/landing.html')

    @app.route('/overview')
    def product_overview():
        return render_template('dashboard/home.html')

    @app.route('/dashboard')
    @login_required
    def dashboard():
        return redirect(url_for('control_center.dashboard'))

    @app.route('/health')
    def health():
        return {'status': 'ok', 'service': 'MaterialHub'}, 200

    @app.route('/getting-started')
    def getting_started_alias():
        return redirect(url_for('help.getting_started'))

    @app.route('/user-guide')
    def user_guide_alias():
        return redirect(url_for('help.user_guide'))

    @app.route('/about')
    def about_alias():
        return redirect(url_for('help.about'))

    @app.route('/register')
    def register_alias():
        return redirect(url_for('auth.register'))

    @app.route('/login')
    def login_alias():
        return redirect(url_for('auth.login'))

    @app.route('/inventory')
    @login_required
    def inventory():
        return render_template('warehouse/inventory.html')

    @app.route('/material_marketplace', methods=['GET', 'POST'])
    def material_marketplace():
        form = MaterialMarketplaceForm()
        query = SupplierMaterial.query
        if form.validate_on_submit():
            search_query = form.search.data
            country_code = form.country.data
            if search_query:
                query = query.filter(SupplierMaterial.material_name.ilike(f'%{search_query}%'))
            if country_code:
                query = query.filter(SupplierMaterial.country_code == country_code)
        materials = query.order_by(SupplierMaterial.updated_at.desc()).all()
        return render_template(
            'procurement/material_marketplace.html',
            form=form,
            materials=materials,
            COUNTRY_NAMES_BY_CODE=COUNTRY_NAMES_BY_CODE
        )

    @app.route('/add_material', methods=['GET', 'POST'])
    @login_required
    def add_material():
        if current_user.access_level != AccessLevel.supplier:
            flash('Only suppliers can add materials.', 'danger')
            return redirect(url_for('material_marketplace'))
        form = AddMaterialForm()
        if form.validate_on_submit():
            material = SupplierMaterial(
                user_id=current_user.id,
                material_name=form.material_name.data,
                material_type=form.category.data,
                price=form.unit_price.data,
                available_qty=form.available_quantity.data,
                unit=form.unit_of_measure.data,
                delivery_time_days=7,
                country_code=current_user.country,
                company_name=current_user.company_name
            )
            db.session.add(material)
            db.session.commit()
            flash('Material added successfully!', 'success')
            return redirect(url_for('material_marketplace'))
        return render_template('procurement/add_material.html', form=form)

    @app.route('/edit_material/<int:material_id>', methods=['GET', 'POST'])
    @login_required
    def edit_material(material_id):
        if current_user.access_level != AccessLevel.supplier:
            flash('Only suppliers can edit materials.', 'danger')
            return redirect(url_for('material_marketplace'))
        material = SupplierMaterial.query.get_or_404(material_id)
        if material.user_id != current_user.id:
            flash('You can only edit your own materials.', 'danger')
            return redirect(url_for('material_marketplace'))
        form = AddMaterialForm()
        if request.method == 'GET':
            form.material_name.data = material.material_name
            form.description.data = material.material_name
            form.category.data = material.material_type
            form.unit_price.data = material.price
            form.available_quantity.data = material.available_qty
            form.unit_of_measure.data = material.unit
        if form.validate_on_submit():
            material.material_name = form.material_name.data
            material.material_type = form.category.data
            material.price = form.unit_price.data
            material.available_qty = form.available_quantity.data
            material.unit = form.unit_of_measure.data
            material.country_code = current_user.country
            db.session.commit()
            flash('Material updated successfully!', 'success')
            return redirect(url_for('material_marketplace'))
        return render_template('procurement/edit_material.html', form=form, material=material)

    @app.route('/materials')
    @login_required
    def materials():
        query = SupplierMaterial.query
        if not current_user.is_admin:
            query = query.filter_by(company_name=current_user.company_name)
        materials = query.order_by(SupplierMaterial.updated_at.desc()).all()
        return render_template('procurement/materials.html', materials=materials)

    @app.route('/tender')
    @login_required
    def tender():
        return render_template('procurement/tender.html')

    @app.route('/privacy_policy')
    def privacy_policy():
        return render_template('legal/privacy_policy.html')

    @app.route('/terms_of_service')
    def terms_of_service():
        return render_template('legal/terms_of_service.html')

    @app.route('/contact_support')
    def contact_support():
        return render_template('support/contact_support.html')

    from errors import page_not_found, internal_server_error, forbidden
    app.register_error_handler(404, page_not_found)
    app.register_error_handler(500, internal_server_error)
    app.register_error_handler(403, forbidden)

    app.logger.info("MaterialHub application created successfully.")
    return app


app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=app.config.get('DEBUG', False))
