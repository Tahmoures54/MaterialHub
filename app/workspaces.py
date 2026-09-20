from flask import Blueprint, render_template

workspace_bp = Blueprint("workspace", __name__, url_prefix="/workspace")

@workspace_bp.get("/")
def index():
    return render_template("workspaces/project_manager.html")

@workspace_bp.get("/project-manager")
def project_manager(): return render_template("workspaces/project_manager.html")
@workspace_bp.get("/engineering")
def engineering(): return render_template("workspaces/engineering.html")
@workspace_bp.get("/procurement")
def procurement(): return render_template("workspaces/procurement.html")
@workspace_bp.get("/warehouse")
def warehouse(): return render_template("workspaces/warehouse.html")
@workspace_bp.get("/quality")
def quality(): return render_template("workspaces/quality.html")
@workspace_bp.get("/supplier")
def supplier(): return render_template("workspaces/supplier.html")
@workspace_bp.get("/admin")
def admin(): return render_template("workspaces/admin.html")
