"""Session-bound CSRF protection and shared database-backed request limits."""
import hashlib
import hmac
import secrets

from flask import abort, request, session

from mf_app.db import consume_request_limit, get_admin_session_version


def csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


def install_security(app):
    app.jinja_env.globals["csrf_token"] = csrf_token

    @app.before_request
    def protect_requests():
        if request.endpoint != "static" and session.get("admin_logged_in"):
            version = get_admin_session_version(session.get("admin_username", ""))
            if version is None or session.get("admin_session_version") != version:
                session.pop("admin_logged_in", None)
                session.pop("admin_username", None)
                session.pop("admin_session_version", None)
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            expected = session.get("csrf_token")
            supplied = request.form.get("csrf_token", "")
            if not expected or not isinstance(supplied, str) or len(supplied) != len(expected) or not hmac.compare_digest(expected.encode(), supplied.encode()):
                abort(400, description="This form expired or could not be verified. Reload the page and try again.")

    @app.after_request
    def response_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        if request.endpoint != "static":
            response.headers["Cache-Control"] = "no-store"
        return response


def request_allowed(app, action, limit, seconds):
    # Only a keyed digest is stored; raw visitor IP addresses are not retained.
    identity = hmac.new(app.secret_key.encode(), (request.remote_addr or "unknown").encode(), hashlib.sha256).hexdigest()
    return consume_request_limit(f"{action}:{identity}", limit, seconds)
