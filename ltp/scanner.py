from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

import numpy as np
import pandas as pd
import streamlit as st

try:
    import yfinance as yf
except Exception:
    yf = None


# Curated for reliability on free market data. Users can add symbols in the UI.
AI_TECH_UNIVERSE = {
    "AI Platforms": [
        "NBIS", "PLTR", "AI", "SOUN", "BBAI", "PATH", "TEM", "GTLB",
    ],
    "Semiconductors": [
        "NVDA", "AMD", "AVGO", "ARM", "TSM", "MU", "MRVL", "QCOM",
        "INTC", "ASML", "AMAT", "LRCX", "KLAC", "ON", "MCHP", "NXPI",
        "MPWR", "SMCI", "DELL", "HPE",
    ],
    "Cloud & Data": [
        "MSFT", "AMZN", "GOOGL", "ORCL", "SNOW", "DDOG", "NET", "MDB",
        "ESTC", "CFLT", "DOCN", "GDDY", "AKAM",
    ],
    "Cybersecurity": [
        "CRWD", "PANW", "ZS", "S", "FTNT", "CYBR", "OKTA", "TENB",
        "RBRK", "VRNS",
    ],
    "Software & Automation": [
        "NOW", "CRM", "ADBE", "INTU", "TEAM", "HUBS", "APP", "DUOL",
        "SHOP", "U", "RBLX", "IOT",
    ],
    "Data Centers & Power": [
        "APLD", "IREN", "CORZ", "VRT", "ETN", "CEG", "VST", "NRG",
        "PWR", "GEV", "NVT", "ANET", "CLS",
    ],
    "Robotics & Quantum": [
        "ISRG", "TER", "ROK", "SYM", "SERV", "RGTI", "QBTS", "QUBT", "IONQ",
    ],
    "High-Growth Tech": [
        "TSLA", "RDDT", "HOOD", "COIN", "MSTR", "RKLB", "ASTS", "CRDO",
        "ALAB", "WULF",
    ],
}

DEFAULT_UNIVERSE = sorted(
    {ticker for group in AI_TECH_UNIVERSE.values() for ticker in group}
)


def _flatten_download(data: pd.DataFrame, tickers: list[str]) -> dict[str, pd.DataFrame]:
    result: dict[str, pd.DataFrame] = {}
    if data.empty:
        return result

    if len(tickers) == 1 and not isinstance(data.columns, pd.MultiIndex):
        result[tickers[0]] = data.dropna(how="all")
        return result

    if not isinstance(data.columns, pd.MultiIndex):
        return result

    level0 = set(map(str, data.columns.get_level_values(0)))
    price_fields = {"Open", "High", "Low", "Close", "Adj Close", "Volume"}

    if level0 & price_fields:
        for ticker in tickers:
            try:
                frame = data.xs(ticker, axis=1, level=1).dropna(how="all")
                if not frame.empty:
                    result[ticker] = frame
            except Exception:
                continue
    else:
        for ticker in tickers:
            try:
                frame = data[ticker].dropna(how="all")
                if not frame.empty:
                    result[ticker] = frame
            except Exception:
                continue

    return result


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
    return 100 - 100 / (1 + rs)


def _safe(value):
    return None if pd.isna(value) else float(value)


def _technical_snapshot(ticker: str, frame: pd.DataFrame, sector: str) -> dict | None:
    if frame.empty or len(frame) < 55:
        return None

    close = _series(frame, "Close")
    high = _series(frame, "High")
    low = _series(frame, "Low")
    open_ = _series(frame, "Open")
    volume = _series(frame, "Volume")

    indicators = frame.copy()
    indicators["EMA9"] = close.ewm(span=9, adjust=False).mean()
    indicators["EMA20"] = close.ewm(span=20, adjust=False).mean()
    indicators["EMA50"] = close.ewm(span=50, adjust=False).mean()
    indicators["EMA200"] = close.ewm(span=200, adjust=False).mean()
    indicators["RSI14"] = _rsi(close)
    macd = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
    indicators["MACD"] = macd
    indicators["MACDSignal"] = macd.ewm(span=9, adjust=False).mean()
    indicators["MACDHist"] = indicators["MACD"] - indicators["MACDSignal"]
    indicators["Vol20"] = volume.rolling(20).mean()
    indicators["RelVol"] = volume / indicators["Vol20"]
    indicators["ATR"] = pd.concat(
        [
            high - low,
            (high - close.shift(1)).abs(),
            (low - close.shift(1)).abs(),
        ],
        axis=1,
    ).max(axis=1).rolling(14).mean()
    indicators["High20"] = high.rolling(20).max()
    indicators["Low20"] = low.rolling(20).min()
    indicators["Return1D"] = close.pct_change()
    indicators["Return5D"] = close.pct_change(5)
    indicators["Return20D"] = close.pct_change(20)

    row = indicators.iloc[-1]
    previous = indicators.iloc[-2]

    price = _safe(row["Close"])
    if price is None or price <= 0:
        return None

    ema9 = _safe(row["EMA9"])
    ema20 = _safe(row["EMA20"])
    ema50 = _safe(row["EMA50"])
    ema200 = _safe(row["EMA200"])
    rsi = _safe(row["RSI14"])
    rel_vol = _safe(row["RelVol"])
    atr = _safe(row["ATR"])
    macd_hist = _safe(row["MACDHist"])
    prev_hist = _safe(previous["MACDHist"])
    day_move = _safe(row["Return1D"])
    week_move = _safe(row["Return5D"])
    month_move = _safe(row["Return20D"])
    high20 = _safe(previous["High20"])
    low20 = _safe(row["Low20"])

    trend_points = 0
    trend_reasons = []
    if ema20 and price > ema20:
        trend_points += 9
        trend_reasons.append("above EMA20")
    if ema50 and price > ema50:
        trend_points += 7
        trend_reasons.append("above EMA50")
    if ema200 and price > ema200:
        trend_points += 5
        trend_reasons.append("above EMA200")
    if ema20 and ema50 and ema20 > ema50:
        trend_points += 4
        trend_reasons.append("EMA20 above EMA50")
    if ema20 and len(indicators) >= 6 and ema20 > float(indicators["EMA20"].iloc[-6]):
        trend_points += 5
        trend_reasons.append("EMA20 rising")
    trend_score = min(30, trend_points)

    momentum_points = 0
    momentum_reasons = []
    if rsi is not None:
        if 45 <= rsi <= 65:
            momentum_points += 9
            momentum_reasons.append("RSI in healthy zone")
        elif 65 < rsi <= 75:
            momentum_points += 6
            momentum_reasons.append("strong RSI")
        elif 35 <= rsi < 45:
            momentum_points += 5
            momentum_reasons.append("RSI recovering")
        elif rsi > 80:
            momentum_points -= 4
            momentum_reasons.append("RSI very extended")
    if macd_hist is not None and macd_hist > 0:
        momentum_points += 6
        momentum_reasons.append("MACD histogram positive")
    if macd_hist is not None and prev_hist is not None and macd_hist > prev_hist:
        momentum_points += 5
        momentum_reasons.append("MACD momentum improving")
    momentum_score = int(np.clip(momentum_points, 0, 20))

    volume_points = 0
    volume_reasons = []
    if rel_vol is not None:
        if rel_vol >= 2:
            volume_points += 20
            volume_reasons.append(f"relative volume {rel_vol:.1f}×")
        elif rel_vol >= 1.4:
            volume_points += 16
            volume_reasons.append(f"relative volume {rel_vol:.1f}×")
        elif rel_vol >= 1:
            volume_points += 10
            volume_reasons.append("volume near/above average")
        elif rel_vol < 0.7:
            volume_points += 2
            volume_reasons.append("light volume")
        else:
            volume_points += 6
    volume_score = min(20, volume_points)

    distance_ema20 = None if not ema20 else price / ema20 - 1
    entry_points = 0
    entry_reasons = []
    if distance_ema20 is not None:
        abs_distance = abs(distance_ema20)
        if 0 <= distance_ema20 <= 0.03:
            entry_points += 15
            entry_reasons.append("close to rising EMA20")
        elif -0.02 <= distance_ema20 < 0:
            entry_points += 10
            entry_reasons.append("testing EMA20 support")
        elif 0.03 < distance_ema20 <= 0.07:
            entry_points += 8
            entry_reasons.append("moderately extended")
        elif distance_ema20 > 0.10:
            entry_points -= 5
            entry_reasons.append("far above EMA20")
    if high20 and price > high20:
        entry_points += 5
        entry_reasons.append("20-day breakout")
    elif high20 and price >= high20 * 0.98:
        entry_points += 3
        entry_reasons.append("near breakout")
    entry_score = int(np.clip(entry_points, 0, 20))

    move_points = 0
    if day_move is not None:
        if 0.02 <= day_move <= 0.08:
            move_points += 5
        elif day_move > 0.12:
            move_points -= 2
    if week_move is not None:
        if 0.02 <= week_move <= 0.15:
            move_points += 5
        elif week_move > 0.25:
            move_points -= 3
    movement_score = int(np.clip(move_points, 0, 10))

    evidence_score = int(np.clip(
        trend_score + momentum_score + volume_score + entry_score + movement_score,
        0,
        100,
    ))

    # Structural planning levels—not brokerage instructions.
    support_candidates = [v for v in [ema20, ema50, low20] if v and v < price]
    support = max(support_candidates) if support_candidates else price - (atr or price * 0.05)
    balanced_entry_low = max(support, price - (atr or price * 0.03) * 0.65)
    balanced_entry_high = max(balanced_entry_low, min(price, (ema20 or price) * 1.015))

    balanced_stop = support - (atr or price * 0.03) * 0.35
    tight_stop = max(balanced_stop, price - (atr or price * 0.025))
    wide_stop = min(balanced_stop, (ema50 or balanced_stop) - (atr or price * 0.03) * 0.25)

    resistance = high20 if high20 and high20 > price else price + (atr or price * 0.04) * 2
    target1 = max(resistance, price + (atr or price * 0.04) * 1.5)
    target2 = max(target1 + (atr or price * 0.04), price + (atr or price * 0.04) * 3)

    planned_entry = (balanced_entry_low + balanced_entry_high) / 2
    risk = max(planned_entry - balanced_stop, 0.01)
    reward = max(target1 - planned_entry, 0)
    rr = reward / risk

    opportunity_score = evidence_score
    if rr >= 4:
        opportunity_score += 12
    elif rr >= 3:
        opportunity_score += 9
    elif rr >= 2:
        opportunity_score += 5
    elif rr < 1.5:
        opportunity_score -= 12
    if distance_ema20 is not None and distance_ema20 > 0.08:
        opportunity_score -= 12
    opportunity_score = int(np.clip(opportunity_score, 0, 100))

    if high20 and price > high20 and rel_vol and rel_vol >= 1.4:
        setup = "Volume breakout"
    elif ema20 and abs(price / ema20 - 1) <= 0.025 and price >= ema20:
        setup = "EMA20 pullback"
    elif rsi and 35 <= rsi <= 48 and macd_hist and macd_hist > prev_hist:
        setup = "Momentum recovery"
    elif day_move and day_move >= 0.03 and rel_vol and rel_vol >= 1.3:
        setup = "Momentum continuation"
    elif distance_ema20 and distance_ema20 > 0.09:
        setup = "Extended—wait"
    else:
        setup = "Trend watch"

    if evidence_score >= 85 and opportunity_score >= 80 and rr >= 2:
        classification = "Strong candidate"
    elif evidence_score >= 75 and opportunity_score >= 65:
        classification = "Watch for confirmation"
    elif setup == "EMA20 pullback" and evidence_score >= 65:
        classification = "Constructive pullback"
    elif distance_ema20 is not None and distance_ema20 > 0.09:
        classification = "Extended—do not chase"
    else:
        classification = "Mixed evidence"

    reasons = trend_reasons + momentum_reasons + volume_reasons + entry_reasons
    summary = "; ".join(reasons[:5]) if reasons else "Insufficient confirming evidence."

    return {
        "Ticker": ticker,
        "Group": sector,
        "Price": price,
        "Daily Move": day_move,
        "5-Day Move": week_move,
        "20-Day Move": month_move,
        "Relative Volume": rel_vol,
        "RSI": rsi,
        "EMA20": ema20,
        "Distance from EMA20": distance_ema20,
        "MACD Histogram": macd_hist,
        "Evidence Score": evidence_score,
        "Opportunity Score": opportunity_score,
        "Setup": setup,
        "Classification": classification,
        "Entry Low": balanced_entry_low,
        "Entry High": balanced_entry_high,
        "Tight Stop": tight_stop,
        "Balanced Stop": balanced_stop,
        "Wide Stop": wide_stop,
        "Target 1": target1,
        "Target 2": target2,
        "Risk/Reward": rr,
        "Summary": summary,
        "As Of": frame.index[-1].strftime("%Y-%m-%d"),
    }


@st.cache_data(ttl=1800, show_spinner=False)
def run_morning_scan(
    tickers: tuple[str, ...],
    period: str = "1y",
) -> pd.DataFrame:
    if yf is None:
        raise RuntimeError("The yfinance market-data package is unavailable.")

    clean = sorted({str(t).upper().strip() for t in tickers if str(t).strip()})
    if not clean:
        return pd.DataFrame()

    # Download in manageable batches to reduce failures and rate pressure.
    frames: dict[str, pd.DataFrame] = {}
    batch_size = 35
    for start in range(0, len(clean), batch_size):
        batch = clean[start:start + batch_size]
        data = yf.download(
            tickers=batch,
            period=period,
            interval="1d",
            auto_adjust=False,
            progress=False,
            group_by="column",
            threads=True,
        )
        frames.update(_flatten_download(data, batch))

    sector_lookup = {
        ticker: sector
        for sector, members in AI_TECH_UNIVERSE.items()
        for ticker in members
    }

    results = []
    for ticker in clean:
        frame = frames.get(ticker)
        if frame is None:
            continue
        snapshot = _technical_snapshot(
            ticker,
            frame,
            sector_lookup.get(ticker, "Custom Watchlist"),
        )
        if snapshot:
            results.append(snapshot)

    if not results:
        return pd.DataFrame()

    output = pd.DataFrame(results)
    return output.sort_values(
        ["Opportunity Score", "Evidence Score", "Relative Volume"],
        ascending=[False, False, False],
        na_position="last",
    ).reset_index(drop=True)


def clear_scan_cache() -> None:
    run_morning_scan.clear()
