from __future__ import annotations

import os
from functools import lru_cache
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

DEFAULT_ADMIN_USERNAME = os.getenv("MF_ADMIN_USERNAME", "admin")
DEFAULT_ADMIN_PASSWORD = os.getenv("MF_ADMIN_PASSWORD", "admin123")


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
        is_sqlite = engine.dialect.name == "sqlite"
        id_column = "INTEGER PRIMARY KEY AUTOINCREMENT" if is_sqlite else "BIGSERIAL PRIMARY KEY"
        amount_type = "REAL" if is_sqlite else "DOUBLE PRECISION"
        inspector = inspect(connection)
        if not inspector.has_table("admins"):
            if not is_sqlite:
                connection.execute(text("DROP SEQUENCE IF EXISTS admins_id_seq CASCADE"))
            connection.execute(
                text(
                    f"""
                    CREATE TABLE admins (
                        id {id_column},
                        username TEXT UNIQUE NOT NULL,
                        password_hash TEXT NOT NULL
                    )
                    """
                )
            )

        if not inspector.has_table("schemes"):
            connection.execute(
                text(
                    """
                    CREATE TABLE schemes (
                        scheme_code TEXT PRIMARY KEY,
                        scheme_name TEXT NOT NULL,
                        isin_growth TEXT,
                        isin_div_reinvestment TEXT,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            )

        connection.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_schemes_name
                ON schemes(scheme_name)
                """
            )
        )

        if not inspector.has_table("sync_meta"):
            connection.execute(
                text(
                    """
                    CREATE TABLE sync_meta (
                        cache_key TEXT PRIMARY KEY,
                        cache_value TEXT NOT NULL,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            )

        if not inspector.has_table("sip_orders"):
            if not is_sqlite:
                connection.execute(text("DROP SEQUENCE IF EXISTS sip_orders_id_seq CASCADE"))
            connection.execute(
                text(
                    f"""
                    CREATE TABLE sip_orders (
                        id {id_column},
                        investor_name TEXT NOT NULL,
                        investor_contact TEXT,
                        scheme_code TEXT NOT NULL,
                        scheme_name TEXT NOT NULL,
                        amount {amount_type} NOT NULL,
                        frequency TEXT NOT NULL,
                        start_date TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            )

        if not inspector.has_table("fund_admin_details"):
            connection.execute(
                text(
                    """
                    CREATE TABLE fund_admin_details (
                        scheme_code TEXT PRIMARY KEY,
                        scheme_name TEXT NOT NULL,
                        fund_manager TEXT,
                        aum TEXT,
                        lock_in_period TEXT,
                        expense_ratio TEXT,
                        risk_level TEXT,
                        notes TEXT,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            )

        inspector = inspect(connection)
        admin_columns = {column["name"] for column in inspector.get_columns("admins")}

        if "password_hash" not in admin_columns:
            connection.execute(text("ALTER TABLE admins ADD COLUMN password_hash TEXT"))
            admin_columns.add("password_hash")

        if "password" in admin_columns:
            legacy_admins = connection.execute(
                text(
                    """
                    SELECT id, password
                    FROM admins
                    WHERE password_hash IS NULL OR password_hash = ''
                    """
                )
            ).fetchall()
            for admin in legacy_admins:
                connection.execute(
                    text("UPDATE admins SET password_hash = :password_hash WHERE id = :admin_id"),
                    {
                        "password_hash": generate_password_hash(admin.password),
                        "admin_id": admin.id,
                    },
                )

        admin_row = connection.execute(
            text("SELECT id FROM admins WHERE username = :username"),
            {"username": DEFAULT_ADMIN_USERNAME},
        ).fetchone()
        if admin_row is None:
            params = {
                "username": DEFAULT_ADMIN_USERNAME,
                "password_hash": generate_password_hash(DEFAULT_ADMIN_PASSWORD),
            }
            if "password" in admin_columns:
                params["password"] = DEFAULT_ADMIN_PASSWORD
                connection.execute(
                    text(
                        """
                        INSERT INTO admins (username, password, password_hash)
                        VALUES (:username, :password, :password_hash)
                        """
                    ),
                    params,
                )
            else:
                connection.execute(
                    text(
                        """
                        INSERT INTO admins (username, password_hash)
                        VALUES (:username, :password_hash)
                        """
                    ),
                    params,
                )


def authenticate_admin(username: str, password: str) -> bool:
    with get_engine().connect() as connection:
        row = connection.execute(
            text("SELECT password_hash FROM admins WHERE username = :username"),
            {"username": username},
        ).fetchone()
    return bool(row and check_password_hash(row.password_hash, password))


def create_admin_user(username: str, password: str) -> tuple[bool, str]:
    engine = get_engine()
    inspector = inspect(engine)
    admin_columns = {column["name"] for column in inspector.get_columns("admins")}

    with engine.begin() as connection:
        existing = connection.execute(
            text("SELECT id FROM admins WHERE username = :username"),
            {"username": username},
        ).fetchone()
        if existing:
            return False, "An admin with that username already exists."

        params = {
            "username": username,
            "password_hash": generate_password_hash(password),
        }
        try:
            if "password" in admin_columns:
                params["password"] = password
                connection.execute(
                    text(
                        """
                        INSERT INTO admins (username, password, password_hash)
                        VALUES (:username, :password, :password_hash)
                        """
                    ),
                    params,
                )
            else:
                connection.execute(
                    text(
                        """
                        INSERT INTO admins (username, password_hash)
                        VALUES (:username, :password_hash)
                        """
                    ),
                    params,
                )
        except IntegrityError:
            return False, "An admin with that username already exists."
    return True, "Admin user created successfully."


def update_admin_password(username: str, current_password: str, new_password: str) -> bool:
    engine = get_engine()
    inspector = inspect(engine)
    admin_columns = {column["name"] for column in inspector.get_columns("admins")}

    with engine.begin() as connection:
        row = connection.execute(
            text("SELECT password_hash FROM admins WHERE username = :username"),
            {"username": username},
        ).fetchone()
        if not row or not check_password_hash(row.password_hash, current_password):
            return False

        params = {
            "username": username,
            "password_hash": generate_password_hash(new_password),
        }
        if "password" in admin_columns:
            params["password"] = new_password
            connection.execute(
                text(
                    """
                    UPDATE admins
                    SET password = :password, password_hash = :password_hash
                    WHERE username = :username
                    """
                ),
                params,
            )
        else:
            connection.execute(
                text(
                    """
                    UPDATE admins
                    SET password_hash = :password_hash
                    WHERE username = :username
                    """
                ),
                params,
            )
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
    with get_engine().connect() as connection:
        if query:
            wildcard = f"%{query.lower()}%"
            prefix = f"{query.lower()}%"
            rows = connection.execute(
                text(
                    """
                    SELECT scheme_code, scheme_name, isin_growth, isin_div_reinvestment
                    FROM schemes
                    WHERE lower(scheme_name) LIKE :wildcard
                       OR scheme_code LIKE :wildcard
                    ORDER BY
                        CASE
                            WHEN lower(scheme_name) = :exact_match THEN 0
                            WHEN lower(scheme_name) LIKE :prefix_match THEN 1
                            ELSE 2
                        END,
                        scheme_name ASC
                    """
                ),
                {
                    "wildcard": wildcard,
                    "exact_match": query.lower(),
                    "prefix_match": prefix,
                },
            ).fetchall()
        else:
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


def add_sip_orders(investor_name: str, investor_contact: str, allocations: List[Dict[str, str]]) -> None:
    payload = [
        {
            "investor_name": investor_name,
            "investor_contact": investor_contact,
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
                    investor_contact,
                    scheme_code,
                    scheme_name,
                    amount,
                    frequency,
                    start_date
                ) VALUES (
                    :investor_name,
                    :investor_contact,
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
                SELECT id, investor_name, investor_contact, scheme_code, scheme_name,
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
        rows = connection.execute(
            text(
                """
                SELECT investor_name, scheme_name
                FROM sip_orders
                ORDER BY investor_name ASC, scheme_name ASC
                """
            )
        ).fetchall()

    baskets: Dict[str, List[str]] = {}
    for row in rows:
        investor_name = row.investor_name
        scheme_name = row.scheme_name
        baskets.setdefault(investor_name, [])
        if scheme_name not in baskets[investor_name]:
            baskets[investor_name].append(scheme_name)
    return list(baskets.values())
