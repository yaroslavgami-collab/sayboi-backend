from functools import wraps

from flask import session, redirect, url_for, flash

from database import get_account


def current_account():
    account_id = session.get("account_id")

    if not account_id:
        return None

    return get_account(account_id)


def login_account(account):
    session.clear()
    session["account_id"] = account["id"]
    session["role"] = account["role"]


def logout_account():
    session.clear()


def login_required(role=None):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            account = current_account()

            if account is None:
                return redirect(url_for("auth.login"))

            if role and account["role"] != role:
                flash("Недостатньо прав доступу", "error")
                return redirect(url_for("auth.login"))

            return view(account, *args, **kwargs)

        return wrapped

    return decorator
