from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
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
def research_data(ticker: str, period: str = "6mo") -> pd.DataFrame:
    if yf is None:
        raise RuntimeError("The yfinance market-data package is unavailable.")
    data = yf.download(
        ticker.upper(),
        period=period,
        interval="1d",
        auto_adjust=False,
        progress=False,
        threads=False,
    )
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    data = data.dropna(how="all").copy()
    if data.empty:
        return data

    close = pd.to_numeric(data["Close"], errors="coerce")
    volume = pd.to_numeric(data["Volume"], errors="coerce")
    data["EMA9"] = close.ewm(span=9, adjust=False).mean()
    data["EMA20"] = close.ewm(span=20, adjust=False).mean()
    data["EMA50"] = close.ewm(span=50, adjust=False).mean()
    data["EMA200"] = close.ewm(span=200, adjust=False).mean()
    data["RSI14"] = _rsi(close)
    data["MACD"] = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
    data["MACDSignal"] = data["MACD"].ewm(span=9, adjust=False).mean()
    data["MACDHist"] = data["MACD"] - data["MACDSignal"]
    data["Volume20"] = volume.rolling(20).mean()
    return data


def research_chart(data: pd.DataFrame, ticker: str) -> go.Figure:
    figure = make_subplots(
        rows=4,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.035,
        row_heights=[0.52, 0.16, 0.15, 0.17],
        subplot_titles=(
            f"{ticker.upper()} price and trend",
            "Volume",
            "RSI 14",
            "MACD",
        ),
    )

    figure.add_trace(
        go.Candlestick(
            x=data.index,
            open=data["Open"],
            high=data["High"],
            low=data["Low"],
            close=data["Close"],
            name="Price",
        ),
        row=1,
        col=1,
    )
    for name in ["EMA9", "EMA20", "EMA50", "EMA200"]:
        figure.add_trace(
            go.Scatter(x=data.index, y=data[name], name=name, mode="lines"),
            row=1,
            col=1,
        )

    figure.add_trace(
        go.Bar(x=data.index, y=data["Volume"], name="Volume"),
        row=2,
        col=1,
    )
    figure.add_trace(
        go.Scatter(x=data.index, y=data["Volume20"], name="20-day avg volume"),
        row=2,
        col=1,
    )

    figure.add_trace(
        go.Scatter(x=data.index, y=data["RSI14"], name="RSI 14"),
        row=3,
        col=1,
    )
    figure.add_hline(y=70, line_dash="dash", row=3, col=1)
    figure.add_hline(y=50, line_dash="dot", row=3, col=1)
    figure.add_hline(y=30, line_dash="dash", row=3, col=1)

    figure.add_trace(
        go.Scatter(x=data.index, y=data["MACD"], name="MACD"),
        row=4,
        col=1,
    )
    figure.add_trace(
        go.Scatter(x=data.index, y=data["MACDSignal"], name="Signal"),
        row=4,
        col=1,
    )
    figure.add_trace(
        go.Bar(x=data.index, y=data["MACDHist"], name="Histogram"),
        row=4,
        col=1,
    )

    figure.update_layout(
        height=940,
        template="plotly_dark",
        xaxis_rangeslider_visible=False,
        legend_orientation="h",
        legend_y=1.02,
        margin=dict(l=20, r=20, t=70, b=20),
    )
    return figure


def indicator_cards(data: pd.DataFrame) -> list[dict]:
    if data.empty:
        return []
    row = data.iloc[-1]
    price = float(row["Close"])
    ema20 = float(row["EMA20"])
    ema50 = float(row["EMA50"])
    ema200 = float(row["EMA200"])
    rsi = float(row["RSI14"])
    macd = float(row["MACD"])
    signal = float(row["MACDSignal"])
    hist = float(row["MACDHist"])
    rel_volume = (
        float(row["Volume"] / row["Volume20"])
        if pd.notna(row["Volume20"]) and row["Volume20"] > 0
        else np.nan
    )

    distance = price / ema20 - 1
    ema_status = (
        "Excellent" if price >= ema20 and 0 <= distance <= 0.03
        else "Good" if price >= ema20 and distance <= 0.07
        else "Extended" if distance > 0.07
        else "Caution"
    )
    rsi_status = (
        "Healthy" if 45 <= rsi <= 65
        else "Strong—watch extension" if 65 < rsi <= 75
        else "Very extended" if rsi > 75
        else "Weak/recovering"
    )
    volume_status = (
        "Excellent" if rel_volume >= 2
        else "Good" if rel_volume >= 1.3
        else "Normal" if rel_volume >= 0.9
        else "Weak"
    )
    macd_status = (
        "Improving" if hist > 0 and macd > signal
        else "Weakening" if hist > 0
        else "Bearish"
    )

    return [
        {
            "name": "EMA 20",
            "value": f"${ema20:,.2f}",
            "status": ema_status,
            "actuals": f"Price ${price:,.2f} · distance {distance:+.2%}",
            "good": "Price above a rising EMA20 and generally within about 0–5%.",
            "caution": "Repeated closes below it, a flat/downward slope, or price more than ~8–10% above it.",
            "why": "Tracks the short-term trend and often acts as dynamic support in growth stocks.",
        },
        {
            "name": "EMA 50 / EMA 200",
            "value": f"${ema50:,.2f} / ${ema200:,.2f}",
            "status": "Bullish" if price > ema50 > ema200 else "Mixed",
            "actuals": f"Price ${price:,.2f}",
            "good": "Price above both averages, with EMA50 above EMA200.",
            "caution": "Price below EMA50 or EMA50 below EMA200.",
            "why": "Shows intermediate and long-term trend structure.",
        },
        {
            "name": "RSI 14",
            "value": f"{rsi:.1f}",
            "status": rsi_status,
            "actuals": "Healthy momentum is often around 45–65.",
            "good": "45–65 for constructive momentum; 65–75 can be strong but requires entry discipline.",
            "caution": "Above 75–80 may be extended; below 40 may indicate weak momentum.",
            "why": "Measures the speed and persistence of recent price movement.",
        },
        {
            "name": "Relative Volume",
            "value": "—" if pd.isna(rel_volume) else f"{rel_volume:.2f}×",
            "status": volume_status,
            "actuals": "Current session volume versus the recent 20-day average.",
            "good": "Above 1.3× supports interest; 2× or more is unusually strong participation.",
            "caution": "Breakouts below 1× average volume are less convincing.",
            "why": "Price moves supported by participation generally carry more information.",
        },
        {
            "name": "MACD",
            "value": f"{macd:.2f}",
            "status": macd_status,
            "actuals": f"Signal {signal:.2f} · histogram {hist:+.2f}",
            "good": "MACD above its signal with a rising positive histogram.",
            "caution": "A shrinking histogram or MACD below the signal can show slowing momentum.",
            "why": "Confirms momentum changes; it should not be used alone.",
        },
    ]
