from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import pandas as pd
import requests

from mf_app.db import get_last_scheme_sync, get_scheme_count, replace_schemes, search_schemes


logger = logging.getLogger(__name__)


class MFAPIUnavailable(Exception):
    """The upstream API could not provide usable fund data."""


@dataclass
class SchemeDetails:
    scheme_code: str
    scheme_name: str
    fund_house: str
    scheme_type: str
    scheme_category: str
    current_nav: float
    current_date: pd.Timestamp
    nav_history: pd.DataFrame
    actual_nav_history: pd.DataFrame

    def nav_chart_points(self) -> List[Dict[str, float]]:
        return [
            {"date": row["date"].strftime("%Y-%m-%d"), "nav": round(float(row["nav"]), 4)}
            for _, row in self.nav_history.iterrows()
        ]


class MFAPIClient:
    def __init__(self) -> None:
        self.base_url = "https://api.mfapi.in"
        self.session = requests.Session()

    def ensure_scheme_cache(self) -> None:
        cached_count = get_scheme_count()
        last_sync = get_last_scheme_sync()
        last_sync_ts = pd.to_datetime(last_sync, errors="coerce") if last_sync else pd.NaT
        stale_cache = pd.isna(last_sync_ts) or (pd.Timestamp.utcnow().tz_localize(None) - last_sync_ts) > pd.Timedelta(hours=12)
        if cached_count and not stale_cache:
            return

        try:
            response = self.session.get(f"{self.base_url}/mf", timeout=45)
            response.raise_for_status()
            schemes = response.json()
            if not isinstance(schemes, list) or not schemes or any(not isinstance(item, dict) or not str(item.get("schemeCode", "")).isdigit() or not isinstance(item.get("schemeName"), str) or not item["schemeName"].strip() for item in schemes):
                raise ValueError("Invalid scheme catalogue")
            replace_schemes({str(item["schemeCode"]): item for item in schemes}.values())
        except (requests.RequestException, ValueError):
            logger.warning("Scheme refresh failed; using cached catalogue.")
            if cached_count == 0:
                fallback = Path(__file__).resolve().parent.parent / "data/raw/Schemes-List.csv"
                if fallback.exists():
                    frame = pd.read_csv(fallback)
                    replace_schemes(frame.fillna("").to_dict(orient="records"))
                else:
                    raise MFAPIUnavailable("The fund catalogue is temporarily unavailable.") from None

    def search_schemes(self, query: str) -> List[Dict[str, str]]:
        self.ensure_scheme_cache()
        return search_schemes(query)

    def fetch_scheme_details(self, scheme_code: str) -> SchemeDetails:
        try:
            response = self.session.get(f"{self.base_url}/mf/{scheme_code}", timeout=20)
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict) or not isinstance(payload.get("meta"), dict) or not isinstance(payload.get("data"), list):
                raise ValueError("Malformed fund details")
            if not all(isinstance(record, dict) for record in payload["data"]):
                raise ValueError("Malformed NAV observations")
            meta = payload["meta"]
            nav_history = pd.DataFrame(payload["data"])
            if nav_history.empty:
                nav_history = pd.DataFrame(columns=["date", "nav"])
            nav_history["date"] = pd.to_datetime(nav_history["date"], format="%d-%m-%Y", errors="coerce")
            nav_history["nav"] = pd.to_numeric(nav_history["nav"], errors="coerce")
            nav_history = nav_history.dropna(subset=["date", "nav"])
            valid_nav = nav_history["nav"].map(lambda nav: math.isfinite(nav) and nav > 0).astype(bool)
            nav_history = nav_history.loc[valid_nav]
            nav_history = nav_history[nav_history["date"] <= pd.Timestamp.now().normalize()]
            nav_history = nav_history.sort_values("date").drop_duplicates("date").reset_index(drop=True)
        except (requests.RequestException, ValueError, KeyError, TypeError):
            logger.warning("MFAPI fund details unavailable for scheme %s", scheme_code)
            raise MFAPIUnavailable("Fund details are temporarily unavailable. Please try again shortly.") from None
        actual_nav_history = nav_history.copy()
        nav_history = self.extend_nav_history_to_today(actual_nav_history)

        current_nav = float(actual_nav_history.iloc[-1]["nav"]) if not actual_nav_history.empty else 0.0
        current_date = actual_nav_history.iloc[-1]["date"] if not actual_nav_history.empty else pd.NaT

        return SchemeDetails(
            scheme_code=str(meta.get("scheme_code", scheme_code)),
            scheme_name=meta.get("scheme_name", "Unknown Scheme"),
            fund_house=meta.get("fund_house", "Unknown Fund House"),
            scheme_type=meta.get("scheme_type", "Unknown Type"),
            scheme_category=meta.get("scheme_category", "Unknown Category"),
            current_nav=current_nav,
            current_date=current_date,
            nav_history=nav_history,
            actual_nav_history=actual_nav_history,
        )

    def extend_nav_history_to_today(self, nav_history: pd.DataFrame) -> pd.DataFrame:
        if nav_history.empty:
            return nav_history

        latest_date = pd.Timestamp(nav_history.iloc[-1]["date"]).normalize()
        today = pd.Timestamp.now().normalize()
        if latest_date >= today:
            return nav_history

        future_dates = pd.date_range(start=latest_date + pd.Timedelta(days=1), end=today, freq="D")
        if future_dates.empty:
            return nav_history

        latest_nav = float(nav_history.iloc[-1]["nav"])
        extension = pd.DataFrame({"date": future_dates, "nav": latest_nav})
        extended = pd.concat([nav_history, extension], ignore_index=True)
        return extended.sort_values("date").reset_index(drop=True)


def compute_trailing_returns(nav_history: pd.DataFrame) -> List[Dict[str, float]]:
    if nav_history.empty:
        return []

    latest = nav_history.iloc[-1]
    latest_date = latest["date"]
    latest_nav = float(latest["nav"])
    periods = {
        "1 Month": latest_date - pd.DateOffset(months=1),
        "3 Months": latest_date - pd.DateOffset(months=3),
        "6 Months": latest_date - pd.DateOffset(months=6),
        "1 Year": latest_date - pd.DateOffset(years=1),
        "3 Years": latest_date - pd.DateOffset(years=3),
        "5 Years": latest_date - pd.DateOffset(years=5),
        "Since Inception": nav_history.iloc[0]["date"],
    }

    rows: List[Dict[str, float]] = []
    for label, target_date in periods.items():
        anchor = nav_history[nav_history["date"] <= target_date]
        if anchor.empty:
            anchor = nav_history.iloc[[0]]
        start_nav = float(anchor.iloc[-1]["nav"])
        if start_nav <= 0:
            continue
        returns_pct = ((latest_nav - start_nav) / start_nav) * 100
        rows.append({"period": label, "return_pct": round(returns_pct, 2)})

    return rows
