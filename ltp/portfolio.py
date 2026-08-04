import numpy as np
import pandas as pd

def build_live_portfolio(open_trades, quotes):
    rows = []
    for _, row in open_trades.iterrows():
        ticker = str(row["ticker"]).upper()
        entry = float(row["entry_price"])
        qty = float(row["quantity"])
        current = quotes.get(ticker)
        stop = None if pd.isna(row.get("stop_price")) else float(row["stop_price"])
        target = None if pd.isna(row.get("target_price")) else float(row["target_price"])
        cost = entry * qty
        value = None if current is None else current * qty
        pnl = None if value is None else value - cost
        ret = None if current is None else current / entry - 1
        stop_dist = None if current is None or stop is None else (current - stop) / current
        target_dist = None if current is None or target is None else (target - current) / current
        risk = None if current is None or stop is None else max(current - stop, 0) * qty
        reward = None if current is None or target is None else max(target - current, 0) * qty
        rr = None if risk is None or reward is None or risk <= 0 else reward / risk
        rows.append({
            "Ticker": ticker,
            "Account": row["account_type"],
            "Strategy": row["strategy"],
            "Quantity": qty,
            "Entry": entry,
            "Current": current,
            "Cost basis": cost,
            "Market value": value,
            "Unrealized P&L": pnl,
            "Return": ret,
            "Days held": int(row["holding_days"]),
            "Stop": stop,
            "Target": target,
            "Distance to stop": stop_dist,
            "Distance to target": target_dist,
            "Remaining R/R": rr,
        })
    return pd.DataFrame(rows)

def portfolio_totals(portfolio):
    if portfolio.empty:
        return {"cost_basis":0.0, "market_value":0.0, "unrealized":0.0, "return_pct":np.nan}
    cost = float(portfolio["Cost basis"].fillna(0).sum())
    value = float(portfolio["Market value"].fillna(0).sum())
    pnl = float(portfolio["Unrealized P&L"].fillna(0).sum())
    return {"cost_basis":cost, "market_value":value, "unrealized":pnl,
            "return_pct":np.nan if cost <= 0 else value/cost-1}
