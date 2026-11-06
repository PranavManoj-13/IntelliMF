import os
import re
import secrets
from datetime import timedelta

import click

from dotenv import load_dotenv
import pandas as pd
from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from werkzeug.middleware.proxy_fix import ProxyFix

# Load environment variables from .env file
load_dotenv()

from mf_app.analytics import compare_sip_frequencies, mine_frequent_itemsets, simulate_sip
from mf_app.db import (
    add_sip_orders,
    add_public_basket,
    delete_public_basket,
    fetch_public_baskets,
    verified_admin_session_version,
    has_public_basket,
    set_admin_credentials,
    authenticate_admin,
    create_admin_user,
    delete_sip_order,
    fetch_all_fund_admin_details,
    fetch_baskets,
    fetch_fund_admin_details,
    fetch_scheme_by_code,
    fetch_sip_orders,
    init_db,
    upsert_fund_admin_details,
    update_admin_password,
)
from mf_app.services import MFAPIClient, MFAPIUnavailable, compute_trailing_returns
from mf_app.security import install_security, request_allowed
from mf_app.validation import amount_value, date_value, frequency_value, metadata_values, order_allocations, selected_funds


def create_app() -> Flask:
    flask_secret_key = os.getenv("FLASK_SECRET_KEY")
    debug_enabled = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    if not flask_secret_key and not debug_enabled:
        raise RuntimeError("FLASK_SECRET_KEY must be set for non-debug deployments.")

    app = Flask(__name__)
    app.secret_key = flask_secret_key or secrets.token_urlsafe(48)
    if os.getenv("TRUST_PROXY", "false").lower() == "true":
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
    app.config.update(
        SECRET_KEY=app.secret_key,
        MAX_CONTENT_LENGTH=128 * 1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "true").lower() == "true",
        SESSION_REFRESH_EACH_REQUEST=False,
        SESSION_PERMANENT=False,
        PERMANENT_SESSION_LIFETIME=timedelta(days=7),
        PREFERRED_URL_SCHEME="https",
    )

    init_db()
    client = MFAPIClient()
    install_security(app)

    @app.cli.command("set-admin")
    @click.option("--username", prompt=True)
    @click.password_option()
    def set_admin(username, password):
        """Create or reset an admin using an interactive, hidden password prompt."""
        try:
            set_admin_credentials(username, password)
        except ValueError as error:
            raise click.ClickException(str(error)) from None
        click.echo("Admin credentials saved. Existing sessions for this account have been invalidated.")

    @app.before_request
    def validate_query_lengths():
        if any(len(value) > 200 or "\x00" in value for _, value in request.args.items(multi=True)):
            abort(400, description="The search or form value is too long or contains invalid characters.")

    @app.errorhandler(400)
    @app.errorhandler(413)
    @app.errorhandler(429)
    def invalid_request(error):
        return render_template("error.html", message=error.description), error.code

    @app.errorhandler(404)
    def page_not_found(_error):
        return render_template("404.html"), 404

    @app.errorhandler(MFAPIUnavailable)
    def unavailable_fund(error):
        flash(str(error), "error")
        return redirect(url_for("home"))

    @app.context_processor
    def inject_globals():
        return {
            "admin_logged_in": bool(session.get("admin_logged_in")),
            "admin_username": session.get("admin_username", ""),
        }

    @app.route("/")
    def home():
        return render_template("home.html")

    @app.route("/search")
    def search():
        query = request.args.get("q", "").strip()
        schemes = client.search_schemes(query) if query else []
        page_size = 24
        total_results = len(schemes)
        page_count = max(1, (total_results + page_size - 1) // page_size)
        page = min(max(1, request.args.get("page", 1, type=int)), page_count)
        start = (page - 1) * page_size
        return render_template(
            "search_results.html",
            query=query,
            schemes=schemes[start:start + page_size],
            total_results=total_results,
            page=page,
            page_count=page_count,
            first_result=start + 1,
            last_result=min(start + page_size, total_results),
        )

    @app.route("/fund/<scheme_code>")
    def fund_detail(scheme_code: str):
        if not re.fullmatch(r"\d{1,12}", scheme_code):
            abort(404)
        details = client.fetch_scheme_details(scheme_code)
        nav_history = details.nav_history

        if nav_history.empty:
            flash("NAV history is not available for this mutual fund.", "error")
            return redirect(url_for("home"))

        default_end = pd.Timestamp(nav_history["date"].max())
        default_start = max(pd.Timestamp(nav_history["date"].min()), default_end - pd.DateOffset(years=3))
        try:
            default_amount = amount_value(request.args.get("amount", "5000"))
            selected_start = pd.Timestamp(date_value(request.args["start_date"])) if request.args.get("start_date") else default_start
            selected_end = pd.Timestamp(date_value(request.args["end_date"])) if request.args.get("end_date") else default_end
            if selected_start > selected_end:
                raise ValueError("Start date must be on or before end date.")
            if selected_start < nav_history["date"].min() or selected_end > default_end:
                raise ValueError("Choose dates within the available NAV history.")
            if request.args.get("frequency"):
                frequency_value(request.args["frequency"])
        except ValueError as error:
            flash(str(error), "error")
            return redirect(url_for("fund_detail", scheme_code=scheme_code))

        recommendation = compare_sip_frequencies(
            nav_history=nav_history,
            amount=default_amount,
            start_date=selected_start,
            end_date=selected_end,
        )

        selected_frequency = request.args.get("frequency") or recommendation["best_frequency"]

        sip_result = simulate_sip(
            nav_history=nav_history,
            amount=default_amount,
            frequency=selected_frequency,
            start_date=selected_start,
            end_date=selected_end,
        )

        if not sip_result["summary"]:
            flash("No SIP executions are available within this date range. Choose a period containing a NAV date.", "error")

        return render_template(
            "fund_detail.html",
            details=details,
            admin_fund_details=fetch_fund_admin_details(details.scheme_code),
            nav_chart=details.nav_chart_points(),
            trailing_returns=compute_trailing_returns(details.actual_nav_history),
            sip_result=sip_result,
            recommendation=recommendation,
            selected_frequency=selected_frequency,
            selected_amount=default_amount,
            selected_start=selected_start.strftime("%Y-%m-%d"),
            selected_end=selected_end.strftime("%Y-%m-%d"),
            min_date=nav_history["date"].min().strftime("%Y-%m-%d"),
            max_date=nav_history["date"].max().strftime("%Y-%m-%d"),
        )

    @app.route("/recommendations")
    def recommendations():
        baskets = fetch_baskets()
        try:
            itemsets, rules = mine_frequent_itemsets(baskets)
        except Exception:
            app.logger.exception("Basket mining failed")
            flash("Recommendations could not be generated from the current order history.", "error")
            itemsets, rules = [], []
        return render_template(
            "recommendations.html",
            basket_count=len(baskets),
            itemsets=itemsets,
            rules=rules,
        )

    @app.route("/admin/login", methods=["GET", "POST"])
    def admin_login():
        if request.method == "POST":
            if not request_allowed(app, "admin-login", 10, 900):
                abort(429, description="Too many login attempts. Please try again in 15 minutes.")
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            if len(username) > 80 or (username and not username.isprintable()) or len(password) > 256:
                abort(400, description="Invalid login details.")
            version = verified_admin_session_version(username, password)
            if version is not None:
                respondent = session.get("public_respondent_key")
                session.clear()
                if respondent:
                    session["public_respondent_key"] = respondent
                session["admin_session_version"] = version
                session["admin_logged_in"] = True
                session["admin_username"] = username
                session.permanent = False
                flash("Admin login successful.", "success")
                return redirect(url_for("admin_dashboard"))
            flash("Invalid username or password.", "error")

        return render_template("admin_login.html")

    @app.post("/admin/logout")
    def admin_logout():
        respondent = session.get("public_respondent_key")
        session.clear()
        if respondent:
            session["public_respondent_key"] = respondent
        flash("Logged out successfully.", "success")
        return redirect(url_for("home"))

    @app.post("/admin/orders/<int:order_id>/delete")
    def admin_delete_order(order_id: int):
        if not session.get("admin_logged_in"):
            flash("Please log in as admin to continue.", "error")
            return redirect(url_for("admin_login"))

        if delete_sip_order(order_id):
            flash("SIP entry deleted successfully.", "success")
        else:
            flash("SIP entry could not be deleted.", "error")
        return redirect(url_for("admin_cart"))

    @app.route("/admin/password", methods=["GET", "POST"])
    def admin_password():
        if not session.get("admin_logged_in"):
            flash("Please log in as admin to continue.", "error")
            return redirect(url_for("admin_login"))

        if request.method == "POST":
            current_password = request.form.get("current_password", "")
            new_password = request.form.get("new_password", "")
            confirm_password = request.form.get("confirm_password", "")

            if not 12 <= len(new_password) <= 256:
                flash("New password must be 12–256 characters long.", "error")
            elif new_password != confirm_password:
                flash("New password and confirmation do not match.", "error")
            elif update_admin_password(session.get("admin_username", ""), current_password, new_password):
                session.clear()
                flash("Password updated. Please log in again.", "success")
                return redirect(url_for("admin_login"))
            else:
                flash("Current password is incorrect.", "error")
            return redirect(url_for("admin_password"))

        return render_template("admin_password.html")

    @app.route("/admin/users", methods=["GET", "POST"])
    def admin_users():
        if not session.get("admin_logged_in"):
            flash("Please log in as admin to continue.", "error")
            return redirect(url_for("admin_login"))

        if request.method == "POST":
            username = request.form.get("new_admin_username", "").strip()
            password = request.form.get("new_admin_password", "")
            confirm_password = request.form.get("confirm_new_admin_password", "")

            if not authenticate_admin(session.get("admin_username", ""), request.form.get("current_password", "")):
                flash("Enter your current password to create an admin account.", "error")
            elif not username or len(username) > 80:
                flash("Use a username of 1–80 characters.", "error")
            elif not 12 <= len(password) <= 256:
                flash("New admin password must be 12–256 characters long.", "error")
            elif password != confirm_password:
                flash("New admin password and confirmation do not match.", "error")
            else:
                ok, message = create_admin_user(username, password)
                flash(message, "success" if ok else "error")
            return redirect(url_for("admin_users"))

        return render_template("admin_users.html")

    @app.route("/admin/metadata", methods=["GET", "POST"])
    def admin_metadata():
        if not session.get("admin_logged_in"):
            flash("Please log in as admin to continue.", "error")
            return redirect(url_for("admin_login"))

        if request.method == "POST":
            try:
                values = metadata_values(request.form)
            except ValueError as error:
                flash(str(error), "error")
                return redirect(url_for("admin_metadata"))
            scheme_code = values["scheme_code"]
            upsert_fund_admin_details([values])
            flash(f"Fund metadata updated for {values['scheme_name']}.", "success")
            return redirect(
                url_for(
                    "admin_metadata",
                    meta_query=request.args.get("meta_query", ""),
                    meta_scheme_code=scheme_code,
                )
            )

        meta_query = request.args.get("meta_query", "").strip()
        meta_scheme_code = request.args.get("meta_scheme_code", "").strip()
        metadata_search_results = client.search_schemes(meta_query) if meta_query else []
        selected_metadata_scheme = fetch_scheme_by_code(meta_scheme_code) if meta_scheme_code else None
        return render_template(
            "admin_metadata.html",
            meta_query=meta_query,
            meta_scheme_code=meta_scheme_code,
            metadata_search_results=metadata_search_results,
            selected_metadata_scheme=selected_metadata_scheme,
            selected_metadata_details=fetch_fund_admin_details(meta_scheme_code) if meta_scheme_code else None,
            fund_metadata_rows=fetch_all_fund_admin_details(),
        )

    @app.route("/admin/orders")
    def admin_orders():
        if not session.get("admin_logged_in"):
            flash("Please log in as admin to continue.", "error")
            return redirect(url_for("admin_login"))

        fund_query = request.args.get("fund_query", "").strip()
        admin_search_results = client.search_schemes(fund_query) if fund_query else []
        return render_template(
            "admin_orders.html",
            fund_query=fund_query,
            search_results=admin_search_results,
        )

    @app.route("/admin/cart", methods=["GET", "POST"])
    def admin_cart():
        if not session.get("admin_logged_in"):
            flash("Please log in as admin to continue.", "error")
            return redirect(url_for("admin_login"))

        if request.method == "POST":
            investor_id = request.form.get("investor_id", "").strip()
            try:
                if not investor_id or len(investor_id) > 100 or not investor_id.isprintable():
                    raise ValueError("Enter an investor ID of 1–100 characters.")
                allocations = order_allocations(request.form)
            except ValueError as error:
                flash(str(error), "error")
            else:
                add_sip_orders(investor_id, allocations)
                flash(f"Stored {len(allocations)} SIP order(s) for {investor_id}.", "success")
                return redirect(url_for("admin_cart", clear_cart="1"))

        orders = fetch_sip_orders()
        return render_template(
            "admin_cart.html",
            orders=orders,
            clear_cart=request.args.get("clear_cart") == "1",
        )

    @app.route("/share-basket", methods=["GET", "POST"])
    def share_basket():
        if "public_respondent_key" not in session:
            session["public_respondent_key"] = secrets.token_urlsafe(32)
        respondent = session["public_respondent_key"]
        submitted = has_public_basket(respondent)
        if request.method == "POST":
            if submitted:
                flash("Your basket has already been received. Thank you!", "success")
                return redirect(url_for("share_basket"))
            if not request_allowed(app, "public-basket", 30, 3600):
                abort(429, description="Too many submissions. Please try again in an hour.")
            try:
                schemes = selected_funds(request.form.getlist("scheme_codes"))
            except ValueError as error:
                flash(str(error), "error")
            else:
                add_public_basket(respondent, schemes)
                flash("Thank you! Your basket now contributes to investor patterns.", "success")
                return redirect(url_for("share_basket"))
        query = request.args.get("q", "").strip()
        results = client.search_schemes(query)[:100] if query and not submitted else []
        return render_template("share_basket.html", query=query, results=results, submitted=submitted)

    @app.get("/admin/public-baskets")
    def admin_public_baskets():
        if not session.get("admin_logged_in"):
            flash("Please log in as admin to continue.", "error")
            return redirect(url_for("admin_login"))
        return render_template("admin_public_baskets.html", baskets=fetch_public_baskets())

    @app.post("/admin/public-baskets/<basket_id>/delete")
    def admin_delete_public_basket(basket_id):
        if not session.get("admin_logged_in"):
            abort(403)
        if delete_public_basket(basket_id):
            flash("Public basket deleted and removed from investor pattern calculations.", "success")
        else:
            flash("That basket was already removed.", "error")
        return redirect(url_for("admin_public_baskets"))

    @app.route("/admin/dashboard")
    def admin_dashboard():
        if not session.get("admin_logged_in"):
            flash("Please log in as admin to continue.", "error")
            return redirect(url_for("admin_login"))

        return render_template("admin_dashboard.html")

    return app


app = create_app()


if __name__ == "__main__":
    debug_enabled = os.getenv("FLASK_DEBUG", "False").lower() == "true"
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=debug_enabled)
