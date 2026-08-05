from __future__ import annotations

from datetime import datetime
import json

import pandas as pd
import plotly.express as px
import streamlit as st

from ltp.analytics import enrich, summary, curve
from ltp.auth import init_auth, current_user, sign_in, sign_out
from ltp.config import APP_NAME, MOTTO, SHERLOCK_MOTTO
from ltp.database import load_trades, update_trade, load_privacy, save_privacy
from ltp.client import get_supabase
from ltp.market_data import reconstruct_case, quote_snapshot, clear_quote_cache
from ltp.portfolio import build_live_portfolio, portfolio_totals
from ltp.research import research_data, research_chart, indicator_cards
from ltp.scanner import (
    AI_TECH_UNIVERSE,
    DEFAULT_UNIVERSE,
    run_morning_scan,
    clear_scan_cache,
)
from ltp.sherlock import snapshot_to_json


st.set_page_config(
    page_title=APP_NAME,
    page_icon="🕵️",
    layout="wide",
    initial_sidebar_state="expanded",
)
init_auth()

st.markdown(
    """
    <style>
    :root { --navy:#07111f; --panel:#101d2f; --gold:#d6ad4b; --green:#35c46a; --muted:#91a0b6; }
    .stApp { background:radial-gradient(circle at 80% -10%,#17304e 0%,#07111f 42%,#040a12 100%); color:#eef3f8; }
    .block-container { padding-top:1.15rem; padding-bottom:3rem; max-width:1550px; }
    [data-testid="stSidebar"] { background:linear-gradient(180deg,#0c1828 0%,#07111f 100%); border-right:1px solid rgba(214,173,75,.18); }
    [data-testid="stMetric"] { background:linear-gradient(145deg,rgba(21,39,62,.96),rgba(10,22,37,.96)); border:1px solid rgba(214,173,75,.22); border-radius:18px; padding:16px; box-shadow:0 12px 34px rgba(0,0,0,.22); }
    [data-testid="stMetricLabel"] { color:#9eacc0; }
    [data-testid="stMetricValue"] { color:#f4d47f; }
    .stButton>button,.stFormSubmitButton>button { border-radius:12px; border:1px solid #d6ad4b; background:linear-gradient(135deg,#d6ad4b,#a87518); color:#07111f; font-weight:800; }
    [data-testid="stDataFrame"] { border:1px solid rgba(214,173,75,.18); border-radius:14px; overflow:hidden; }
    .hero { background:linear-gradient(135deg,rgba(18,34,55,.92),rgba(8,18,31,.96)); border:1px solid rgba(214,173,75,.26); border-radius:24px; padding:24px 28px; margin-bottom:18px; box-shadow:0 20px 50px rgba(0,0,0,.26); }
    .eyebrow { color:#d6ad4b; text-transform:uppercase; letter-spacing:.18em; font-size:.75rem; font-weight:800; }
    .hero-title { font-size:2.15rem; font-weight:850; margin:.25rem 0; }
    .hero-copy { color:#a7b4c6; margin:0; }
    .learning-card { background:linear-gradient(145deg,rgba(18,34,55,.96),rgba(8,18,31,.98)); border:1px solid rgba(214,173,75,.20); border-radius:18px; padding:18px; margin:8px 0 16px; }
    .score-chip { display:inline-block; padding:5px 10px; border-radius:999px; background:rgba(53,196,106,.12); color:#65dc91; border:1px solid rgba(53,196,106,.28); font-weight:750; }
    @media(max-width:700px){.block-container{padding-left:.7rem;padding-right:.7rem}.hero{padding:18px}.hero-title{font-size:1.55rem}.stButton button{min-height:44px}}
    </style>
    """,
    unsafe_allow_html=True,
)

try:
    get_supabase()
except Exception as exc:
    st.title(APP_NAME)
    st.error(str(exc))
    st.stop()

user = current_user()

if user is None:
    left, right = st.columns([1.05, 1], gap="large")
    with left:
        st.image("assets/ltp_logo.png", use_container_width=True)
    with right:
        st.markdown(
            '<div class="hero"><div class="eyebrow">Sherlock Awakens</div>'
            '<div class="hero-title">Evidence Over Emotion</div>'
            '<p class="hero-copy">Discover what deserves your research time—then understand why.</p></div>',
            unsafe_allow_html=True,
        )
        with st.form("login"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Enter the platform", type="primary", use_container_width=True)
        if submitted:
            ok, message = sign_in(email, password)
            if ok:
                st.rerun()
            st.error(message)
    st.stop()

with st.sidebar:
    st.image("assets/ltp_logo.png", use_container_width=True)
    st.markdown(f"### {APP_NAME}")
    st.write(f"**{user.display_name}**")
    st.caption("Administrator" if user.role == "admin" else "Investor")

    pages = [
        "🔎 Morning Scanner",
        "🧪 Research Lab",
        "🏠 Command Center",
        "💼 Live Portfolio",
        "🕵️ Sherlock Cases",
        "📊 Analytics",
        "🔄 Broker Data",
        "🔒 Privacy & Sharing",
        "✨ What's New",
    ]
    if user.role == "admin":
        pages.append("⚙️ Admin")

    page = st.radio("Navigation", pages, label_visibility="collapsed")
    st.divider()
    st.success("Secure cloud database")
    if st.button("Sign out", use_container_width=True):
        sign_out()


def trades() -> pd.DataFrame:
    try:
        return load_trades(user.user_id)
    except Exception as exc:
        st.error(f"Could not load trades: {exc}")
        return pd.DataFrame()


def decode_snapshot(value):
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return json.loads(value)
        except Exception:
            return None
    return None


def set_research_ticker(ticker: str):
    st.session_state["research_ticker"] = ticker
    st.session_state["navigation_hint"] = "Open Research Lab from the left menu."


if page == "🔎 Morning Scanner":
    st.markdown(
        '<div class="hero"><div class="eyebrow">Release 1 · Sherlock Awakens</div>'
        '<div class="hero-title">Morning AI & Technology Scanner</div>'
        '<p class="hero-copy">Rank high-movement growth stocks by technical evidence, entry quality, and estimated risk/reward.</p></div>',
        unsafe_allow_html=True,
    )

    st.warning(
        "Planning levels are educational estimates from delayed daily market data—not predictions, "
        "brokerage quotes, or instructions to trade."
    )

    with st.expander("Scanner universe and controls", expanded=False):
        selected_groups = st.multiselect(
            "Groups",
            list(AI_TECH_UNIVERSE.keys()),
            default=list(AI_TECH_UNIVERSE.keys()),
        )
        custom_symbols = st.text_input(
            "Add custom tickers (comma separated)",
            placeholder="Example: AAPL, META, IBM",
        )
        top_n = st.slider("Results to display", 5, 30, 15)

    selected = {
        ticker
        for group in selected_groups
        for ticker in AI_TECH_UNIVERSE[group]
    }
    selected.update(
        token.strip().upper()
        for token in custom_symbols.split(",")
        if token.strip()
    )

    c1, c2 = st.columns([1, 4])
    with c1:
        if st.button("Run fresh scan", type="primary", use_container_width=True):
            clear_scan_cache()
    with c2:
        st.caption(
            f"Selected universe: {len(selected)} symbols. Results cache for 30 minutes "
            "to reduce free-data request failures."
        )

    try:
        with st.spinner("Sherlock is investigating trend, momentum, volume, and entry quality..."):
            scan = run_morning_scan(tuple(sorted(selected)))
    except Exception as exc:
        st.error(f"Scanner could not complete: {exc}")
        st.stop()

    if scan.empty:
        st.info("No scanner results were returned. Try fewer groups or run the scan again later.")
        st.stop()

    shortlist = scan.head(top_n).copy()
    strong = int((scan["Classification"] == "Strong candidate").sum())
    watch = int((scan["Classification"] == "Watch for confirmation").sum())
    extended = int((scan["Classification"] == "Extended—do not chase").sum())
    scanned = len(scan)

    a, b, c, d = st.columns(4)
    a.metric("Stocks analyzed", scanned)
    b.metric("Strong candidates", strong)
    c.metric("Watch for confirmation", watch)
    d.metric("Extended—avoid chasing", extended)

    st.subheader("If you only research three stocks today")
    for rank, (_, row) in enumerate(shortlist.head(3).iterrows(), start=1):
        with st.container(border=True):
            left, middle, right = st.columns([1, 3, 1.2])
            left.markdown(f"## #{rank}")
            middle.markdown(f"### {row['Ticker']} · {row['Setup']}")
            middle.write(row["Summary"])
            middle.caption(
                f"Entry planning zone ${row['Entry Low']:,.2f}–${row['Entry High']:,.2f} · "
                f"Balanced stop area ${row['Balanced Stop']:,.2f} · "
                f"First resistance/target area ${row['Target 1']:,.2f}"
            )
            right.metric("Evidence", int(row["Evidence Score"]))
            right.metric("Opportunity", int(row["Opportunity Score"]))
            if right.button("Research", key=f"research_top_{row['Ticker']}", use_container_width=True):
                set_research_ticker(str(row["Ticker"]))
                st.info("Ticker saved. Open Research Lab from the left menu.")

    st.subheader("Ranked opportunities")
    display = shortlist[
        [
            "Ticker", "Group", "Classification", "Setup", "Price",
            "Daily Move", "Relative Volume", "RSI",
            "Evidence Score", "Opportunity Score", "Risk/Reward",
            "Entry Low", "Entry High", "Balanced Stop", "Target 1",
        ]
    ]
    st.dataframe(
        display,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Price": st.column_config.NumberColumn(format="$%.2f"),
            "Daily Move": st.column_config.NumberColumn(format="percent"),
            "Relative Volume": st.column_config.NumberColumn(format="%.2f×"),
            "RSI": st.column_config.NumberColumn(format="%.1f"),
            "Entry Low": st.column_config.NumberColumn(format="$%.2f"),
            "Entry High": st.column_config.NumberColumn(format="$%.2f"),
            "Balanced Stop": st.column_config.NumberColumn(format="$%.2f"),
            "Target 1": st.column_config.NumberColumn(format="$%.2f"),
            "Risk/Reward": st.column_config.NumberColumn(format="%.2f"),
        },
    )

    ticker_choice = st.selectbox("Open detailed planning card", shortlist["Ticker"].tolist())
    row = shortlist.loc[shortlist["Ticker"] == ticker_choice].iloc[0]
    with st.container(border=True):
        st.markdown(f"## {row['Ticker']} · {row['Classification']}")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Current delayed price", f"${row['Price']:,.2f}")
        c2.metric("Evidence Score", int(row["Evidence Score"]))
        c3.metric("Opportunity Score", int(row["Opportunity Score"]))
        c4.metric("Risk/Reward", f"{row['Risk/Reward']:.2f}:1")

        st.markdown("### Planning levels")
        p1, p2, p3 = st.columns(3)
        p1.metric("Balanced entry zone", f"${row['Entry Low']:,.2f}–${row['Entry High']:,.2f}")
        p2.metric("Balanced stop area", f"${row['Balanced Stop']:,.2f}")
        p3.metric("First resistance area", f"${row['Target 1']:,.2f}")

        st.write(f"**Tighter stop area:** ${row['Tight Stop']:,.2f}")
        st.write(f"**Wider structural stop area:** ${row['Wide Stop']:,.2f}")
        st.write(f"**Second potential resistance area:** ${row['Target 2']:,.2f}")

        rr = float(row["Risk/Reward"])
        rr_label = (
            "Excellent" if rr >= 4
            else "Very good" if rr >= 3
            else "Good" if rr >= 2
            else "Fair" if rr >= 1.5
            else "Poor—wait for a better entry"
        )
        st.info(
            f"Risk/reward guide: **{rr:.2f}:1 — {rr_label}.** "
            "Around 2:1 can be reasonable with strong evidence; 3:1 or better is generally more attractive."
        )
        st.caption(row["Summary"])


elif page == "🧪 Research Lab":
    st.markdown(
        '<div class="hero"><div class="eyebrow">Deep Investigation</div>'
        '<div class="hero-title">Research Lab</div>'
        '<p class="hero-copy">See the actual indicator values, the chart, and a plain-language legend explaining what good looks like.</p></div>',
        unsafe_allow_html=True,
    )

    default_ticker = st.session_state.get("research_ticker", "NBIS")
    c1, c2 = st.columns([1, 1])
    ticker = c1.text_input("Ticker", value=default_ticker).upper().strip()
    period = c2.selectbox("Chart period", ["3mo", "6mo", "1y", "2y"], index=1)

    if not ticker:
        st.info("Enter a ticker.")
        st.stop()

    try:
        with st.spinner(f"Building the {ticker} research file..."):
            data = research_data(ticker, period)
    except Exception as exc:
        st.error(f"Research data could not be loaded: {exc}")
        st.stop()

    if data.empty:
        st.error("No market data was returned for that ticker.")
        st.stop()

    st.plotly_chart(research_chart(data, ticker), use_container_width=True)

    cards = indicator_cards(data)
    st.subheader("Indicator numbers and interpretation")
    for card in cards:
        with st.expander(
            f"{card['name']} · {card['value']} · {card['status']}",
            expanded=card["name"] == "EMA 20",
        ):
            a, b = st.columns([1, 2])
            a.metric(card["name"], card["value"])
            a.markdown(f'<span class="score-chip">{card["status"]}</span>', unsafe_allow_html=True)
            b.write(f"**Actual context:** {card['actuals']}")
            b.success(f"**What generally looks good:** {card['good']}")
            b.warning(f"**Caution:** {card['caution']}")
            b.info(f"**Why Sherlock watches it:** {card['why']}")

    st.caption(
        "Indicator ranges are guides, not universal rules. Sherlock combines trend, momentum, "
        "volume, entry location, and risk/reward instead of relying on one indicator."
    )


elif page == "🏠 Command Center":
    st.markdown(
        f'<div class="hero"><div class="eyebrow">Command Center</div>'
        f'<div class="hero-title">Good to see you, {user.display_name}</div>'
        '<p class="hero-copy">Portfolio status and saved investigations. The Morning Scanner is now your primary starting point.</p></div>',
        unsafe_allow_html=True,
    )
    df = trades()
    x = enrich(df)
    m = summary(df)
    open_df = (
        x.loc[
            x["status"].astype(str).str.lower().eq("open")
            & ~x["archived"].fillna(False).astype(bool)
        ].copy()
        if not x.empty else x
    )
    a, b, c, d = st.columns(4)
    a.metric("Open positions", len(open_df))
    b.metric("Realized P&L", f"${m['pnl']:,.2f}")
    c.metric("Win rate", "—" if pd.isna(m["win_rate"]) else f"{m['win_rate']:.1%}")
    d.metric("Adherence", "—" if pd.isna(m["adherence"]) else f"{m['adherence']:.0f}%")
    st.info("Start each morning in **Morning Scanner**, then open the highest-priority names in **Research Lab**.")


elif page == "💼 Live Portfolio":
    st.markdown(
        '<div class="hero"><div class="eyebrow">Portfolio Intelligence</div>'
        '<div class="hero-title">Live Portfolio</div>'
        '<p class="hero-copy">Read-only tracking using delayed third-party prices. LTP never places, changes, or cancels orders.</p></div>',
        unsafe_allow_html=True,
    )
    x = enrich(trades())
    open_df = (
        x.loc[
            x["status"].astype(str).str.lower().eq("open")
            & ~x["archived"].fillna(False).astype(bool)
        ].copy()
        if not x.empty else x
    )
    if open_df.empty:
        st.info("No open positions are stored.")
    else:
        if st.button("Refresh delayed quotes"):
            clear_quote_cache()
            st.rerun()
        tickers = tuple(sorted(open_df["ticker"].astype(str).str.upper().unique()))
        quotes = quote_snapshot(tickers)
        portfolio = build_live_portfolio(open_df, quotes)
        totals = portfolio_totals(portfolio)
        a, b, c, d = st.columns(4)
        a.metric("Cost basis", f"${totals['cost_basis']:,.2f}")
        b.metric("Market value", f"${totals['market_value']:,.2f}")
        c.metric(
            "Unrealized P&L",
            f"${totals['unrealized']:,.2f}",
            delta=None if pd.isna(totals["return_pct"]) else f"{totals['return_pct']:+.2%}",
        )
        d.metric("Open positions", len(portfolio))
        st.dataframe(portfolio, hide_index=True, use_container_width=True)


elif page == "🕵️ Sherlock Cases":
    st.markdown(
        '<div class="hero"><div class="eyebrow">Case Board</div>'
        '<div class="hero-title">Sherlock Case Files</div>'
        '<p class="hero-copy">Reconstruct the technical evidence that existed when a stored position was opened.</p></div>',
        unsafe_allow_html=True,
    )
    x = enrich(trades())
    if x.empty:
        st.info("No positions are available for investigation.")
    else:
        for _, row in x.iterrows():
            with st.container(border=True):
                st.subheader(f"{row['ticker']} · {row['status']}")
                snapshot = decode_snapshot(row.get("case_snapshot"))
                if snapshot is None:
                    if st.button("Investigate entry", key=f"case_{row['id']}"):
                        with st.spinner("Reconstructing the evidence..."):
                            snapshot = reconstruct_case(
                                str(row["ticker"]),
                                pd.to_datetime(row["entry_date"]).date(),
                            )
                        if snapshot.get("status") == "Complete":
                            update_trade(
                                str(row["id"]),
                                user.user_id,
                                {
                                    "case_snapshot": snapshot_to_json(snapshot),
                                    "evidence_score": snapshot.get("evidence_score"),
                                    "case_verdict": snapshot.get("verdict"),
                                    "case_created_at": datetime.utcnow().isoformat(),
                                    "entry_rsi14": snapshot.get("rsi14"),
                                    "entry_ema20": snapshot.get("ema20"),
                                    "entry_ema50": snapshot.get("ema50"),
                                    "entry_volume_ratio": snapshot.get("relative_volume"),
                                    "reconstruction_status": "Complete",
                                    "reconstructed_at": datetime.utcnow().isoformat(),
                                },
                            )
                            st.rerun()
                        else:
                            st.error(snapshot.get("message", "Investigation failed."))
                else:
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Evidence Score", snapshot.get("evidence_score", "—"))
                    c2.metric("RSI", "—" if snapshot.get("rsi14") is None else f"{snapshot['rsi14']:.1f}")
                    c3.metric(
                        "Relative Volume",
                        "—" if snapshot.get("relative_volume") is None else f"{snapshot['relative_volume']:.2f}×",
                    )
                    st.write(f"**Verdict:** {snapshot.get('verdict', 'Unknown')}")
                    for evidence in snapshot.get("evidence", []):
                        st.write(f"• {evidence}")


elif page == "📊 Analytics":
    st.markdown(
        '<div class="hero"><div class="eyebrow">Performance</div>'
        '<div class="hero-title">Analytics</div>'
        '<p class="hero-copy">Review realized results and decision discipline.</p></div>',
        unsafe_allow_html=True,
    )
    df = trades()
    chart = curve(df)
    if chart.empty:
        st.info("Closed positions are needed to populate the realized performance curve.")
    else:
        st.plotly_chart(
            px.line(chart, x="Date", y="Cumulative P&L", markers=True),
            use_container_width=True,
        )


elif page == "🔄 Broker Data":
    st.markdown(
        '<div class="hero"><div class="eyebrow">Read Only</div>'
        '<div class="hero-title">E*TRADE Data Connection</div>'
        '<p class="hero-copy">LTP will read holdings, balances, and transaction history. It will never place or modify orders.</p></div>',
        unsafe_allow_html=True,
    )
    st.info(
        "The next broker milestone will add a reliable E*TRADE CSV import first, followed by "
        "official read-only OAuth sync after developer credentials are available."
    )
    st.success("Existing Supabase positions remain available in Portfolio and Sherlock.")


elif page == "🔒 Privacy & Sharing":
    st.title("Privacy & Sharing")
    try:
        privacy = load_privacy(user.user_id)
    except Exception as exc:
        st.error(str(exc))
        st.stop()
    with st.form("privacy"):
        share_balance = st.toggle("Share exact dollar results", privacy["share_balance"])
        share_holdings = st.toggle("Share holdings", privacy["share_holdings"])
        share_details = st.toggle("Share full trade details", privacy["share_trade_details"])
        submitted = st.form_submit_button("Save")
    if submitted:
        save_privacy(
            user.user_id,
            {
                "share_balance": share_balance,
                "share_holdings": share_holdings,
                "share_trade_details": share_details,
                "share_performance_summary": privacy["share_performance_summary"],
                "share_strategy_stats": privacy["share_strategy_stats"],
            },
        )
        st.success("Privacy settings saved.")


elif page == "✨ What's New":
    st.title("v1.1 — Sherlock Awakens")
    st.markdown(
        """
        - Morning Scanner is now the first page after login
        - Curated AI and technology universe
        - Evidence Score and Opportunity Score
        - High-movement and relative-volume ranking
        - Balanced entry planning zones
        - Tight, balanced, and wider stop areas
        - Potential resistance/target areas
        - Risk/reward rating and legend
        - Research Lab with candlesticks, EMA 9/20/50/200, volume, RSI, and MACD
        - Indicator cards show the actual number, status, what good looks like, and warning conditions
        - No real trade execution controls
        """
    )


elif page == "⚙️ Admin":
    st.title("Administrator")
    st.success("Sherlock Awakens is active.")
    st.write(f"Default scanner universe: {len(DEFAULT_UNIVERSE)} symbols.")
