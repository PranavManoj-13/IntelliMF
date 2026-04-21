import os
from datetime import timedelta

import pandas as pd
from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.middleware.proxy_fix import ProxyFix

from mf_app.analytics import compare_sip_frequencies, mine_frequent_itemsets, simulate_sip
from mf_app.db import (
    add_sip_orders,
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
from mf_app.services import MFAPIClient, compute_trailing_returns


def create_app() -> Flask:
    railway_environment = os.getenv("RAILWAY_ENVIRONMENT")
    flask_secret_key = os.getenv("FLASK_SECRET_KEY")
    if railway_environment and not flask_secret_key:
        raise RuntimeError("FLASK_SECRET_KEY must be set in Railway for stable admin sessions.")

    app = Flask(__name__)
    app.secret_key = flask_secret_key or os.urandom(24)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "true").lower() == "true",
        PERMANENT_SESSION_LIFETIME=timedelta(days=7),
        PREFERRED_URL_SCHEME="https",
    )

    init_db()
    client = MFAPIClient()

    @app.context_processor
    def inject_globals():
        return {
            "admin_logged_in": bool(session.get("admin_logged_in")),
            "admin_username": session.get("admin_username", ""),
        }

    @app.route("/")
    def home():
        total_schemes = client.get_scheme_count()
        return render_template("home.html", total_schemes=total_schemes)

    @app.route("/search")
    def search():
        query = request.args.get("q", "").strip()
        schemes = client.search_schemes(query) if query else []
        return render_template(
            "search_results.html",
            query=query,
            schemes=schemes,
            total_results=len(schemes),
        )

    @app.route("/fund/<scheme_code>")
    def fund_detail(scheme_code: str):
        details = client.fetch_scheme_details(scheme_code)
        nav_history = details.nav_history

        if nav_history.empty:
            flash("NAV history is not available for this mutual fund.", "error")
            return redirect(url_for("home"))

        try:
            default_amount = float(request.args.get("amount", 5000))
        except ValueError:
            default_amount = 5000.0
        default_end = nav_history["date"].max()
        default_start = max(
            nav_history["date"].min(),
            default_end - pd.DateOffset(years=3),
        )

        requested_start = request.args.get("start_date")
        requested_end = request.args.get("end_date")
        selected_start = pd.to_datetime(requested_start, errors="coerce") if requested_start else pd.Timestamp(default_start)
        selected_end = pd.to_datetime(requested_end, errors="coerce") if requested_end else pd.Timestamp(default_end)
        if pd.isna(selected_start):
            selected_start = pd.Timestamp(default_start)
        if pd.isna(selected_end):
            selected_end = pd.Timestamp(default_end)

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
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            if authenticate_admin(username, password):
                session["admin_logged_in"] = True
                session["admin_username"] = username
                session.permanent = True
                flash("Admin login successful.", "success")
                return redirect(url_for("admin_dashboard"))
            flash("Invalid username or password.", "error")

        return render_template("admin_login.html")

    @app.route("/admin/logout")
    def admin_logout():
        session.pop("admin_logged_in", None)
        session.pop("admin_username", None)
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

            if len(new_password) < 6:
                flash("New password must be at least 6 characters long.", "error")
            elif new_password != confirm_password:
                flash("New password and confirmation do not match.", "error")
            elif update_admin_password(session.get("admin_username", ""), current_password, new_password):
                flash("Admin password updated successfully.", "success")
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

            if not username:
                flash("New admin username is required.", "error")
            elif len(password) < 6:
                flash("New admin password must be at least 6 characters long.", "error")
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
            scheme_code = request.form.get("scheme_code", "").strip()
            scheme_name = request.form.get("scheme_name", "").strip()
            if not scheme_code or not scheme_name:
                flash("Scheme code and scheme name are required to save metadata.", "error")
                return redirect(url_for("admin_metadata"))

            upsert_fund_admin_details(
                [
                    {
                        "scheme_code": scheme_code,
                        "scheme_name": scheme_name,
                        "fund_manager": request.form.get("fund_manager", "").strip(),
                        "aum": request.form.get("aum", "").strip(),
                        "lock_in_period": request.form.get("lock_in_period", "").strip(),
                        "expense_ratio": request.form.get("expense_ratio", "").strip(),
                        "risk_level": request.form.get("risk_level", "").strip(),
                        "notes": request.form.get("notes", "").strip(),
                    }
                ]
            )
            flash(f"Fund metadata updated for {scheme_name}.", "success")
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
            selected_schemes = request.form.getlist("selected_schemes")

            if not investor_id:
                flash("Investor ID is required.", "error")
            elif not selected_schemes:
                flash("Select at least one mutual fund.", "error")
            else:
                allocations = []
                for scheme in selected_schemes:
                    scheme_code, scheme_name = scheme.split("|||", 1)
                    amount_raw = request.form.get(f"amount_{scheme_code}", "0")
                    frequency = request.form.get(f"frequency_{scheme_code}", "Monthly")
                    start_date = request.form.get(f"start_date_{scheme_code}", "")
                    try:
                        amount = float(amount_raw or 0)
                    except ValueError:
                        amount = 0

                    if amount <= 0 or not start_date:
                        continue

                    allocations.append(
                        {
                            "scheme_code": scheme_code,
                            "scheme_name": scheme_name,
                            "amount": amount,
                            "frequency": frequency,
                            "start_date": start_date,
                        }
                    )
                if not allocations:
                    flash("Each selected fund needs a valid SIP amount and start date.", "error")
                else:
                    add_sip_orders(investor_id, "", allocations)
                    flash(f"Stored {len(allocations)} SIP order(s) for {investor_id}.", "success")
                    return redirect(url_for("admin_cart", clear_cart="1"))

        orders = fetch_sip_orders()
        return render_template(
            "admin_cart.html",
            orders=orders,
            clear_cart=request.args.get("clear_cart") == "1",
        )

    @app.route("/admin/dashboard")
    def admin_dashboard():
        if not session.get("admin_logged_in"):
            flash("Please log in as admin to continue.", "error")
            return redirect(url_for("admin_login"))

        return render_template("admin_dashboard.html")

    return app


app = create_app()


if __name__ == "__main__":
    debug_enabled = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=debug_enabled)
