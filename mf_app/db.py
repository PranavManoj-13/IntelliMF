from __future__ import annotations

import os
import re
import secrets
import time
from uuid import uuid4
from functools import lru_cache
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash



def normalize_database_url(raw_url: Optional[str]) -> str:
    if not raw_url:
        raise ValueError("DATABASE_URL is not set")

    if raw_url.startswith("postgres://"):
        return raw_url.replace("postgres://", "postgresql+psycopg://", 1)

    if raw_url.startswith("postgresql://") and "+" not in raw_url.split("://", 1)[0]:
        return raw_url.replace("postgresql://", "postgresql+psycopg://", 1)

    return raw_url


DATABASE_URL = normalize_database_url(os.getenv("DATABASE_URL"))


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
    return create_engine(
        DATABASE_URL,
        future=True,
        pool_pre_ping=True,
        pool_recycle=300,
        connect_args=connect_args,
    )


def row_to_dict(row: Any) -> Dict[str, Any]:
    return dict(row._mapping)


def init_db() -> None:
    engine = get_engine()
    with engine.begin() as connection:
        if engine.dialect.name == "postgresql":
            # Serialize schema setup when multiple Gunicorn workers start together.
            connection.execute(text("SELECT pg_advisory_xact_lock(1228746054)"))
        identity = "INTEGER PRIMARY KEY AUTOINCREMENT" if engine.dialect.name == "sqlite" else "BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY"
        tables = {
            "admins": f"id {identity}, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, session_version INTEGER NOT NULL DEFAULT 1",
            "schemes": "scheme_code TEXT PRIMARY KEY, scheme_name TEXT NOT NULL, isin_growth TEXT, isin_div_reinvestment TEXT, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
            "sync_meta": "cache_key TEXT PRIMARY KEY, cache_value TEXT NOT NULL, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
            "sip_orders": f"id {identity}, investor_name TEXT NOT NULL, scheme_code TEXT NOT NULL, scheme_name TEXT NOT NULL, amount DOUBLE PRECISION NOT NULL, frequency TEXT NOT NULL, start_date TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
            "fund_admin_details": "scheme_code TEXT PRIMARY KEY, scheme_name TEXT NOT NULL, fund_manager TEXT, aum TEXT, lock_in_period TEXT, expense_ratio TEXT, risk_level TEXT, notes TEXT, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
            "public_baskets": "id TEXT PRIMARY KEY, respondent_key TEXT UNIQUE NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
            "public_basket_items": "basket_id TEXT NOT NULL REFERENCES public_baskets(id) ON DELETE CASCADE, scheme_code TEXT NOT NULL, scheme_name TEXT NOT NULL, PRIMARY KEY (basket_id, scheme_code)",
            "request_limits": "bucket_key TEXT PRIMARY KEY, hits INTEGER NOT NULL, expires_at BIGINT NOT NULL",
        }
        for name, columns in tables.items():
            connection.execute(text(f"CREATE TABLE IF NOT EXISTS {name} ({columns})"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS idx_schemes_name ON schemes(scheme_name)"))
        columns = {column["name"] for column in inspect(connection).get_columns("admins")}
        if "password_hash" not in columns:
            connection.execute(text("ALTER TABLE admins ADD COLUMN password_hash TEXT"))
        if "session_version" not in columns:
            connection.execute(text("ALTER TABLE admins ADD COLUMN session_version INTEGER NOT NULL DEFAULT 1"))
        if "password" in columns:
            for row in connection.execute(text("SELECT id, password FROM admins WHERE password_hash IS NULL OR password_hash = ''")).fetchall():
                connection.execute(text("UPDATE admins SET password_hash = :hashed WHERE id = :id"), {"hashed": generate_password_hash(row.password or secrets.token_urlsafe(32)), "id": row.id})
            # Stop retaining plaintext passwords, including in legacy installations.
            connection.execute(text("ALTER TABLE admins DROP COLUMN password"))
        for row in connection.execute(text("SELECT id, password_hash FROM admins")).fetchall():
            if row.password_hash and not row.password_hash.startswith("!disabled") and check_password_hash(row.password_hash, "admin123"):
                connection.execute(text("UPDATE admins SET password_hash = '!disabled-default-password', session_version = session_version + 1 WHERE id = :id"), {"id": row.id})
        # Bootstrap only explicitly configured strong credentials. No built-in login.
        username = os.getenv("MF_ADMIN_USERNAME", "").strip()
        password = os.getenv("MF_ADMIN_PASSWORD", "")
        if username and username.isprintable() and len(username) <= 80 and 12 <= len(password) <= 256 and password != "admin123":
            connection.execute(text("INSERT INTO admins (username, password_hash) VALUES (:username, :hashed) ON CONFLICT (username) DO NOTHING"), {"username": username, "hashed": generate_password_hash(password)})


def verified_admin_session_version(username: str, password: str) -> Optional[int]:
    if not username or len(username) > 80 or not username.isprintable() or not password or len(password) > 256:
        return None
    with get_engine().connect() as connection:
        row = connection.execute(
            text("SELECT password_hash, session_version FROM admins WHERE username = :username"),
            {"username": username},
        ).fetchone()
    if row and row.password_hash and not row.password_hash.startswith("!disabled") and check_password_hash(row.password_hash, password):
        return row.session_version
    return None


def authenticate_admin(username: str, password: str) -> bool:
    return verified_admin_session_version(username, password) is not None


def get_admin_session_version(username: str) -> Optional[int]:
    with get_engine().connect() as connection:
        row = connection.execute(text("SELECT session_version FROM admins WHERE username = :username"), {"username": username}).fetchone()
    return row.session_version if row else None


def create_admin_user(username: str, password: str) -> tuple[bool, str]:
    if not username.strip() or len(username) > 80 or not username.isprintable() or not 12 <= len(password) <= 256:
        return False, "Use a username up to 80 characters and a password of 12–256 characters."
    try:
        with get_engine().begin() as connection:
            connection.execute(text("INSERT INTO admins (username, password_hash) VALUES (:username, :hashed)"), {"username": username.strip(), "hashed": generate_password_hash(password)})
    except IntegrityError:
        return False, "An admin with that username already exists."
    return True, "Admin user created successfully."


def set_admin_credentials(username: str, password: str) -> None:
    """Local CLI recovery/bootstrap; never exposed as a public route."""
    if not username.strip() or len(username) > 80 or not username.isprintable() or not 12 <= len(password) <= 256:
        raise ValueError("Use a username up to 80 characters and a password of 12–256 characters.")
    with get_engine().begin() as connection:
        connection.execute(text("INSERT INTO admins (username, password_hash) VALUES (:username, :hashed) ON CONFLICT (username) DO UPDATE SET password_hash = EXCLUDED.password_hash, session_version = admins.session_version + 1"), {"username": username.strip(), "hashed": generate_password_hash(password)})


def update_admin_password(username: str, current_password: str, new_password: str) -> bool:
    if not 12 <= len(new_password) <= 256 or not 1 <= len(current_password) <= 256:
        return False
    with get_engine().begin() as connection:
        row = connection.execute(text("SELECT password_hash FROM admins WHERE username = :username"), {"username": username}).fetchone()
        if not row or not row.password_hash or row.password_hash.startswith("!disabled") or not check_password_hash(row.password_hash, current_password):
            return False
        connection.execute(text("UPDATE admins SET password_hash = :hashed, session_version = session_version + 1 WHERE username = :username"), {"username": username, "hashed": generate_password_hash(new_password)})
    return True


def replace_schemes(schemes: Iterable[Dict[str, str]]) -> None:
    payload = [
        {
            "scheme_code": str(item.get("schemeCode", "")),
            "scheme_name": item.get("schemeName", ""),
            "isin_growth": item.get("isinGrowth", ""),
            "isin_div_reinvestment": item.get("isinDivReinvestment", ""),
        }
        for item in schemes
    ]

    with get_engine().begin() as connection:
        connection.execute(text("DELETE FROM schemes"))
        if payload:
            connection.execute(
                text(
                    """
                    INSERT INTO schemes (
                        scheme_code, scheme_name, isin_growth, isin_div_reinvestment
                    ) VALUES (
                        :scheme_code, :scheme_name, :isin_growth, :isin_div_reinvestment
                    )
                    """
                ),
                payload,
            )
        connection.execute(
            text(
                """
                INSERT INTO sync_meta (cache_key, cache_value, updated_at)
                VALUES ('schemes_last_sync', CAST(CURRENT_TIMESTAMP AS TEXT), CURRENT_TIMESTAMP)
                ON CONFLICT (cache_key) DO UPDATE SET
                    cache_value = EXCLUDED.cache_value,
                    updated_at = CURRENT_TIMESTAMP
                """
            )
        )


def fetch_all_schemes() -> List[Dict[str, Any]]:
    with get_engine().connect() as connection:
        rows = connection.execute(
            text(
                """
                SELECT scheme_code, scheme_name, isin_growth, isin_div_reinvestment
                FROM schemes
                ORDER BY scheme_name ASC
                """
            )
        ).fetchall()
    return [row_to_dict(row) for row in rows]


def fetch_scheme_by_code(scheme_code: str):
    with get_engine().connect() as connection:
        row = connection.execute(
            text(
                """
                SELECT scheme_code, scheme_name, isin_growth, isin_div_reinvestment
                FROM schemes
                WHERE scheme_code = :scheme_code
                """
            ),
            {"scheme_code": scheme_code},
        ).fetchone()
    return row_to_dict(row) if row else None


def search_schemes(query: str) -> List[Dict[str, Any]]:
    query = query.strip().lower()
    if not query:
        return fetch_all_schemes()

    # Match partial words in any order, even when punctuation separates them.
    terms = list(dict.fromkeys(re.findall(r"[^\W\d_]+|\d+", query)))
    if not terms:
        return []

    phrase = " ".join(terms)
    params = {"query": query, "prefix": f"{phrase}%", "phrase": f"%{phrase}%"}
    conditions = []
    for index, term in enumerate(terms):
        parameter = f"term_{index}"
        params[parameter] = f"%{term}%"
        name_match = f"lower(scheme_name) LIKE :{parameter}"
        if term.isdigit():
            conditions.append(f"({name_match} OR scheme_code LIKE :{parameter})")
        else:
            conditions.append(name_match)

    with get_engine().connect() as connection:
        rows = connection.execute(
            text(f"""
                SELECT scheme_code, scheme_name, isin_growth, isin_div_reinvestment
                FROM schemes
                WHERE {' AND '.join(conditions)}
                ORDER BY CASE
                    WHEN scheme_code = :query THEN 0
                    WHEN lower(scheme_name) = :query THEN 1
                    WHEN lower(scheme_name) LIKE :prefix THEN 2
                    WHEN lower(scheme_name) LIKE :phrase THEN 3
                    ELSE 4
                END, scheme_name ASC, scheme_code ASC
            """),
            params,
        ).fetchall()
    return [row_to_dict(row) for row in rows]


def get_scheme_count() -> int:
    with get_engine().connect() as connection:
        row = connection.execute(text("SELECT COUNT(*) AS count FROM schemes")).fetchone()
    return int(row.count) if row else 0


def get_last_scheme_sync() -> str:
    with get_engine().connect() as connection:
        row = connection.execute(
            text("SELECT updated_at FROM sync_meta WHERE cache_key = 'schemes_last_sync'")
        ).fetchone()
    return str(row.updated_at) if row else ""


def add_sip_orders(investor_name: str, allocations: List[Dict[str, str]]) -> None:
    payload = [
        {
            "investor_name": investor_name,
            "scheme_code": allocation["scheme_code"],
            "scheme_name": allocation["scheme_name"],
            "amount": allocation["amount"],
            "frequency": allocation["frequency"],
            "start_date": allocation["start_date"],
        }
        for allocation in allocations
    ]
    with get_engine().begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO sip_orders (
                    investor_name,
                    scheme_code,
                    scheme_name,
                    amount,
                    frequency,
                    start_date
                ) VALUES (
                    :investor_name,
                    :scheme_code,
                    :scheme_name,
                    :amount,
                    :frequency,
                    :start_date
                )
                """
            ),
            payload,
        )


def upsert_fund_admin_details(details: List[Dict[str, str]]) -> None:
    if not details:
        return

    payload = [
        {
            "scheme_code": item["scheme_code"],
            "scheme_name": item["scheme_name"],
            "fund_manager": item.get("fund_manager", ""),
            "aum": item.get("aum", ""),
            "lock_in_period": item.get("lock_in_period", ""),
            "expense_ratio": item.get("expense_ratio", ""),
            "risk_level": item.get("risk_level", ""),
            "notes": item.get("notes", ""),
        }
        for item in details
    ]

    with get_engine().begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO fund_admin_details (
                    scheme_code,
                    scheme_name,
                    fund_manager,
                    aum,
                    lock_in_period,
                    expense_ratio,
                    risk_level,
                    notes,
                    updated_at
                ) VALUES (
                    :scheme_code,
                    :scheme_name,
                    :fund_manager,
                    :aum,
                    :lock_in_period,
                    :expense_ratio,
                    :risk_level,
                    :notes,
                    CURRENT_TIMESTAMP
                )
                ON CONFLICT (scheme_code) DO UPDATE SET
                    scheme_name = EXCLUDED.scheme_name,
                    fund_manager = EXCLUDED.fund_manager,
                    aum = EXCLUDED.aum,
                    lock_in_period = EXCLUDED.lock_in_period,
                    expense_ratio = EXCLUDED.expense_ratio,
                    risk_level = EXCLUDED.risk_level,
                    notes = EXCLUDED.notes,
                    updated_at = CURRENT_TIMESTAMP
                """
            ),
            payload,
        )


def fetch_fund_admin_details(scheme_code: str):
    with get_engine().connect() as connection:
        row = connection.execute(
            text(
                """
                SELECT scheme_code, scheme_name, fund_manager, aum, lock_in_period,
                       expense_ratio, risk_level, notes, updated_at
                FROM fund_admin_details
                WHERE scheme_code = :scheme_code
                """
            ),
            {"scheme_code": scheme_code},
        ).fetchone()
    return row_to_dict(row) if row else None


def fetch_all_fund_admin_details() -> List[Dict[str, Any]]:
    with get_engine().connect() as connection:
        rows = connection.execute(
            text(
                """
                SELECT scheme_code, scheme_name, fund_manager, aum, lock_in_period,
                       expense_ratio, risk_level, notes, updated_at
                FROM fund_admin_details
                ORDER BY updated_at DESC, scheme_name ASC
                """
            )
        ).fetchall()
    return [row_to_dict(row) for row in rows]


def fetch_sip_orders() -> List[Dict[str, Any]]:
    with get_engine().connect() as connection:
        rows = connection.execute(
            text(
                """
                SELECT id, investor_name, scheme_code, scheme_name,
                       amount, frequency, start_date, created_at
                FROM sip_orders
                ORDER BY created_at DESC, investor_name ASC, scheme_name ASC
                """
            )
        ).fetchall()
    return [row_to_dict(row) for row in rows]


def delete_sip_order(order_id: int) -> bool:
    with get_engine().begin() as connection:
        result = connection.execute(
            text("DELETE FROM sip_orders WHERE id = :order_id"),
            {"order_id": order_id},
        )
    return result.rowcount > 0


def fetch_baskets() -> List[List[str]]:
    with get_engine().connect() as connection:
        rows = connection.execute(text("""
            SELECT 'admin' AS source, o.investor_name AS basket_id,
                   COALESCE(s.scheme_name, o.scheme_name) AS scheme_name
            FROM sip_orders o LEFT JOIN schemes s ON s.scheme_code = o.scheme_code
            UNION ALL
            SELECT 'public' AS source, i.basket_id,
                   COALESCE(s.scheme_name, i.scheme_name) AS scheme_name
            FROM public_basket_items i LEFT JOIN schemes s ON s.scheme_code = i.scheme_code
        """)).fetchall()
    baskets = {}
    for row in rows:
        baskets.setdefault((row.source, row.basket_id), set()).add(row.scheme_name)
    return [sorted(funds) for funds in baskets.values()]


def add_public_basket(respondent_key: str, schemes: List[Dict[str, str]]) -> bool:
    basket_id = str(uuid4())
    with get_engine().begin() as connection:
        result = connection.execute(text("INSERT INTO public_baskets (id, respondent_key) VALUES (:id, :key) ON CONFLICT (respondent_key) DO NOTHING"), {"id": basket_id, "key": respondent_key})
        if result.rowcount == 0:
            return False
        connection.execute(text("INSERT INTO public_basket_items (basket_id, scheme_code, scheme_name) VALUES (:basket_id, :scheme_code, :scheme_name)"), [{"basket_id": basket_id, "scheme_code": item["scheme_code"], "scheme_name": item["scheme_name"]} for item in schemes])
    return True


def has_public_basket(respondent_key: str) -> bool:
    with get_engine().connect() as connection:
        return connection.execute(text("SELECT id FROM public_baskets WHERE respondent_key = :key"), {"key": respondent_key}).fetchone() is not None


def fetch_public_baskets() -> List[Dict[str, Any]]:
    with get_engine().connect() as connection:
        rows = connection.execute(text("SELECT b.id, b.created_at, i.scheme_code, i.scheme_name FROM public_baskets b JOIN public_basket_items i ON i.basket_id = b.id ORDER BY b.created_at DESC, b.id, i.scheme_name")).fetchall()
    baskets = {}
    for row in rows:
        baskets.setdefault(row.id, {"id": row.id, "created_at": row.created_at, "schemes": []})["schemes"].append({"scheme_code": row.scheme_code, "scheme_name": row.scheme_name})
    return list(baskets.values())


def delete_public_basket(basket_id: str) -> bool:
    with get_engine().begin() as connection:
        connection.execute(text("DELETE FROM public_basket_items WHERE basket_id = :id"), {"id": basket_id})
        return connection.execute(text("DELETE FROM public_baskets WHERE id = :id"), {"id": basket_id}).rowcount > 0


def consume_request_limit(key: str, limit: int, seconds: int) -> bool:
    now = int(time.time())
    bucket = f"{key}:{now // seconds}"
    with get_engine().begin() as connection:
        connection.execute(text("DELETE FROM request_limits WHERE expires_at < :now"), {"now": now})
        row = connection.execute(text("INSERT INTO request_limits (bucket_key, hits, expires_at) VALUES (:key, 1, :expiry) ON CONFLICT (bucket_key) DO UPDATE SET hits = request_limits.hits + 1 RETURNING hits"), {"key": bucket, "expiry": now + seconds}).fetchone()
    return row.hits <= limit
