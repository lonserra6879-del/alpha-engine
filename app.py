
from __future__ import annotations

from io import BytesIO
from typing import Dict, Tuple

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf
from scipy.stats import binomtest, ttest_1samp
import plotly.graph_objects as go

st.set_page_config(
    page_title="Alpha Engine",
    page_icon="📈",
    layout="wide",
)

AI_STOCKS = {
    "NBIS": "Nebius Group",
    "CRWV": "CoreWeave",
    "NVDA": "NVIDIA",
    "AMD": "Advanced Micro Devices",
    "AVGO": "Broadcom",
    "PLTR": "Palantir",
    "SMCI": "Super Micro Computer",
    "ARM": "Arm Holdings",
    "IREN": "IREN",
    "APLD": "Applied Digital",
}

FORWARD_WINDOWS = (1, 3, 5, 10, 20)


@st.cache_data(ttl=1800, show_spinner=False)
def download_prices(ticker: str, period: str = "2y") -> pd.DataFrame:
    data = yf.download(
        ticker,
        period=period,
        interval="1d",
        auto_adjust=False,
        progress=False,
        actions=False,
        threads=False,
    )
    if data.empty:
        raise RuntimeError(f"No historical data was returned for {ticker}.")
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    required = ["Open", "High", "Low", "Close", "Volume"]
    missing = [c for c in required if c not in data.columns]
    if missing:
        raise RuntimeError(f"Missing columns for {ticker}: {', '.join(missing)}")
    data = data[required].copy()
    data.index = pd.to_datetime(data.index).tz_localize(None)
    data.index.name = "Date"
    return data.dropna(subset=["Close"])


def calculate_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)
    avg_gain = gains.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = losses.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    result = 100 - (100 / (1 + rs))
    return result.where(avg_loss != 0, 100)


def enrich(df: pd.DataFrame) -> pd.DataFrame:
    x = df.copy()
    x["Return_1d"] = x["Close"].pct_change()
    x["Gap"] = x["Open"] / x["Close"].shift(1) - 1
    x["RSI14"] = calculate_rsi(x["Close"])
    x["EMA10"] = x["Close"].ewm(span=10, adjust=False).mean()
    x["EMA20"] = x["Close"].ewm(span=20, adjust=False).mean()
    x["SMA50"] = x["Close"].rolling(50).mean()
    x["SMA100"] = x["Close"].rolling(100).mean()
    x["High20"] = x["Close"].rolling(20).max()
    x["High60"] = x["Close"].rolling(60).max()
    x["Pullback20"] = x["Close"] / x["High20"] - 1
    x["Pullback60"] = x["Close"] / x["High60"] - 1
    x["Vol20"] = x["Volume"].rolling(20).mean()
    x["VolumeRatio"] = x["Volume"] / x["Vol20"]
    x["Day"] = x.index.day_name()
    x["Week"] = x.index.to_period("W-FRI")

    tr = pd.concat(
        [
            x["High"] - x["Low"],
            (x["High"] - x["Close"].shift()).abs(),
            (x["Low"] - x["Close"].shift()).abs(),
        ],
        axis=1,
    ).max(axis=1)
    x["ATR14"] = tr.rolling(14).mean()
    x["ATRpct"] = x["ATR14"] / x["Close"]

    signs = np.sign(x["Return_1d"].fillna(0))
    streaks, current, previous = [], 0, 0
    for sign in signs:
        if sign == 0:
            current = 0
        elif sign == previous:
            current += int(sign)
        else:
            current = int(sign)
        streaks.append(current)
        previous = sign
    x["Streak"] = streaks

    for n in FORWARD_WINDOWS:
        x[f"Fwd_{n}d"] = x["Close"].shift(-n) / x["Close"] - 1
    return x


def friday_analysis(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    for week, group in df.groupby("Week"):
        group = group.sort_index()
        friday = group[group.index.dayofweek == 4]
        before = group[group.index.dayofweek < 4]
        if friday.empty or before.empty:
            continue
        mon_thu = before.iloc[-1]["Close"] / before.iloc[0]["Open"] - 1
        friday_return = friday.iloc[0]["Close"] / friday.iloc[0]["Open"] - 1
        reversal = bool(
            (mon_thu > 0 and friday_return < 0)
            or (mon_thu < 0 and friday_return > 0)
        )
        rows.append(
            {
                "Week": str(week),
                "Friday Date": friday.index[0],
                "Mon-Thu Return": mon_thu,
                "Friday Return": friday_return,
                "Reversal": reversal,
                "Absolute Mon-Thu Move": abs(mon_thu),
            }
        )

    raw = pd.DataFrame(rows)
    if raw.empty:
        return raw, pd.DataFrame()

    conditions = [
        ("All qualifying weeks", pd.Series(True, index=raw.index)),
        ("Mon-Thu up", raw["Mon-Thu Return"] > 0),
        ("Mon-Thu down", raw["Mon-Thu Return"] < 0),
        ("|Mon-Thu| ≥ 2%", raw["Absolute Mon-Thu Move"] >= 0.02),
        ("|Mon-Thu| ≥ 5%", raw["Absolute Mon-Thu Move"] >= 0.05),
        ("Mon-Thu up ≥ 5%", raw["Mon-Thu Return"] >= 0.05),
        ("Mon-Thu down ≤ -5%", raw["Mon-Thu Return"] <= -0.05),
    ]

    summary = []
    for label, mask in conditions:
        sample = raw.loc[mask]
        n = len(sample)
        reversals = int(sample["Reversal"].sum()) if n else 0
        summary.append(
            {
                "Condition": label,
                "Occurrences": n,
                "Reversal Rate": reversals / n if n else np.nan,
                "Average Friday Return": sample["Friday Return"].mean() if n else np.nan,
                "Median Friday Return": sample["Friday Return"].median() if n else np.nan,
                "p-value vs 50%": binomtest(reversals, n, 0.5).pvalue if n else np.nan,
            }
        )
    return raw, pd.DataFrame(summary)


def summarize_signal(df: pd.DataFrame, mask: pd.Series, name: str, horizon: int) -> dict:
    values = df.loc[mask.fillna(False), f"Fwd_{horizon}d"].dropna()
    n = len(values)
    if not n:
        return {"Signal": name, "Horizon": horizon, "N": 0}
    wins = int((values > 0).sum())
    return {
        "Signal": name,
        "Horizon": horizon,
        "N": n,
        "Win Rate": wins / n,
        "Average Return": values.mean(),
        "Median Return": values.median(),
        "Average Winner": values[values > 0].mean() if wins else np.nan,
        "Average Loser": values[values <= 0].mean() if wins < n else np.nan,
        "p-value Return": ttest_1samp(values, 0).pvalue if n >= 2 else np.nan,
        "p-value Win Rate": binomtest(wins, n, 0.5).pvalue,
    }


def pattern_table(df: pd.DataFrame) -> pd.DataFrame:
    masks = {}

    for threshold in (30, 35, 40, 45, 50, 65, 70, 75, 80):
        if threshold <= 50:
            masks[f"RSI14 ≤ {threshold}"] = df["RSI14"] <= threshold
        else:
            masks[f"RSI14 ≥ {threshold}"] = df["RSI14"] >= threshold

    for pullback in (0.05, 0.08, 0.10, 0.12, 0.15, 0.20):
        masks[f"Pullback from 20-day high ≥ {pullback:.0%}"] = (
            df["Pullback20"] <= -pullback
        )

    for days in (2, 3, 4):
        masks[f"{days}+ red days"] = df["Streak"] <= -days
        masks[f"{days}+ green days"] = df["Streak"] >= days

    for move in (0.03, 0.05, 0.08, 0.10):
        masks[f"Daily decline ≥ {move:.0%}"] = df["Return_1d"] <= -move
        masks[f"Daily gain ≥ {move:.0%}"] = df["Return_1d"] >= move

    masks["Near EMA20 ±3%"] = (df["Close"] / df["EMA20"] - 1).abs() <= 0.03
    masks["Below EMA20 by 5%+"] = df["Close"] / df["EMA20"] - 1 <= -0.05
    masks["Above EMA20 and SMA50"] = (
        (df["Close"] > df["EMA20"]) & (df["Close"] > df["SMA50"])
    )
    masks["Low-volume red day"] = (
        (df["Return_1d"] < 0) & (df["VolumeRatio"] < 0.8)
    )
    masks["High-volume selloff"] = (
        (df["Return_1d"] <= -0.05) & (df["VolumeRatio"] >= 1.5)
    )
    masks["Gap up 5%+"] = df["Gap"] >= 0.05
    masks["Gap down 5%+"] = df["Gap"] <= -0.05

    records = []
    for name, mask in masks.items():
        for horizon in FORWARD_WINDOWS:
            records.append(summarize_signal(df, mask, name, horizon))
    return pd.DataFrame(records)


def alpha_score(df: pd.DataFrame, friday_summary: pd.DataFrame) -> dict:
    valid = df.dropna(subset=["RSI14", "EMA20", "SMA50", "Pullback20", "ATRpct"])
    if valid.empty:
        raise RuntimeError("Not enough history to calculate a reliable score.")

    last = valid.iloc[-1]
    score = 50
    positives, risks = [], []

    rsi = float(last["RSI14"])
    if rsi <= 35:
        score += 18
        positives.append("RSI is deeply compressed")
    elif rsi <= 45:
        score += 10
        positives.append("RSI is below neutral")
    elif rsi >= 78:
        score -= 18
        risks.append("RSI is extremely extended")
    elif rsi >= 70:
        score -= 10
        risks.append("RSI is overbought")

    pullback = -float(last["Pullback20"])
    if pullback >= 0.15:
        score += 16
        positives.append("Price is at least 15% below its 20-day high")
    elif pullback >= 0.08:
        score += 9
        positives.append("Price has made a meaningful pullback")
    elif pullback < 0.02 and rsi >= 65:
        score -= 6
        risks.append("Price is near a recent high with elevated momentum")

    ema_distance = float(last["Close"] / last["EMA20"] - 1)
    if -0.06 <= ema_distance <= 0.02:
        score += 10
        positives.append("Price is near the 20-day EMA")
    elif ema_distance > 0.15:
        score -= 12
        risks.append("Price is more than 15% above the 20-day EMA")
    elif ema_distance < -0.12:
        score -= 5
        risks.append("Price is far below the 20-day EMA")

    if last["Close"] > last["SMA50"]:
        score += 9
        positives.append("Price remains above the 50-day trend")
    else:
        score -= 9
        risks.append("Price is below the 50-day trend")

    streak = int(last["Streak"])
    if streak <= -3:
        score += 7
        positives.append("The stock has a three-or-more-day losing streak")
    elif streak >= 4:
        score -= 7
        risks.append("The stock has a four-or-more-day winning streak")

    volume_ratio = float(last["VolumeRatio"]) if pd.notna(last["VolumeRatio"]) else 1.0
    if last["Return_1d"] < 0 and volume_ratio < 0.8:
        score += 5
        positives.append("The pullback occurred on subdued volume")
    elif last["Return_1d"] <= -0.05 and volume_ratio >= 1.5:
        score -= 8
        risks.append("The stock experienced a heavy-volume selloff")

    atr = float(last["ATRpct"])
    if atr >= 0.08:
        score -= 5
        risks.append("Daily volatility is exceptionally high")

    friday_rate = np.nan
    if not friday_summary.empty:
        row = friday_summary[friday_summary["Condition"] == "All qualifying weeks"]
        if not row.empty:
            friday_rate = float(row.iloc[0]["Reversal Rate"])

    score = int(np.clip(score, 0, 100))
    label = (
        "Strong accumulation setup"
        if score >= 85
        else "Favorable setup"
        if score >= 72
        else "Mixed — wait for confirmation"
        if score >= 55
        else "Unfavorable entry setup"
    )

    return {
        "Date": valid.index[-1],
        "Close": float(last["Close"]),
        "Score": score,
        "Label": label,
        "RSI14": rsi,
        "Pullback20": float(last["Pullback20"]),
        "EMA20 Distance": ema_distance,
        "SMA50 Distance": float(last["Close"] / last["SMA50"] - 1),
        "ATR %": atr,
        "Friday Reversal Rate": friday_rate,
        "Positive Factors": positives,
        "Risk Factors": risks,
    }


def format_percent_columns(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    for column in result.columns:
        if any(
            word in column
            for word in ["Return", "Rate", "Pullback", "Distance", "ATR"]
        ):
            if pd.api.types.is_numeric_dtype(result[column]):
                result[column] = result[column].map(
                    lambda x: "—" if pd.isna(x) else f"{x:.2%}"
                )
        elif "p-value" in column and pd.api.types.is_numeric_dtype(result[column]):
            result[column] = result[column].map(
                lambda x: "—" if pd.isna(x) else f"{x:.4f}"
            )
    return result


def excel_report(
    ticker: str,
    score: dict,
    daily: pd.DataFrame,
    friday_raw: pd.DataFrame,
    friday_summary: pd.DataFrame,
    patterns: pd.DataFrame,
) -> bytes:
    output = BytesIO()
    score_row = {
        key: ", ".join(value) if isinstance(value, list) else value
        for key, value in score.items()
    }
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        pd.DataFrame([score_row]).to_excel(writer, "Current Score", index=False)
        friday_summary.to_excel(writer, "Friday Summary", index=False)
        friday_raw.to_excel(writer, "Friday Raw", index=False)
        patterns.to_excel(writer, "Pattern Backtests", index=False)
        daily.reset_index().to_excel(writer, "Daily Data", index=False)

        for ws in writer.book.worksheets:
            ws.freeze_panes = "A2"
            ws.auto_filter.ref = ws.dimensions
            ws.sheet_view.showGridLines = False
            for cell in ws[1]:
                cell.font = cell.font.copy(bold=True)
            for column_cells in ws.columns:
                width = min(
                    48,
                    max(10, max(len(str(cell.value or "")) for cell in column_cells) + 2),
                )
                ws.column_dimensions[column_cells[0].column_letter].width = width
    return output.getvalue()


def analyze_ticker(ticker: str, period: str):
    daily = enrich(download_prices(ticker, period))
    friday_raw, friday_summary = friday_analysis(daily)
    patterns = pattern_table(daily)
    score = alpha_score(daily, friday_summary)
    return daily, friday_raw, friday_summary, patterns, score


def answer_question(question: str, ticker: str, score: dict, friday_summary: pd.DataFrame, patterns: pd.DataFrame) -> str:
    q = question.lower().strip()

    if "friday" in q or "reversal" in q:
        row = friday_summary[friday_summary["Condition"] == "All qualifying weeks"]
        if row.empty:
            return "There is not enough Friday history to evaluate the reversal pattern."
        row = row.iloc[0]
        significance = (
            "statistically noteworthy"
            if row["p-value vs 50%"] < 0.05
            else "not statistically conclusive"
        )
        return (
            f"{ticker}'s Friday reversal rate is {row['Reversal Rate']:.1%} across "
            f"{int(row['Occurrences'])} qualifying weeks. The result is {significance} "
            f"(p={row['p-value vs 50%']:.3f})."
        )

    if any(word in q for word in ["buy", "entry", "accumulate"]):
        positive = "; ".join(score["Positive Factors"]) or "no major positive factor"
        risk = "; ".join(score["Risk Factors"]) or "no major risk flag"
        return (
            f"{ticker} has an Alpha Score of {score['Score']}/100, classified as "
            f"'{score['Label']}'. Positive factors: {positive}. Risks: {risk}. "
            "This is a research signal rather than a guaranteed recommendation."
        )

    if any(word in q for word in ["sell", "exit", "trim", "overbought"]):
        high_rsi = score["RSI14"] >= 70
        extended = score["EMA20 Distance"] >= 0.15
        if high_rsi or extended:
            return (
                f"{ticker} shows at least one extension warning. RSI is "
                f"{score['RSI14']:.1f} and price is {score['EMA20 Distance']:+.1%} "
                "from the 20-day EMA. Consider evaluating partial-profit or trailing-stop rules."
            )
        return (
            f"{ticker} does not currently show the strongest generic extension warning. "
            f"RSI is {score['RSI14']:.1f}, and price is {score['EMA20 Distance']:+.1%} "
            "from the 20-day EMA."
        )

    if "best pattern" in q or "strongest pattern" in q:
        eligible = patterns[(patterns["N"] >= 8) & (patterns["Horizon"] == 10)].copy()
        if eligible.empty:
            return "There are not enough repeated 10-day setups to identify a strongest pattern."
        best = eligible.sort_values(["Average Return", "Win Rate"], ascending=False).iloc[0]
        return (
            f"The highest-average 10-day setup with at least eight observations is "
            f"'{best['Signal']}'. It occurred {int(best['N'])} times, had a "
            f"{best['Win Rate']:.1%} win rate, and an average 10-day return of "
            f"{best['Average Return']:.2%}."
        )

    return (
        f"{ticker}'s current Alpha Score is {score['Score']}/100. RSI is "
        f"{score['RSI14']:.1f}, the 20-day pullback is {score['Pullback20']:.1%}, "
        f"and price is {score['SMA50 Distance']:+.1%} from the 50-day average. "
        "Try asking about the Friday reversal, entry quality, exit risk, or strongest historical pattern."
    )


st.title("📈 Alpha Engine")
st.caption(
    "A browser-based research dashboard for high-volatility AI and infrastructure stocks."
)

with st.sidebar:
    st.header("Analysis settings")
    default_ticker = st.selectbox(
        "AI stock",
        list(AI_STOCKS.keys()),
        format_func=lambda x: f"{x} — {AI_STOCKS[x]}",
    )
    custom_ticker = st.text_input("Or enter another ticker", "").upper().strip()
    ticker = custom_ticker or default_ticker
    period = st.selectbox("Historical period", ["1y", "2y", "5y", "max"], index=1)
    analyze = st.button("Analyze stock", type="primary", use_container_width=True)
    compare = st.button("Scan AI stocks", use_container_width=True)
    st.divider()
    st.caption(
        "Scores summarize technical and historical conditions. They are not guarantees "
        "or personalized financial advice."
    )

if "analysis" not in st.session_state:
    st.session_state.analysis = None
if "comparison" not in st.session_state:
    st.session_state.comparison = None

if analyze:
    try:
        with st.spinner(f"Analyzing {ticker}…"):
            st.session_state.analysis = (ticker, *analyze_ticker(ticker, period))
    except Exception as exc:
        st.error(str(exc))

if compare:
    records = []
    progress = st.progress(0, text="Scanning AI stocks…")
    for i, (symbol, company) in enumerate(AI_STOCKS.items(), start=1):
        try:
            daily, fr_raw, fr_summary, patterns, score = analyze_ticker(symbol, period)
            records.append(
                {
                    "Ticker": symbol,
                    "Company": company,
                    "Price": score["Close"],
                    "Score": score["Score"],
                    "Setup": score["Label"],
                    "RSI14": score["RSI14"],
                    "20D Pullback": score["Pullback20"],
                    "Friday Reversal": score["Friday Reversal Rate"],
                    "ATR %": score["ATR %"],
                }
            )
        except Exception as exc:
            records.append(
                {
                    "Ticker": symbol,
                    "Company": company,
                    "Price": np.nan,
                    "Score": np.nan,
                    "Setup": f"Unavailable: {exc}",
                    "RSI14": np.nan,
                    "20D Pullback": np.nan,
                    "Friday Reversal": np.nan,
                    "ATR %": np.nan,
                }
            )
        progress.progress(i / len(AI_STOCKS), text=f"Scanned {i} of {len(AI_STOCKS)}")
    progress.empty()
    st.session_state.comparison = pd.DataFrame(records).sort_values(
        "Score", ascending=False, na_position="last"
    )

if st.session_state.comparison is not None:
    st.subheader("AI Momentum Stock Scanner")
    comparison = st.session_state.comparison.copy()
    display = comparison.copy()
    for col in ["20D Pullback", "Friday Reversal", "ATR %"]:
        display[col] = display[col].map(lambda x: "—" if pd.isna(x) else f"{x:.2%}")
    display["Price"] = display["Price"].map(lambda x: "—" if pd.isna(x) else f"${x:,.2f}")
    display["RSI14"] = display["RSI14"].map(lambda x: "—" if pd.isna(x) else f"{x:.1f}")
    st.dataframe(display, use_container_width=True, hide_index=True)

if st.session_state.analysis is None:
    st.info("Choose a stock and click **Analyze stock**.")
else:
    ticker, daily, friday_raw, friday_summary, patterns, score = st.session_state.analysis

    st.subheader(f"{ticker} Alpha Dashboard")
    cols = st.columns(6)
    cols[0].metric("Alpha Score", f"{score['Score']}/100")
    cols[1].metric("Latest Close", f"${score['Close']:,.2f}")
    cols[2].metric("RSI 14", f"{score['RSI14']:.1f}")
    cols[3].metric("20-Day Pullback", f"{score['Pullback20']:.1%}")
    cols[4].metric("50-Day Trend", f"{score['SMA50 Distance']:+.1%}")
    friday_value = score["Friday Reversal Rate"]
    cols[5].metric(
        "Friday Reversal",
        "N/A" if pd.isna(friday_value) else f"{friday_value:.1%}",
    )

    st.markdown(f"### {score['Label']}")

    positive_col, risk_col = st.columns(2)
    with positive_col:
        st.markdown("#### Positive factors")
        if score["Positive Factors"]:
            for item in score["Positive Factors"]:
                st.write(f"✅ {item}")
        else:
            st.write("No major positive factor detected.")

    with risk_col:
        st.markdown("#### Risk factors")
        if score["Risk Factors"]:
            for item in score["Risk Factors"]:
                st.write(f"⚠️ {item}")
        else:
            st.write("No major technical risk flag detected.")

    tabs = st.tabs(
        ["Price chart", "Friday study", "Pattern backtests", "Ask Alpha Engine", "Export"]
    )

    with tabs[0]:
        view = daily.tail(180)
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(x=view.index, y=view["Close"], name="Close", mode="lines")
        )
        fig.add_trace(
            go.Scatter(x=view.index, y=view["EMA20"], name="EMA20", mode="lines")
        )
        fig.add_trace(
            go.Scatter(x=view.index, y=view["SMA50"], name="SMA50", mode="lines")
        )
        fig.update_layout(
            height=560,
            xaxis_title="Date",
            yaxis_title="Price",
            hovermode="x unified",
            margin=dict(l=20, r=20, t=40, b=20),
        )
        st.plotly_chart(fig, use_container_width=True)

    with tabs[1]:
        st.markdown(
            "A reversal occurs when Friday moves opposite to the cumulative Monday–Thursday direction."
        )
        st.dataframe(
            format_percent_columns(friday_summary),
            use_container_width=True,
            hide_index=True,
        )
        with st.expander("View every qualifying week"):
            st.dataframe(
                format_percent_columns(friday_raw),
                use_container_width=True,
                hide_index=True,
            )

    with tabs[2]:
        min_occurrences = st.slider("Minimum occurrences", 3, 30, 8)
        horizon = st.selectbox("Forward return horizon", FORWARD_WINDOWS, index=3)
        filtered = patterns[
            (patterns["N"] >= min_occurrences) & (patterns["Horizon"] == horizon)
        ].sort_values(["Average Return", "Win Rate"], ascending=False)
        st.dataframe(
            format_percent_columns(filtered),
            use_container_width=True,
            hide_index=True,
        )

    with tabs[3]:
        question = st.text_input(
            "Ask a question",
            placeholder="Examples: Is this a good entry? Does the Friday reversal hold? What is the strongest pattern?",
        )
        if question:
            st.write(answer_question(question, ticker, score, friday_summary, patterns))

    with tabs[4]:
        report = excel_report(
            ticker,
            score,
            daily,
            friday_raw,
            friday_summary,
            patterns,
        )
        st.download_button(
            "Download complete Excel report",
            data=report,
            file_name=f"{ticker}_alpha_engine_report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
