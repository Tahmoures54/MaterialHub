from flask import Blueprint, render_template

help_bp = Blueprint('help', __name__, template_folder='templates')

@help_bp.route('/help')
def help():
    return render_template('help/help.html')

@help_bp.route('/user-guide')
def user_guide():
    return render_template('help/user_guide.html')

@help_bp.route('/getting-started')
def getting_started():
    return render_template('help/getting_started.html')

@help_bp.route('/about')
def about():
    return render_template('help/about.html')
