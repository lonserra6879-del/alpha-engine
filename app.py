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
from ltp.market_data import reconstruct_case
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
    .block-container {
        padding-top: 1rem;
        padding-bottom: 3rem;
    }

    [data-testid="stMetric"] {
        border: 1px solid rgba(128, 128, 128, 0.25);
        border-radius: 14px;
        padding: 12px;
    }

    @media (max-width: 700px) {
        .block-container {
            padding-left: .7rem;
            padding-right: .7rem;
        }

        .stButton button {
            min-height: 44px;
        }
    }
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
    st.title(APP_NAME)
    st.caption(f'{MOTTO} · Sherlock: “{SHERLOCK_MOTTO}”')

    with st.form("login"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button(
            "Sign in",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        ok, message = sign_in(email, password)
        if ok:
            st.rerun()
        st.error(message)

    st.stop()


with st.sidebar:
    st.markdown(f"### {APP_NAME}")
    st.write(f"**{user.display_name}**")
    st.caption("Administrator" if user.role == "admin" else "Investor")

    pages = [
        "Dashboard",
        "Trading Workspace",
        "Portfolio",
        "Analytics",
        "Sherlock",
        "Privacy & Sharing",
        "What's New",
    ]

    if user.role == "admin":
        pages.append("Admin")

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


if page == "Dashboard":
    st.title(f"Welcome, {user.display_name}")

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


elif page == "Trading Workspace":
    st.title("Trading Workspace")

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


elif page == "Portfolio":
    st.title("Portfolio")

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
        st.info("No open positions.")
    else:
        st.dataframe(
            open_df[
                [
                    "ticker",
                    "quantity",
                    "entry_price",
                    "account_type",
                    "strategy",
                ]
            ],
            hide_index=True,
            use_container_width=True,
        )


elif page == "Analytics":
    st.title("Analytics")

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


elif page == "Sherlock":
    st.title("🕵️ Sherlock Case Files")
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


elif page == "Privacy & Sharing":
    st.title("Privacy & Sharing")

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


elif page == "What's New":
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


elif page == "Admin":
    st.title("Administrator")
    st.success(
        "Supabase foundation and Sherlock Case Files are active."
    )
