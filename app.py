import logging
import os
import sys
from flask import Flask, render_template, redirect, url_for, flash
from flask_login import LoginManager, login_required, current_user
from flask_wtf.csrf import CSRFProtect
from logging.handlers import RotatingFileHandler
from extensions import db
from config.config import config_by_name
from data.country_codes import COUNTRY_NAMES_BY_CODE


def create_app(config_name=None):
    """Application factory."""
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'development')

    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_by_name.get(config_name, config_by_name['default']))

    try:
        os.makedirs(app.instance_path, exist_ok=True)
    except OSError as e:
        app.logger.error(f"Error creating instance folder: {e}")

    # Extensions
    db.init_app(app)
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'warning'

    csrf = CSRFProtect()
    csrf.init_app(app)

    # Logging
    log_level = getattr(logging, app.config.get('LOG_LEVEL', 'INFO'))
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

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    ))
    console_handler.setLevel(log_level)

    app.logger.handlers = [log_handler, console_handler]
    app.logger.setLevel(log_level)

    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

    # Import models & forms after app context is ready
    from forms.material_forms import MaterialMarketplaceForm, AddMaterialForm
    from models import SupplierMaterial, User, AccessLevel

    # Register Blueprints
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

    with app.app_context():
        try:
            db.create_all()
            app.logger.info("Database tables created successfully.")
        except Exception as e:
            app.logger.error(f"Error creating database tables: {e}")
            raise

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # ---------- General routes ----------
    @app.route('/')
    def index():
        return render_template('home.html')

    @app.route('/dashboard')
    @login_required
    def dashboard():
        return render_template('dashboard.html')

    @app.route('/inventory')
    @login_required
    def inventory():
        return render_template('inventory.html')

    @app.route('/material_marketplace', methods=['GET', 'POST'])
    def material_marketplace():
        form = MaterialMarketplaceForm()
        materials = SupplierMaterial.query.all()
        if form.validate_on_submit():
            search_query = form.search.data
            country_code = form.country.data
            query = SupplierMaterial.query
            if search_query:
                query = query.filter(SupplierMaterial.material_name.ilike(f'%{search_query}%'))
            if country_code:
                query = query.filter(SupplierMaterial.country_code == country_code)
            materials = query.all()
        return render_template(
            'material_marketplace.html',
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
        return render_template('add_material.html', form=form)

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
        form = AddMaterialForm(obj=material)
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
        return render_template('edit_material.html', form=form, material=material)

    @app.route('/materials')
    @login_required
    def materials():
        materials = SupplierMaterial.query.all()
        return render_template('materials.html', materials=materials)

    @app.route('/tender')
    @login_required
    def tender():
        return render_template('tender.html')

    @app.route('/privacy_policy')
    def privacy_policy():
        return render_template('privacy_policy.html')

    @app.route('/terms_of_service')
    def terms_of_service():
        return render_template('terms_of_service.html')

    @app.route('/contact_support')
    def contact_support():
        return render_template('contact_support.html')

    # Error handlers
    try:
        from errors import page_not_found, internal_server_error
        app.register_error_handler(404, page_not_found)
        app.register_error_handler(500, internal_server_error)
    except ImportError as e:
        app.logger.error(f"Error importing error handlers: {e}")

        @app.errorhandler(404)
        def fallback_page_not_found(e):
            return render_template('404.html'), 404

        @app.errorhandler(500)
        def fallback_internal_server_error(e):
            return render_template('500.html'), 500

    app.logger.info("MaterialHub application created successfully.")
    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5000, debug=True)
