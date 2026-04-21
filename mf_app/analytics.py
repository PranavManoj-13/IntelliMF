from __future__ import annotations

from typing import Dict, List

import pandas as pd
from mlxtend.frequent_patterns import association_rules, fpgrowth
from mlxtend.preprocessing import TransactionEncoder


FREQUENCIES = ["Daily", "Weekly", "Bi-Weekly", "Monthly"]


def normalize_baskets(baskets: List[List[str]]) -> List[List[str]]:
    normalized = []
    for basket in baskets:
        cleaned = sorted({str(item).strip() for item in basket if str(item).strip()})
        if cleaned:
            normalized.append(cleaned)
    return normalized


def generate_sip_dates(
    frequency: str,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    nav_history: pd.DataFrame,
) -> pd.DatetimeIndex:
    if frequency == "Daily":
        available_dates = nav_history[
            (nav_history["date"] >= start_date) & (nav_history["date"] <= end_date)
        ]["date"]
        return pd.DatetimeIndex(available_dates.tolist())

    dates = []
    current = pd.Timestamp(start_date)
    end_date = pd.Timestamp(end_date)

    while current <= end_date:
        dates.append(current)
        if frequency == "Daily":
            current += pd.Timedelta(days=1)
        elif frequency == "Weekly":
            current += pd.Timedelta(days=7)
        elif frequency == "Bi-Weekly":
            current += pd.Timedelta(days=14)
        elif frequency == "Monthly":
            current += pd.DateOffset(months=1)
        else:
            break

    return pd.DatetimeIndex(dates)


def map_investments_to_nav(nav_history: pd.DataFrame, scheduled_dates: pd.DatetimeIndex) -> pd.DataFrame:
    nav_frame = nav_history.sort_values("date")[["date", "nav"]].copy()
    targets = pd.DataFrame({"scheduled_date": scheduled_dates}).sort_values("scheduled_date")
    aligned = pd.merge_asof(
        targets,
        nav_frame,
        left_on="scheduled_date",
        right_on="date",
        direction="forward",
    )
    aligned = aligned.dropna(subset=["date", "nav"]).copy()
    aligned["scheduled_date"] = pd.to_datetime(aligned["scheduled_date"])
    aligned["date"] = pd.to_datetime(aligned["date"])
    aligned["nav"] = pd.to_numeric(aligned["nav"], errors="coerce")
    return aligned.dropna(subset=["nav"])


def allocate_monthly_budget(investments: pd.DataFrame, monthly_amount: float) -> pd.DataFrame:
    investments = investments.copy()
    investments["month_bucket"] = investments["scheduled_date"].dt.to_period("M").astype(str)
    monthly_counts = investments.groupby("month_bucket")["scheduled_date"].transform("count")
    investments["investment_amount"] = float(monthly_amount) / monthly_counts
    return investments


def build_daily_portfolio(nav_history: pd.DataFrame, investment_events: pd.DataFrame) -> pd.DataFrame:
    daily_frame = nav_history.copy().sort_values("date")
    event_rollup = (
        investment_events.groupby("date", as_index=False)[["units_bought", "investment_amount"]]
        .sum()
        .rename(columns={"date": "event_date"})
    )
    daily_frame = daily_frame.merge(event_rollup, left_on="date", right_on="event_date", how="left")
    daily_frame["units_bought"] = daily_frame["units_bought"].fillna(0.0)
    daily_frame["investment_amount"] = daily_frame["investment_amount"].fillna(0.0)
    daily_frame["cumulative_units"] = daily_frame["units_bought"].cumsum()
    daily_frame["invested_amount"] = daily_frame["investment_amount"].cumsum()
    daily_frame["portfolio_value"] = daily_frame["nav"] * daily_frame["cumulative_units"]
    daily_frame["gain_loss"] = daily_frame["portfolio_value"] - daily_frame["invested_amount"]
    return daily_frame[
        ["date", "nav", "units_bought", "investment_amount", "cumulative_units", "invested_amount", "portfolio_value", "gain_loss"]
    ]


def simulate_sip(
    nav_history: pd.DataFrame,
    amount: float,
    frequency: str,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> Dict[str, object]:
    if nav_history.empty:
        return {"summary": {}, "investments": [], "daily_series": []}

    nav_history = nav_history.sort_values("date").copy()
    start_date = max(pd.Timestamp(start_date), pd.Timestamp(nav_history["date"].min()))
    end_date = min(pd.Timestamp(end_date), pd.Timestamp(nav_history["date"].max()))

    if start_date > end_date:
        return {"summary": {}, "investments": [], "daily_series": []}

    scheduled_dates = generate_sip_dates(frequency, start_date, end_date, nav_history)
    if scheduled_dates.empty:
        scheduled_dates = pd.DatetimeIndex([start_date])

    investments = map_investments_to_nav(nav_history, scheduled_dates)
    if investments.empty:
        return {"summary": {}, "investments": [], "daily_series": []}

    investments = allocate_monthly_budget(investments, float(amount))
    investments["units_bought"] = investments["investment_amount"] / investments["nav"]
    investments["cumulative_units"] = investments["units_bought"].cumsum()

    portfolio_window = nav_history[
        (nav_history["date"] >= investments["date"].min()) & (nav_history["date"] <= end_date)
    ].copy()
    daily_portfolio = build_daily_portfolio(portfolio_window, investments)
    final_row = daily_portfolio.iloc[-1]

    summary = {
        "frequency": frequency,
        "installments": int(len(investments)),
        "total_invested": round(float(investments["investment_amount"].sum()), 2),
        "units_held": round(float(investments["units_bought"].sum()), 6),
        "current_value": round(float(final_row["portfolio_value"]), 2),
        "absolute_return": round(float(final_row["gain_loss"]), 2),
        "return_pct": round(
            (float(final_row["gain_loss"]) / float(final_row["invested_amount"]) * 100)
            if float(final_row["invested_amount"]) > 0
            else 0.0,
            2,
        ),
    }

    investment_records = [
        {
            "scheduled_date": row["scheduled_date"].strftime("%Y-%m-%d"),
            "execution_date": row["date"].strftime("%Y-%m-%d"),
            "month_bucket": row["month_bucket"],
            "nav": round(float(row["nav"]), 4),
            "investment_amount": round(float(row["investment_amount"]), 2),
            "units_bought": round(float(row["units_bought"]), 6),
            "cumulative_units": round(float(row["cumulative_units"]), 6),
        }
        for _, row in investments.iterrows()
    ]

    daily_records = [
        {
            "date": row["date"].strftime("%Y-%m-%d"),
            "nav": round(float(row["nav"]), 4),
            "cumulative_units": round(float(row["cumulative_units"]), 6),
            "invested_amount": round(float(row["invested_amount"]), 2),
            "portfolio_value": round(float(row["portfolio_value"]), 2),
            "gain_loss": round(float(row["gain_loss"]), 2),
        }
        for _, row in daily_portfolio.iterrows()
    ]

    return {
        "summary": summary,
        "investments": investment_records,
        "daily_series": daily_records,
    }


def compare_sip_frequencies(
    nav_history: pd.DataFrame,
    amount: float,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> Dict[str, object]:
    comparisons = []
    for frequency in FREQUENCIES:
        result = simulate_sip(nav_history, amount, frequency, start_date, end_date)
        if result["summary"]:
            comparisons.append(result["summary"])

    if not comparisons:
        return {"best_frequency": "Monthly", "comparisons": [], "assumption": ""}

    best = sorted(
        comparisons,
        key=lambda item: (item["return_pct"], item["current_value"], -item["installments"]),
        reverse=True,
    )[0]
    return {
        "best_frequency": best["frequency"],
        "comparisons": comparisons,
        "assumption": (
            "Optimal frequency is selected using the highest return percentage while keeping the total SIP amount per month constant across frequencies."
        ),
    }


def mine_frequent_itemsets(baskets: List[List[str]]) -> tuple[List[Dict[str, object]], List[Dict[str, object]]]:
    baskets = normalize_baskets(baskets)
    if not baskets:
        return [], []

    encoder = TransactionEncoder()
    encoded = encoder.fit(baskets).transform(baskets)
    basket_frame = pd.DataFrame(encoded, columns=encoder.columns_)

    # Require support from at least two baskets wherever possible so one
    # investor basket does not dominate "frequently bought together" output.
    min_support = max(0.1, 2 / len(baskets)) if len(baskets) > 1 else 1.0
    itemsets = fpgrowth(basket_frame, min_support=min_support, use_colnames=True)
    if itemsets.empty:
        return [], []

    itemset_rows = [
        {
            "itemsets": ", ".join(sorted(items)),
            "support": round(float(support), 4),
        }
        for support, items in zip(itemsets["support"], itemsets["itemsets"])
    ]
    itemset_rows = sorted(itemset_rows, key=lambda item: (-item["support"], item["itemsets"]))

    if itemsets["itemsets"].map(len).max() < 2:
        return itemset_rows, []

    try:
        rules = association_rules(itemsets, metric="confidence", min_threshold=0.3)
    except ValueError:
        return itemset_rows, []

    if rules.empty:
        return itemset_rows, []

    rule_rows = []
    for _, row in rules.iterrows():
        rule_rows.append(
            {
                "antecedents": ", ".join(sorted(row["antecedents"])),
                "consequents": ", ".join(sorted(row["consequents"])),
                "support": round(float(row["support"]), 4),
                "confidence": round(float(row["confidence"]), 4),
                "lift": round(float(row["lift"]), 4),
            }
        )
    rule_rows = sorted(rule_rows, key=lambda item: (-item["lift"], -item["confidence"]))

    return itemset_rows, rule_rows
