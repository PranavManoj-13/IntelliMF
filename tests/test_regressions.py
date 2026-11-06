"""Regression checks using isolated SQLite and synthetic upstream responses."""
import importlib
import os
import re
import runpy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd
import requests
from sqlalchemy import inspect, text


ROOT = Path(__file__).resolve().parents[1]
PASSWORD = "test-only-admin-password"


class AppRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        env = patch.dict(os.environ, {
            "DATABASE_URL": "sqlite:///:memory:", "FLASK_SECRET_KEY": "isolated-test-secret",
            "COOKIE_SECURE": "false", "MF_ADMIN_USERNAME": "", "MF_ADMIN_PASSWORD": "",
        })
        env.start()
        cls.addClassCleanup(env.stop)
        cls.app = importlib.import_module("app").app
        cls.app.config["TESTING"] = True
        cls.db = importlib.import_module("mf_app.db")
        cls.analytics = importlib.import_module("mf_app.analytics")
        cls.services = importlib.import_module("mf_app.services")

    def setUp(self):
        self.db.get_engine().dispose()
        self.db.init_db()
        self.db.replace_schemes([
            {"schemeCode": "1001", "schemeName": "Example Index Fund"},
            {"schemeCode": "1002", "schemeName": "Example Bond Fund"},
        ])
        self.client = self.app.test_client()

    def token(self, client, path):
        page = client.get(path)
        self.assertEqual(page.status_code, 200)
        match = re.search(r'name="csrf_token" value="([^"]+)"', page.get_data(as_text=True))
        self.assertIsNotNone(match, path)
        return match.group(1)

    def login(self):
        self.db.set_admin_credentials("reviewer", PASSWORD)
        token = self.token(self.client, "/admin/login")
        response = self.client.post("/admin/login", data={"username": "reviewer", "password": PASSWORD, "csrf_token": token})
        self.assertTrue(response.location.endswith("/admin/dashboard"))
        return self.token(self.client, "/admin/dashboard")

    def test_fund_search_matches_partial_terms_in_any_order(self):
        self.db.replace_schemes([
            {"schemeCode": "1001", "schemeName": "Example Nifty 50 Index Fund - Direct Growth"},
            {"schemeCode": "1002", "schemeName": "Example Nifty 50 Index Fund - Regular Growth"},
            {"schemeCode": "1003", "schemeName": "Another Nifty 50 Index Fund - Direct Growth"},
        ])
        for query in ("direct example nifty50", "EXAM / NIFTY 50 - DIRECT"):
            with self.subTest(query=query):
                response = self.client.get("/search", query_string={"q": query})
                self.assertEqual(response.status_code, 200)
                self.assertIn(b'href="/fund/1001"', response.data)
                self.assertNotIn(b'href="/fund/1002"', response.data)
                self.assertNotIn(b'href="/fund/1003"', response.data)
        self.assertEqual(self.db.search_schemes("1001")[0]["scheme_code"], "1001")

    def test_weekly_execution_after_end_does_not_count(self):
        nav = pd.DataFrame({"date": pd.to_datetime(["2025-01-01", "2025-01-08", "2025-01-22"]), "nav": [100, 110, 121]})
        result = self.analytics.simulate_sip(nav, 5000, "Weekly", pd.Timestamp("2025-01-01"), pd.Timestamp("2025-01-15"))
        self.assertEqual([row["execution_date"] for row in result["investments"]], ["2025-01-01", "2025-01-08"])
        self.assertEqual(result["summary"]["installments"], 2)
        self.assertEqual(result["summary"]["total_invested"], 5000)
        self.assertEqual(result["summary"]["current_value"], 5250)
        self.assertEqual(result["daily_series"][-1]["invested_amount"], 5000)
        empty = self.analytics.simulate_sip(nav, 5000, "Monthly", pd.Timestamp("2025-01-09"), pd.Timestamp("2025-01-15"))
        self.assertEqual(empty, {"summary": {}, "investments": [], "daily_series": []})

    def test_preprocessed_csv_keeps_imputed_values(self):
        preprocess = runpy.run_path(str(ROOT / "files/Data-Preprocessing.py"))
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder)
            (source / "scheme_1001.csv").write_text("date,nav,scheme_name,fund_house\n03-01-2025,110,A,B\n02-01-2025,,A,B\n01-01-2025,100,A,B\n")
            (source / "Schemes-List.csv").write_text("schemeCode,schemeName\n1001,A\n")
            output = source / "processed"
            preprocess["ProcessAllCSVFiles"](str(source), str(output))
            processed = pd.read_csv(output / "scheme_1001.csv")
            self.assertEqual(processed["nav"].tolist(), [100, 100, 110])
            self.assertEqual(processed["date"].tolist(), ["01-01-2025", "02-01-2025", "03-01-2025"])
            self.assertEqual(processed.columns.tolist(), ["date", "nav"])
            self.assertFalse((output / "Schemes-List.csv").exists())

    def test_upstream_timeout_and_malformed_details(self):
        api = self.services.MFAPIClient()
        response = Mock()
        response.json.return_value = {"meta": {}, "data": [{"date": "01-01-2025"}, 1]}
        with patch.object(api.session, "get", return_value=response):
            with self.assertRaises(self.services.MFAPIUnavailable):
                api.fetch_scheme_details("1001")
        response.json.return_value = {"meta": {}, "data": []}
        with patch.object(api.session, "get", return_value=response):
            self.assertTrue(api.fetch_scheme_details("1001").nav_history.empty)
        with patch("requests.Session.get", side_effect=requests.Timeout):
            response = self.client.get("/fund/1001", follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"Fund details are temporarily unavailable", response.data)

    def test_invalid_sip_inputs_are_rejected(self):
        frame = pd.DataFrame({"date": pd.to_datetime(["2025-01-01", "2025-01-08", "2025-01-22"]), "nav": [100, 110, 121]})
        details = self.services.SchemeDetails("1001", "Example Fund", "Example", "Equity", "Index", 121, frame.date.max(), frame, frame)
        with patch.object(self.services.MFAPIClient, "fetch_scheme_details", return_value=details):
            for query in ["amount=NaN", "amount=inf", "amount=-1", "frequency=Never", "start_date=2025-01-03T00:00:00Z", "start_date=2025-01-08&end_date=2025-01-01"]:
                with self.subTest(query=query):
                    response = self.client.get(f"/fund/1001?{query}")
                    self.assertEqual(response.status_code, 302)
                    self.assertEqual(response.location, "/fund/1001")
            response = self.client.get("/fund/1001?start_date=2025-01-09&end_date=2025-01-15")
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"No SIP executions", response.data)

    def test_old_default_login_is_disabled_and_legacy_plaintext_removed(self):
        with self.db.get_engine().begin() as connection:
            connection.execute(text("DROP TABLE admins"))
            connection.execute(text("CREATE TABLE admins (id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, password TEXT NOT NULL)"))
            connection.execute(text("INSERT INTO admins (username, password) VALUES ('admin', 'admin123'), ('existing', :password)"), {"password": PASSWORD})
        with patch.dict(os.environ, {"MF_ADMIN_USERNAME": "admin", "MF_ADMIN_PASSWORD": "admin123"}):
            self.db.init_db()
        columns = {column["name"] for column in inspect(self.db.get_engine()).get_columns("admins")}
        self.assertNotIn("password", columns)
        self.assertFalse(self.db.authenticate_admin("admin", "admin123"))
        self.assertTrue(self.db.authenticate_admin("existing", PASSWORD))
        self.db.set_admin_credentials("admin", PASSWORD)
        self.assertTrue(self.db.authenticate_admin("admin", PASSWORD))

    def test_admin_cli_resets_password_and_invalidates_old_session(self):
        self.login()
        replacement = "test-only-replacement-password"
        result = self.app.test_cli_runner().invoke(args=["set-admin", "--username", "reviewer"], input=f"{replacement}\n{replacement}\n")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertTrue(self.db.authenticate_admin("reviewer", replacement))
        self.assertFalse(self.db.authenticate_admin("reviewer", PASSWORD))
        self.assertEqual(self.client.get("/admin/dashboard").status_code, 302)

    def test_admin_writes_need_csrf_and_logout_is_a_toast(self):
        self.assertFalse(self.db.authenticate_admin("admin", "admin123"))
        token = self.login()
        for route in ["/admin/login", "/admin/logout", "/admin/password", "/admin/users", "/admin/metadata", "/admin/cart", "/admin/orders/1/delete", "/admin/public-baskets/example/delete", "/share-basket"]:
            with self.subTest(route=route):
                self.assertEqual(self.client.post(route).status_code, 400)
        self.assertEqual(self.client.post("/admin/logout", data={"csrf_token": "é" * len(token)}).status_code, 400)
        self.assertEqual(self.client.get("/admin/logout").status_code, 405)
        response = self.client.post("/admin/logout", data={"csrf_token": token}, follow_redirects=True)
        self.assertIn(b"toast-success", response.data)
        self.assertIn(b"Logged out successfully.", response.data)
        self.assertEqual(self.client.get("/admin/dashboard").status_code, 302)

    def test_cart_is_validated_as_one_basket_and_uses_catalogue_names(self):
        token = self.login()
        data = {"csrf_token": token, "investor_id": "test investor", "selected_schemes": ["1001|||<img onerror=alert(1)>", "1002"],
                "amount_1001": "5000", "frequency_1001": "Monthly", "start_date_1001": "2025-01-01",
                "amount_1002": "NaN", "frequency_1002": "Weekly", "start_date_1002": "2025-01-02"}
        response = self.client.post("/admin/cart", data=data)
        self.assertIn(b"finite", response.data)
        self.assertEqual(self.db.fetch_sip_orders(), [])
        data["amount_1002"] = "2000"
        self.assertEqual(self.client.post("/admin/cart", data=data).status_code, 302)
        self.assertEqual({row["scheme_name"] for row in self.db.fetch_sip_orders()}, {"Example Index Fund", "Example Bond Fund"})

    def test_public_basket_contributes_once_and_admin_can_remove_it(self):
        self.db.add_sip_orders("survey investor", [
            {"scheme_code": code, "scheme_name": "Old scheme name", "amount": 5000, "frequency": "Monthly", "start_date": "2025-01-01"}
            for code in ("1001", "1002")
        ])
        public = self.app.test_client()
        token = self.token(public, "/share-basket")
        for codes in (["1001", "1001"], ["9999"], ["<script>"]):
            self.assertEqual(public.post("/share-basket", data={"csrf_token": token, "scheme_codes": codes}).status_code, 200)
            self.assertEqual(self.db.fetch_public_baskets(), [])
        valid = {"csrf_token": token, "scheme_codes": ["1001", "1002"]}
        self.assertEqual(public.post("/share-basket", data=valid).status_code, 302)
        self.assertEqual(public.post("/share-basket", data=valid).status_code, 302)
        baskets = self.db.fetch_public_baskets()
        self.assertEqual(len(baskets), 1)
        self.assertEqual(len(self.db.fetch_baskets()), 2)
        self.assertIn(b"Example Bond Fund, Example Index Fund", public.get("/recommendations").data)
        path = f"/admin/public-baskets/{baskets[0]['id']}/delete"
        self.assertEqual(public.post(path, data={"csrf_token": token}).status_code, 403)
        admin_token = self.login()
        self.assertIn(b"Example Index Fund", self.client.get("/admin/public-baskets").data)
        self.assertEqual(self.client.post(path, data={"csrf_token": admin_token}).status_code, 302)
        self.assertEqual(self.db.fetch_public_baskets(), [])
        self.assertEqual(len(self.db.fetch_baskets()), 1)
        self.assertNotIn(b"Example Bond Fund, Example Index Fund", public.get("/recommendations").data)


if __name__ == "__main__":
    unittest.main()
