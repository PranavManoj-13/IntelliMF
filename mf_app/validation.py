"""Validation shared by public and admin forms."""
import math
import re
from datetime import date

from mf_app.analytics import FREQUENCIES
from mf_app.db import fetch_scheme_by_code


def amount_value(raw, label="SIP amount", allow_zero=False, maximum=1_000_000_000):
    try:
        value = float(raw)
    except (ValueError, TypeError):
        raise ValueError(f"Enter a valid {label}.") from None
    if not math.isfinite(value) or value < 0 or (value == 0 and not allow_zero) or value > maximum:
        raise ValueError(f"Enter a {'non-negative' if allow_zero else 'positive'}, finite {label} up to {maximum:,}.")
    return value


def date_value(raw):
    if not isinstance(raw, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        raise ValueError("Use a valid date in YYYY-MM-DD format.")
    try:
        value = date.fromisoformat(raw)
    except ValueError:
        raise ValueError("Enter a valid calendar date.") from None
    if value.year < 1900 or value.year > 2100:
        raise ValueError("Choose a date between 1900 and 2100.")
    return value


def frequency_value(raw):
    if raw not in FREQUENCIES:
        raise ValueError("Choose Daily, Weekly, Bi-Weekly, or Monthly.")
    return raw


def scheme_value(code):
    if not re.fullmatch(r"\d{1,12}", code or ""):
        raise ValueError("Choose a valid fund from the search results.")
    scheme = fetch_scheme_by_code(code)
    if not scheme:
        raise ValueError("A selected fund is no longer in the catalogue. Search and select it again.")
    return scheme


def selected_funds(codes):
    if not 1 <= len(codes) <= 20:
        raise ValueError("Choose between 1 and 20 funds.")
    if len(set(codes)) != len(codes):
        raise ValueError("Each fund can only appear once in a basket.")
    return [scheme_value(code) for code in codes]


def order_allocations(form):
    values = form.getlist("selected_schemes")
    # Accept legacy code|||name cart values, but always use the database's name.
    codes = [value.split("|||", 1)[0] for value in values]
    schemes = selected_funds(codes)
    allocations = []
    for scheme in schemes:
        code = scheme["scheme_code"]
        allocations.append({
            "scheme_code": code, "scheme_name": scheme["scheme_name"],
            "amount": amount_value(form.get(f"amount_{code}")),
            "frequency": frequency_value(form.get(f"frequency_{code}")),
            "start_date": date_value(form.get(f"start_date_{code}")).isoformat(),
        })
    return allocations


def metadata_values(form):
    scheme = scheme_value(form.get("scheme_code", ""))
    result = {"scheme_code": scheme["scheme_code"], "scheme_name": scheme["scheme_name"]}
    for key, limit in [("fund_manager", 200), ("lock_in_period", 100), ("risk_level", 100), ("notes", 2000)]:
        value = form.get(key, "").strip()
        if "\x00" in value:
            raise ValueError("Remove invalid characters from the metadata fields.")
        if len(value) > limit:
            raise ValueError(f"{key.replace('_', ' ').capitalize()} must be at most {limit} characters.")
        result[key] = value
    for key, maximum in [("aum", 1_000_000_000), ("expense_ratio", 100)]:
        raw = form.get(key, "").strip()
        result[key] = str(amount_value(raw, key.replace('_', ' '), allow_zero=True, maximum=maximum)) if raw else ""
    return result
