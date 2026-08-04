from __future__ import annotations

from datetime import date
import json
import numpy as np
import pandas as pd
import streamlit as st

try:
    import yfinance as yf
except Exception:
    yf = None


def _series(frame: pd.DataFrame, name: str) -> pd.Series:
    value = frame[name]
    if isinstance(value, pd.DataFrame):
        value = value.iloc[:, 0]
    return pd.to_numeric(value, errors="coerce")


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _atr(frame: pd.DataFrame, period: int = 14) -> pd.Series:
    high = _series(frame, "High")
    low = _series(frame, "Low")
    close = _series(frame, "Close")
    previous_close = close.shift(1)
    true_range = pd.concat(
        [
            high - low,
            (high - previous_close).abs(),
            (low - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return true_range.rolling(period).mean()


@st.cache_data(ttl=900, show_spinner=False)
def current_price(ticker: str) -> float | None:
    if yf is None or not ticker:
        return None
    try:
        data = yf.download(
            ticker,
            period="5d",
            interval="1d",
            progress=False,
            auto_adjust=False,
            threads=False,
        )
        if data.empty:
            return None
        return float(_series(data, "Close").dropna().iloc[-1])
    except Exception:
        return None


@st.cache_data(ttl=3600, show_spinner=False)
def reconstruct_case(ticker: str, entry_date_value: date) -> dict:
    if yf is None:
        return {
            "status": "Unavailable",
            "message": "The yfinance package is unavailable.",
        }

    start = pd.Timestamp(entry_date_value) - pd.Timedelta(days=420)
    end = pd.Timestamp(entry_date_value) + pd.Timedelta(days=8)

    try:
        data = yf.download(
            ticker,
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
            progress=False,
            auto_adjust=False,
            actions=False,
            threads=False,
        )

        if data.empty:
            return {
                "status": "Unavailable",
                "message": "No historical price data was returned.",
            }

        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        data.index = pd.to_datetime(data.index).tz_localize(None)
        data = data.sort_index()
        cutoff = pd.Timestamp(entry_date_value)
        available = data.loc[data.index <= cutoff].copy()

        if available.empty:
            return {
                "status": "Unavailable",
                "message": "No market session was available on or before the entry date.",
            }

        close = _series(available, "Close")
        open_ = _series(available, "Open")
        volume = _series(available, "Volume")

        available["EMA9"] = close.ewm(span=9, adjust=False).mean()
        available["EMA20"] = close.ewm(span=20, adjust=False).mean()
        available["EMA50"] = close.ewm(span=50, adjust=False).mean()
        available["EMA200"] = close.ewm(span=200, adjust=False).mean()
        available["RSI14"] = _rsi(close, 14)

        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        available["MACD"] = ema12 - ema26
        available["MACDSignal"] = available["MACD"].ewm(span=9, adjust=False).mean()
        available["MACDHistogram"] = available["MACD"] - available["MACDSignal"]
        available["ATR14"] = _atr(available, 14)
        available["Volume20"] = volume.rolling(20).mean()
        available["RelativeVolume"] = volume / available["Volume20"]
        available["GapPct"] = open_ / close.shift(1) - 1
        available["WeekReturn"] = close.pct_change(5)

        row = available.iloc[-1]
        market_date = available.index[-1].date().isoformat()

        def number(name: str):
            value = row.get(name)
            return None if pd.isna(value) else float(value)

        snapshot = {
            "status": "Complete",
            "ticker": ticker.upper(),
            "requested_entry_date": str(entry_date_value),
            "market_date_used": market_date,
            "close": number("Close"),
            "open": number("Open"),
            "ema9": number("EMA9"),
            "ema20": number("EMA20"),
            "ema50": number("EMA50"),
            "ema200": number("EMA200"),
            "rsi14": number("RSI14"),
            "macd": number("MACD"),
            "macd_signal": number("MACDSignal"),
            "macd_histogram": number("MACDHistogram"),
            "atr14": number("ATR14"),
            "relative_volume": number("RelativeVolume"),
            "gap_pct": number("GapPct"),
            "week_return": number("WeekReturn"),
            "message": (
                "Reconstructed using daily end-of-day data available on or before "
                f"{market_date}. Intraday conditions may have differed."
            ),
        }
        snapshot["evidence_score"], snapshot["verdict"], snapshot["evidence"] = (
            score_case(snapshot)
        )
        return snapshot

    except Exception as exc:
        return {
            "status": "Unavailable",
            "message": f"Historical reconstruction failed: {exc}",
        }


def score_case(snapshot: dict) -> tuple[int, str, list[str]]:
    score = 50
    evidence: list[str] = []

    close = snapshot.get("close")
    ema9 = snapshot.get("ema9")
    ema20 = snapshot.get("ema20")
    ema50 = snapshot.get("ema50")
    ema200 = snapshot.get("ema200")
    rsi = snapshot.get("rsi14")
    rel_volume = snapshot.get("relative_volume")
    macd_hist = snapshot.get("macd_histogram")
    week_return = snapshot.get("week_return")

    if close is not None and ema9 is not None:
        if close >= ema9:
            score += 7
            evidence.append("Price closed above the 9 EMA.")
        else:
            score -= 5
            evidence.append("Price closed below the 9 EMA.")

    if close is not None and ema20 is not None:
        if close >= ema20:
            score += 9
            evidence.append("Price was above the 20 EMA.")
        else:
            score -= 8
            evidence.append("Price was below the 20 EMA.")

    if close is not None and ema50 is not None:
        if close >= ema50:
            score += 9
            evidence.append("Price was above the 50 EMA.")
        else:
            score -= 8
            evidence.append("Price was below the 50 EMA.")

    if close is not None and ema200 is not None:
        if close >= ema200:
            score += 6
            evidence.append("The long-term trend was above the 200 EMA.")
        else:
            score -= 6
            evidence.append("The stock was below the 200 EMA.")

    if rsi is not None:
        if 35 <= rsi <= 55:
            score += 12
            evidence.append(f"RSI {rsi:.1f} was in a constructive pullback zone.")
        elif 55 < rsi <= 70:
            score += 5
            evidence.append(f"RSI {rsi:.1f} showed positive momentum.")
        elif rsi > 75:
            score -= 10
            evidence.append(f"RSI {rsi:.1f} indicated an extended entry.")
        elif rsi < 30:
            score += 3
            evidence.append(f"RSI {rsi:.1f} was deeply oversold.")

    if rel_volume is not None:
        if 1.2 <= rel_volume <= 2.8:
            score += 9
            evidence.append(f"Relative volume was supportive at {rel_volume:.2f}×.")
        elif rel_volume < 0.7:
            score -= 4
            evidence.append(f"Relative volume was light at {rel_volume:.2f}×.")
        elif rel_volume > 3:
            evidence.append(f"Relative volume was unusually high at {rel_volume:.2f}×.")

    if macd_hist is not None:
        if macd_hist > 0:
            score += 6
            evidence.append("MACD histogram was positive.")
        else:
            score -= 4
            evidence.append("MACD histogram was negative.")

    if week_return is not None:
        if week_return > 0.12:
            score -= 8
            evidence.append(
                f"The stock had already risen {week_return:.1%} in five sessions."
            )
        elif -0.08 <= week_return <= 0.05:
            score += 5
            evidence.append("Recent weekly momentum was not excessively extended.")

    score = int(np.clip(score, 0, 100))
    if score >= 85:
        verdict = "Strong evidence"
    elif score >= 70:
        verdict = "Constructive setup"
    elif score >= 55:
        verdict = "Mixed evidence"
    else:
        verdict = "Weak or conflicting evidence"

    return score, verdict, evidence


# Add these functions to the bottom of your existing ltp/market_data.py

@st.cache_data(ttl=60, show_spinner=False)
def quote_snapshot(tickers: tuple[str, ...]) -> dict[str, float | None]:
    return {ticker: current_price(ticker) for ticker in tickers}

def clear_quote_cache() -> None:
    current_price.clear()
    quote_snapshot.clear()

