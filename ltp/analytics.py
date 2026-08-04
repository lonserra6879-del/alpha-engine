from datetime import date
import numpy as np
import pandas as pd

def enrich(df: pd.DataFrame) -> pd.DataFrame:
    x = df.copy()
    if x.empty:
        for col in ["is_closed","pnl","return_pct","holding_days","adherence_score"]:
            x[col] = pd.Series(dtype=float)
        return x
    for col in ["entry_price","quantity","exit_price","stop_price","target_price"]:
        x[col] = pd.to_numeric(x[col], errors="coerce")
    x["entry_date"] = pd.to_datetime(x["entry_date"], errors="coerce")
    x["exit_date"] = pd.to_datetime(x["exit_date"], errors="coerce")
    x["archived"] = x["archived"].fillna(False).astype(bool)
    x["is_closed"] = x["status"].astype(str).str.lower().eq("closed") & x["exit_price"].notna()
    x["pnl"] = np.where(
        x["is_closed"],
        (x["exit_price"] - x["entry_price"]) * x["quantity"],
        np.nan,
    )
    x["return_pct"] = np.where(
        x["is_closed"],
        x["exit_price"] / x["entry_price"] - 1,
        np.nan,
    )
    end_dates = x["exit_date"].fillna(pd.Timestamp(date.today()))
    x["holding_days"] = (end_dates - x["entry_date"]).dt.days.clip(lower=0)
    x["adherence_score"] = x["plan_followed"].map(
        {"Yes":100,"Mostly":75,"Partly":50,"No":0}
    ).fillna(50)
    return x

def summary(df: pd.DataFrame):
    x = enrich(df)
    closed = x.loc[x["is_closed"].fillna(False).astype(bool)].copy()
    return {
        "closed": len(closed),
        "pnl": 0.0 if closed.empty else float(closed["pnl"].sum()),
        "win_rate": np.nan if closed.empty else float((closed["pnl"] > 0).mean()),
        "adherence": np.nan if x.empty else float(x["adherence_score"].mean()),
    }

def curve(df: pd.DataFrame):
    x = enrich(df)
    if x.empty:
        return pd.DataFrame(columns=["Date","Cumulative P&L"])
    closed = (
        x.loc[x["is_closed"].fillna(False).astype(bool)]
        .copy().dropna(subset=["exit_date"]).sort_values("exit_date")
    )
    if closed.empty:
        return pd.DataFrame(columns=["Date","Cumulative P&L"])
    closed["Cumulative P&L"] = closed["pnl"].fillna(0).cumsum()
    return closed[["exit_date","Cumulative P&L"]].rename(columns={"exit_date":"Date"})
