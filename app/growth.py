from flask import Blueprint, render_template, request, redirect, url_for, flash
growth_bp=Blueprint("growth",__name__)
@growth_bp.get("/")
def landing(): return render_template("marketing/landing.html")
@growth_bp.get("/demo")
def demo(): return render_template("marketing/demo.html")
@growth_bp.get("/pricing")
def pricing(): return render_template("marketing/pricing.html")
@growth_bp.route("/contact",methods=["GET","POST"])
def contact():
    if request.method=="POST":
        flash("Thank you. Your demo request has been received.","success")
        return redirect(url_for("growth.contact"))
    return render_template("marketing/contact.html")
