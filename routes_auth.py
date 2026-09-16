from flask import Blueprint, render_template, request, redirect, url_for, flash

from database import verify_login, set_password
from auth import login_account, logout_account, login_required, current_account

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    account = current_account()

    if account is not None:
        return redirect(url_for(
            "teacher.dashboard" if account["role"] == "teacher" else "student.dashboard"
        ))

    if request.method == "POST":
        login_value = request.form.get("login", "").strip()
        password = request.form.get("password", "")

        account = verify_login(login_value, password)

        if account is None:
            flash("Невірний логін або пароль", "error")
            return render_template("login.html")

        login_account(account)

        if account["must_change_password"]:
            return redirect(url_for("auth.change_password"))

        return redirect(url_for(
            "teacher.dashboard" if account["role"] == "teacher" else "student.dashboard"
        ))

    return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    logout_account()
    return redirect(url_for("auth.login"))


@auth_bp.route("/change-password", methods=["GET", "POST"])
@login_required()
def change_password(account):
    if request.method == "POST":
        new_password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")

        if len(new_password) < 6:
            flash("Пароль має містити щонайменше 6 символів", "error")
            return render_template("change_password.html")

        if new_password != confirm:
            flash("Паролі не співпадають", "error")
            return render_template("change_password.html")

        set_password(account["id"], new_password)
        flash("Пароль оновлено", "success")

        return redirect(url_for(
            "teacher.dashboard" if account["role"] == "teacher" else "student.dashboard"
        ))

    return render_template("change_password.html")
