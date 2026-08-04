from __future__ import annotations

from datetime import date, datetime
import json

import pandas as pd
import plotly.express as px
import streamlit as st

from ltp.analytics import enrich, summary, curve
from ltp.auth import init_auth, current_user, sign_in, sign_out
from ltp.config import APP_NAME, MOTTO, SHERLOCK_MOTTO, STRATEGIES
from ltp.database import (
    load_trades,
    insert_trade,
    update_trade,
    load_privacy,
    save_privacy,
)
from ltp.client import get_supabase
from ltp.market_data import reconstruct_case, quote_snapshot, clear_quote_cache
from ltp.portfolio import build_live_portfolio, portfolio_totals
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
    .stApp { background: radial-gradient(circle at 80% -10%, #17304e 0%, #07111f 42%, #040a12 100%); color:#eef3f8; }
    .block-container { padding-top:1.15rem; padding-bottom:3rem; max-width:1500px; }
    [data-testid="stSidebar"] { background:linear-gradient(180deg,#0c1828 0%,#07111f 100%); border-right:1px solid rgba(214,173,75,.18); }
    [data-testid="stMetric"] { background:linear-gradient(145deg,rgba(21,39,62,.96),rgba(10,22,37,.96)); border:1px solid rgba(214,173,75,.22); border-radius:18px; padding:16px; box-shadow:0 12px 34px rgba(0,0,0,.22); }
    [data-testid="stMetricLabel"] { color:#9eacc0; }
    [data-testid="stMetricValue"] { color:#f4d47f; }
    .stButton>button, .stFormSubmitButton>button { border-radius:12px; border:1px solid #d6ad4b; background:linear-gradient(135deg,#d6ad4b,#a87518); color:#07111f; font-weight:800; }
    .stButton>button:hover, .stFormSubmitButton>button:hover { border-color:#f6d77e; color:#07111f; box-shadow:0 0 22px rgba(214,173,75,.3); }
    [data-testid="stDataFrame"] { border:1px solid rgba(214,173,75,.18); border-radius:14px; overflow:hidden; }
    div[data-baseweb="tab-list"] { gap:.3rem; }
    button[data-baseweb="tab"] { border-radius:10px 10px 0 0; }
    h1,h2,h3 { letter-spacing:-.02em; }
    .hero { background:linear-gradient(135deg,rgba(18,34,55,.92),rgba(8,18,31,.96)); border:1px solid rgba(214,173,75,.26); border-radius:24px; padding:24px 28px; margin-bottom:18px; box-shadow:0 20px 50px rgba(0,0,0,.26); }
    .eyebrow { color:#d6ad4b; text-transform:uppercase; letter-spacing:.18em; font-size:.75rem; font-weight:800; }
    .hero-title { font-size:2.15rem; font-weight:850; margin:.25rem 0; }
    .hero-copy { color:#a7b4c6; margin:0; }
    .status-pill { display:inline-block; padding:7px 12px; border-radius:999px; background:rgba(53,196,106,.12); color:#65dc91; border:1px solid rgba(53,196,106,.28); font-weight:700; }
    @media(max-width:700px){ .block-container{padding-left:.7rem;padding-right:.7rem}.hero{padding:18px}.hero-title{font-size:1.55rem}.stButton button{min-height:44px} }
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
        st.markdown('<div class="hero"><div class="eyebrow">Private family trading intelligence</div><div class="hero-title">Evidence Over Emotion</div><p class="hero-copy">Investigate every trade. Learn from every decision. Grow with discipline.</p></div>', unsafe_allow_html=True)
        st.subheader("Welcome back")
        st.caption("Sign in to open your secure trading command center.")
        with st.form("login"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Enter the platform", type="primary", use_container_width=True)
        if submitted:
            ok, message = sign_in(email, password)
            if ok: st.rerun()
            st.error(message)
        st.markdown('<span class="status-pill">● Secure Supabase cloud</span>', unsafe_allow_html=True)
    st.stop()


with st.sidebar:
    st.image("assets/ltp_logo.png", use_container_width=True)
    st.markdown(f"### {APP_NAME}")
    st.write(f"**{user.display_name}**")
    st.caption("Administrator" if user.role == "admin" else "Investor")

    pages = [
        "🏠 Command Center",
        "📈 Trading Workspace",
        "💼 Live Portfolio",
        "📊 Analytics",
        "🕵️ Sherlock",
        "🔒 Privacy & Sharing",
        "✨ What's New",
    ]

    if user.role == "admin":
        pages.append("⚙️ Admin")

    page = st.radio(
        "Navigation",
        pages,
        label_visibility="collapsed",
    )

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


if page == "🏠 Command Center":
    st.markdown(f'<div class="hero"><div class="eyebrow">Command Center</div><div class="hero-title">Good to see you, {user.display_name}</div><p class="hero-copy">Your portfolio, process, and Sherlock investigations in one place.</p></div>', unsafe_allow_html=True)

    df = trades()
    enriched = enrich(df)
    metrics = summary(df)

    open_df = (
        enriched.loc[
            enriched["status"].astype(str).str.lower().eq("open")
            & ~enriched["archived"].fillna(False).astype(bool)
        ].copy()
        if not enriched.empty
        else enriched
    )

    a, b, c, d = st.columns(4)
    a.metric("Open positions", len(open_df))
    b.metric("Realized P&L", f"${metrics['pnl']:,.2f}")
    c.metric(
        "Win rate",
        "—"
        if pd.isna(metrics["win_rate"])
        else f"{metrics['win_rate']:.1%}",
    )
    d.metric(
        "Strategy adherence",
        "—"
        if pd.isna(metrics["adherence"])
        else f"{metrics['adherence']:.0f}%",
    )

    chart = curve(df)
    if chart.empty:
        st.info("Close a trade to begin the performance chart.")
    else:
        st.plotly_chart(
            px.line(
                chart,
                x="Date",
                y="Cumulative P&L",
                markers=True,
            ),
            use_container_width=True,
        )

    st.subheader("Open positions")

    if open_df.empty:
        st.info("No open positions.")
    else:
        st.dataframe(
            open_df[
                [
                    "ticker",
                    "account_type",
                    "strategy",
                    "entry_date",
                    "entry_price",
                    "quantity",
                ]
            ],
            hide_index=True,
            use_container_width=True,
        )


elif page == "📈 Trading Workspace":
    st.markdown('<div class="hero"><div class="eyebrow">Trading</div><div class="hero-title">Trading Workspace</div><p class="hero-copy">Record, import, review, and close positions with a disciplined workflow.</p></div>', unsafe_allow_html=True)

    new_tab, open_tab, history_tab = st.tabs(
        [
            "Open or import trade",
            "Close open trade",
            "History",
        ]
    )

    with new_tab:
        with st.form("new_trade"):
            c1, c2, c3 = st.columns(3)

            account = c1.selectbox(
                "Account",
                ["Real", "Paper"],
            )

            ticker = c2.text_input("Ticker").upper().strip()

            strategy = c3.selectbox(
                "Strategy",
                STRATEGIES,
            )

            c1, c2, c3 = st.columns(3)

            entry_date = c1.date_input(
                "Entry date",
                date.today(),
            )

            entry_price = c2.number_input(
                "Entry price",
                min_value=0.0,
                step=0.01,
            )

            quantity = c3.number_input(
                "Shares/contracts",
                min_value=0.0,
                step=1.0,
            )

            reason = st.text_area("Why did you enter?")

            imported = st.checkbox(
                "This is an existing brokerage position"
            )

            broker = (
                st.selectbox(
                    "Broker",
                    ["E*TRADE", "Robinhood", "Other"],
                )
                if imported
                else None
            )

            submitted = st.form_submit_button(
                "Save open trade",
                type="primary",
                use_container_width=True,
            )

        if submitted:
            if not ticker or entry_price <= 0 or quantity <= 0:
                st.error(
                    "Ticker, price, and quantity are required."
                )
            else:
                payload = {
                    "user_id": user.user_id,
                    "owner_name": user.display_name,
                    "account_type": account,
                    "ticker": ticker,
                    "strategy": strategy,
                    "entry_date": entry_date.isoformat(),
                    "entry_price": float(entry_price),
                    "quantity": float(quantity),
                    "exit_date": None,
                    "exit_price": None,
                    "stop_price": None,
                    "target_price": None,
                    "reason": reason,
                    "notes": "",
                    "plan_followed": "Yes",
                    "confidence": 50,
                    "status": "Open",
                    "archived": False,
                    "close_reason": None,
                    "lesson": None,
                    "imported_position": imported,
                    "source_broker": broker,
                    "entry_rsi14": None,
                    "entry_ema20": None,
                    "entry_ema50": None,
                    "entry_volume_ratio": None,
                    "reconstruction_status": "Pending",
                    "reconstructed_at": None,
                    "case_snapshot": None,
                    "evidence_score": None,
                    "case_verdict": None,
                    "case_created_at": None,
                }

                try:
                    insert_trade(payload)
                    st.success("Trade saved permanently.")
                except Exception as exc:
                    st.error(f"Could not save trade: {exc}")

    with open_tab:
        enriched = enrich(trades())

        open_df = (
            enriched.loc[
                enriched["status"]
                .astype(str)
                .str.lower()
                .eq("open")
            ].copy()
            if not enriched.empty
            else enriched
        )

        if open_df.empty:
            st.info("No open trades.")
        else:
            for _, row in open_df.iterrows():
                with st.container(border=True):
                    st.subheader(
                        f"{row['ticker']} · "
                        f"Entry ${row['entry_price']:,.2f}"
                    )

                    with st.form(f"close_{row['id']}"):
                        c1, c2 = st.columns(2)

                        exit_date = c1.date_input(
                            "Exit date",
                            date.today(),
                            key=f"d{row['id']}",
                        )

                        exit_price = c2.number_input(
                            "Exit price",
                            min_value=0.01,
                            value=float(row["entry_price"]),
                            key=f"p{row['id']}",
                        )

                        followed = st.selectbox(
                            "Followed plan?",
                            ["Yes", "Mostly", "Partly", "No"],
                            key=f"f{row['id']}",
                        )

                        lesson = st.text_area(
                            "Lesson",
                            key=f"l{row['id']}",
                        )

                        close = st.form_submit_button(
                            "Close trade"
                        )

                    if close:
                        try:
                            update_trade(
                                str(row["id"]),
                                user.user_id,
                                {
                                    "exit_date": exit_date.isoformat(),
                                    "exit_price": float(exit_price),
                                    "status": "Closed",
                                    "plan_followed": followed,
                                    "lesson": lesson,
                                    "close_reason": "Manual decision",
                                },
                            )
                            st.success("Trade closed.")
                            st.rerun()
                        except Exception as exc:
                            st.error(
                                f"Could not close trade: {exc}"
                            )

    with history_tab:
        enriched = enrich(trades())

        if enriched.empty:
            st.info("No trade history.")
        else:
            st.dataframe(
                enriched[
                    [
                        "ticker",
                        "entry_date",
                        "entry_price",
                        "quantity",
                        "exit_date",
                        "exit_price",
                        "pnl",
                        "return_pct",
                        "status",
                    ]
                ],
                hide_index=True,
                use_container_width=True,
            )


elif page == "💼 Live Portfolio":
    st.markdown('<div class="hero"><div class="eyebrow">Live Portfolio</div><div class="hero-title">Position Command Center</div><p class="hero-copy">Delayed market quotes, unrealized performance, exposure, and remaining risk.</p></div>', unsafe_allow_html=True)
    enriched = enrich(trades())
    open_df = enriched.loc[enriched["status"].astype(str).str.lower().eq("open") & ~enriched["archived"].fillna(False).astype(bool)].copy() if not enriched.empty else enriched
    if open_df.empty:
        st.info("No open positions.")
    else:
        if st.button("Refresh market quotes"):
            clear_quote_cache(); st.rerun()
        tickers=tuple(sorted(open_df["ticker"].astype(str).str.upper().unique()))
        with st.spinner("Loading delayed market quotes..."):
            quotes=quote_snapshot(tickers)
        portfolio=build_live_portfolio(open_df,quotes); totals=portfolio_totals(portfolio)
        a,b,c,d=st.columns(4)
        a.metric("Cost basis",f"${totals['cost_basis']:,.2f}")
        b.metric("Market value",f"${totals['market_value']:,.2f}")
        c.metric("Unrealized P&L",f"${totals['unrealized']:,.2f}",delta=None if pd.isna(totals["return_pct"]) else f"{totals['return_pct']:+.2%}")
        d.metric("Open positions",len(portfolio))
        st.dataframe(portfolio,hide_index=True,use_container_width=True,column_config={"Entry":st.column_config.NumberColumn(format="$%.2f"),"Current":st.column_config.NumberColumn(format="$%.2f"),"Cost basis":st.column_config.NumberColumn(format="$%.2f"),"Market value":st.column_config.NumberColumn(format="$%.2f"),"Unrealized P&L":st.column_config.NumberColumn(format="$%.2f"),"Return":st.column_config.NumberColumn(format="percent"),"Stop":st.column_config.NumberColumn(format="$%.2f"),"Target":st.column_config.NumberColumn(format="$%.2f"),"Distance to stop":st.column_config.NumberColumn(format="percent"),"Distance to target":st.column_config.NumberColumn(format="percent"),"Remaining R/R":st.column_config.NumberColumn(format="%.2f")})
        allocation=portfolio.dropna(subset=["Market value"])
        if not allocation.empty:
            fig=px.pie(allocation,names="Ticker",values="Market value",hole=.55,title="Portfolio allocation")
            fig.update_layout(paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='rgba(0,0,0,0)',font_color='#eaf0f7')
            st.plotly_chart(fig,use_container_width=True)
        st.caption("Quotes are delayed third-party data and may differ from your brokerage execution quote.")

elif page == "📊 Analytics":
    st.markdown('<div class="hero"><div class="eyebrow">Analytics</div><div class="hero-title">Performance Intelligence</div><p class="hero-copy">Turn completed trades into measurable lessons.</p></div>', unsafe_allow_html=True)

    df = trades()
    chart = curve(df)

    if chart.empty:
        st.info("Close trades to populate analytics.")
    else:
        st.plotly_chart(
            px.line(
                chart,
                x="Date",
                y="Cumulative P&L",
                markers=True,
            ),
            use_container_width=True,
        )


elif page == "🕵️ Sherlock":
    st.markdown('<div class="hero"><div class="eyebrow">Sherlock Intelligence</div><div class="hero-title">Case Files</div><p class="hero-copy">The market leaves clues. Sherlock reconstructs and scores the evidence.</p></div>', unsafe_allow_html=True)
    st.caption(SHERLOCK_MOTTO)

    enriched = enrich(trades())

    if enriched.empty:
        st.info("No trades are available for investigation.")
    else:
        for _, row in enriched.iterrows():
            with st.container(border=True):
                case_status = (
                    "Open Case"
                    if str(row["status"]).lower() == "open"
                    else "Closed Case"
                )

                st.subheader(
                    f"{row['ticker']} · {case_status}"
                )

                st.caption(
                    f"Entry "
                    f"{pd.to_datetime(row['entry_date']).date()} · "
                    f"${float(row['entry_price']):,.2f} · "
                    f"{row['strategy']}"
                )

                snapshot = decode_snapshot(
                    row.get("case_snapshot")
                )

                if snapshot is None:
                    if st.button(
                        "Investigate entry",
                        key=f"investigate_{row['id']}",
                        use_container_width=True,
                    ):
                        with st.spinner(
                            "Sherlock is reconstructing the evidence..."
                        ):
                            snapshot = reconstruct_case(
                                str(row["ticker"]),
                                pd.to_datetime(
                                    row["entry_date"]
                                ).date(),
                            )

                        if snapshot.get("status") == "Complete":
                            try:
                                update_trade(
                                    str(row["id"]),
                                    user.user_id,
                                    {
                                        "case_snapshot": snapshot_to_json(
                                            snapshot
                                        ),
                                        "evidence_score": snapshot.get(
                                            "evidence_score"
                                        ),
                                        "case_verdict": snapshot.get(
                                            "verdict"
                                        ),
                                        "case_created_at": (
                                            datetime.utcnow().isoformat()
                                        ),
                                        "entry_rsi14": snapshot.get(
                                            "rsi14"
                                        ),
                                        "entry_ema20": snapshot.get(
                                            "ema20"
                                        ),
                                        "entry_ema50": snapshot.get(
                                            "ema50"
                                        ),
                                        "entry_volume_ratio": snapshot.get(
                                            "relative_volume"
                                        ),
                                        "reconstruction_status": (
                                            "Complete"
                                        ),
                                        "reconstructed_at": (
                                            datetime.utcnow().isoformat()
                                        ),
                                    },
                                )
                                st.success(
                                    "Case file created and saved."
                                )
                                st.rerun()
                            except Exception as exc:
                                st.error(
                                    f"Could not save case file: {exc}"
                                )
                        else:
                            st.error(
                                snapshot.get(
                                    "message",
                                    "Investigation failed.",
                                )
                            )
                else:
                    c1, c2, c3, c4 = st.columns(4)

                    c1.metric(
                        "Evidence Score",
                        snapshot.get("evidence_score", "—"),
                    )

                    c2.metric(
                        "RSI 14",
                        "—"
                        if snapshot.get("rsi14") is None
                        else f"{snapshot['rsi14']:.1f}",
                    )

                    c3.metric(
                        "Relative Volume",
                        "—"
                        if snapshot.get("relative_volume") is None
                        else (
                            f"{snapshot['relative_volume']:.2f}×"
                        ),
                    )

                    c4.metric(
                        "5-Day Return",
                        "—"
                        if snapshot.get("week_return") is None
                        else f"{snapshot['week_return']:+.1%}",
                    )

                    st.markdown(
                        "### Verdict: "
                        f"{snapshot.get('verdict', 'Unknown')}"
                    )

                    st.caption(
                        "Market date used: "
                        f"{snapshot.get('market_date_used', 'Unknown')}"
                    )

                    indicators = pd.DataFrame(
                        [
                            {
                                "Indicator": "Entry close",
                                "Value": snapshot.get("close"),
                            },
                            {
                                "Indicator": "EMA 9",
                                "Value": snapshot.get("ema9"),
                            },
                            {
                                "Indicator": "EMA 20",
                                "Value": snapshot.get("ema20"),
                            },
                            {
                                "Indicator": "EMA 50",
                                "Value": snapshot.get("ema50"),
                            },
                            {
                                "Indicator": "EMA 200",
                                "Value": snapshot.get("ema200"),
                            },
                            {
                                "Indicator": "MACD",
                                "Value": snapshot.get("macd"),
                            },
                            {
                                "Indicator": "MACD signal",
                                "Value": snapshot.get("macd_signal"),
                            },
                            {
                                "Indicator": "MACD histogram",
                                "Value": snapshot.get(
                                    "macd_histogram"
                                ),
                            },
                            {
                                "Indicator": "ATR 14",
                                "Value": snapshot.get("atr14"),
                            },
                            {
                                "Indicator": "Gap %",
                                "Value": snapshot.get("gap_pct"),
                            },
                        ]
                    )

                    st.dataframe(
                        indicators,
                        hide_index=True,
                        use_container_width=True,
                    )

                    st.markdown("#### Evidence collected")

                    for item in snapshot.get("evidence", []):
                        st.write(f"• {item}")

                    st.info(snapshot.get("message", ""))

                    st.warning(
                        "This is reconstructed daily evidence. "
                        "It is not a record of the exact intraday "
                        "indicators visible when the trade was entered."
                    )


elif page == "🔒 Privacy & Sharing":
    st.markdown('<div class="hero"><div class="eyebrow">Privacy</div><div class="hero-title">You control what is shared</div><p class="hero-copy">Keep balances private while selectively sharing strategy and performance insights.</p></div>', unsafe_allow_html=True)

    try:
        privacy = load_privacy(user.user_id)
    except Exception as exc:
        st.error(f"Could not load privacy settings: {exc}")
        st.stop()

    with st.form("privacy"):
        share_balance = st.toggle(
            "Share exact dollar results",
            privacy["share_balance"],
        )

        share_holdings = st.toggle(
            "Share holdings",
            privacy["share_holdings"],
        )

        share_details = st.toggle(
            "Share full trade details",
            privacy["share_trade_details"],
        )

        submitted = st.form_submit_button("Save")

    if submitted:
        try:
            save_privacy(
                user.user_id,
                {
                    "share_balance": share_balance,
                    "share_holdings": share_holdings,
                    "share_trade_details": share_details,
                    "share_performance_summary": privacy[
                        "share_performance_summary"
                    ],
                    "share_strategy_stats": privacy[
                        "share_strategy_stats"
                    ],
                },
            )
            st.success("Privacy settings saved.")
        except Exception as exc:
            st.error(
                f"Could not save privacy settings: {exc}"
            )


elif page == "✨ What's New":
    st.title("What's New")
    st.subheader("v0.6.1 — Sherlock Case Files")
    st.markdown(
        """
        - Investigate open and closed trades
        - Reconstruct EMA 9, 20, 50, and 200
        - Calculate RSI 14
        - Calculate MACD, signal, and histogram
        - Calculate ATR 14
        - Measure relative volume
        - Measure entry-day gap
        - Measure five-session momentum
        - Save Evidence Score and verdict permanently
        """
    )


elif page == "⚙️ Admin":
    st.title("Administrator")
    st.success(
        "Supabase foundation and Sherlock Case Files are active."
    )
