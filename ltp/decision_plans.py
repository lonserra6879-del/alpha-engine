from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

try:
    import yfinance as yf
except Exception:
    yf = None


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


@st.cache_data(ttl=900, show_spinner=False)
def build_decision_plan(ticker: str) -> dict:
    if yf is None:
        raise RuntimeError("Market-data package unavailable.")

    data = yf.download(
        ticker.upper(),
        period="1y",
        interval="1d",
        auto_adjust=False,
        progress=False,
        threads=False,
    )
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    data = data.dropna(how="all").copy()

    if data.empty or len(data) < 60:
        raise RuntimeError("Not enough historical data for a decision plan.")

    close = pd.to_numeric(data["Close"], errors="coerce")
    high = pd.to_numeric(data["High"], errors="coerce")
    low = pd.to_numeric(data["Low"], errors="coerce")
    volume = pd.to_numeric(data["Volume"], errors="coerce")

    data["EMA9"] = close.ewm(span=9, adjust=False).mean()
    data["EMA20"] = close.ewm(span=20, adjust=False).mean()
    data["EMA50"] = close.ewm(span=50, adjust=False).mean()
    data["EMA200"] = close.ewm(span=200, adjust=False).mean()
    data["RSI14"] = _rsi(close)
    macd = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
    data["MACD"] = macd
    data["MACDSignal"] = macd.ewm(span=9, adjust=False).mean()
    data["MACDHist"] = data["MACD"] - data["MACDSignal"]
    data["Volume20"] = volume.rolling(20).mean()
    data["RelVolume"] = volume / data["Volume20"]

    true_range = pd.concat(
        [
            high - low,
            (high - close.shift(1)).abs(),
            (low - close.shift(1)).abs(),
        ],
        axis=1,
    ).max(axis=1)
    data["ATR14"] = true_range.rolling(14).mean()
    data["Low20"] = low.rolling(20).min()
    data["High20"] = high.rolling(20).max()

    row = data.iloc[-1]
    prev = data.iloc[-2]

    price = float(row["Close"])
    ema20 = float(row["EMA20"])
    ema50 = float(row["EMA50"])
    ema200 = float(row["EMA200"])
    rsi = float(row["RSI14"])
    atr = float(row["ATR14"])
    rel_volume = float(row["RelVolume"]) if pd.notna(row["RelVolume"]) else None
    macd_hist = float(row["MACDHist"])
    prev_macd_hist = float(prev["MACDHist"])
    prior_high20 = float(data["High20"].iloc[-2])
    low20 = float(row["Low20"])

    structural_supports = [value for value in [ema20, ema50, low20] if value < price]
    support = max(structural_supports) if structural_supports else price - atr * 1.25

    balanced_entry_low = max(support, ema20 - atr * 0.25)
    balanced_entry_high = min(price, max(ema20 + atr * 0.35, balanced_entry_low))
    patient_entry_low = max(ema50, support - atr * 0.35)
    patient_entry_high = max(patient_entry_low, balanced_entry_low)
    aggressive_trigger = max(price * 1.008, prior_high20 * 1.002)

    tight_stop = max(support - atr * 0.20, price - atr * 1.0)
    balanced_stop = support - atr * 0.45
    wider_stop = min(balanced_stop, ema50 - atr * 0.35)

    target1 = max(prior_high20, price + atr * 1.5)
    target2 = max(target1 + atr * 1.5, price + atr * 3.0)

    midpoint = (balanced_entry_low + balanced_entry_high) / 2
    risk = max(midpoint - balanced_stop, 0.01)
    rr1 = max(target1 - midpoint, 0) / risk
    rr2 = max(target2 - midpoint, 0) / risk

    distance_ema20 = price / ema20 - 1
    entry_quality = 50

    if price > ema20 > ema50:
        entry_quality += 15
    if price > ema200:
        entry_quality += 8
    if 45 <= rsi <= 65:
        entry_quality += 12
    elif rsi > 75:
        entry_quality -= 12
    if rel_volume is not None and rel_volume >= 1.3:
        entry_quality += 8
    if macd_hist > 0 and macd_hist >= prev_macd_hist:
        entry_quality += 7
    if 0 <= distance_ema20 <= 0.03:
        entry_quality += 15
    elif distance_ema20 > 0.08:
        entry_quality -= 18
    if rr1 >= 3:
        entry_quality += 10
    elif rr1 < 1.5:
        entry_quality -= 12

    entry_quality = int(np.clip(entry_quality, 0, 100))

    if balanced_entry_low <= price <= balanced_entry_high:
        current_status = "Inside balanced entry zone"
        timing_message = "Price is currently within the estimated balanced zone."
    elif price > balanced_entry_high:
        gap = price / balanced_entry_high - 1
        if gap <= 0.04:
            current_status = "Slightly above preferred zone"
            timing_message = "A modest pullback could improve the reward-to-risk."
        else:
            current_status = "Extended—avoid chasing"
            timing_message = "Current price is materially above the preferred zone."
    else:
        current_status = "Below preferred zone"
        timing_message = "Price is below the estimated zone; support should be reconfirmed."

    if rr1 >= 4:
        rr_label = "Excellent"
    elif rr1 >= 3:
        rr_label = "Very good"
    elif rr1 >= 2:
        rr_label = "Good"
    elif rr1 >= 1.5:
        rr_label = "Fair"
    else:
        rr_label = "Poor"

    return {
        "ticker": ticker.upper(),
        "price": price,
        "ema20": ema20,
        "ema50": ema50,
        "ema200": ema200,
        "rsi14": rsi,
        "relative_volume": rel_volume,
        "macd_histogram": macd_hist,
        "atr14": atr,
        "entry_quality_score": entry_quality,
        "current_status": current_status,
        "timing_message": timing_message,
        "aggressive_trigger": aggressive_trigger,
        "balanced_entry_low": balanced_entry_low,
        "balanced_entry_high": balanced_entry_high,
        "patient_entry_low": patient_entry_low,
        "patient_entry_high": patient_entry_high,
        "tight_stop": tight_stop,
        "balanced_stop": balanced_stop,
        "wider_stop": wider_stop,
        "target1": target1,
        "target2": target2,
        "risk_reward_target1": rr1,
        "risk_reward_target2": rr2,
        "risk_reward_label": rr_label,
        "as_of": data.index[-1].strftime("%Y-%m-%d"),
        "data": data,
    }
