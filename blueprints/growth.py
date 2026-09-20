from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import ContactInquiry
from extensions import db

growth_bp = Blueprint("growth", __name__)


@growth_bp.get("/demo")
def demo():
    return render_template("marketing/demo.html")


@growth_bp.get("/pricing")
def pricing():
    return render_template("marketing/pricing.html")


@growth_bp.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip()
        company = (request.form.get("company") or "").strip()
        message = (request.form.get("message") or "").strip()
        if not name or not email:
            flash("Please provide your name and work email.", "danger")
            return render_template("marketing/contact.html")
        inquiry = ContactInquiry(
            name=name,
            email=email,
            company=company or None,
            message=message or None,
            source="website",
        )
        db.session.add(inquiry)
        db.session.commit()
        flash("Thank you. Your demo request has been received.", "success")
        return redirect(url_for("growth.contact"))
    return render_template("marketing/contact.html")
