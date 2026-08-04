from datetime import date, datetime
import pandas as pd
import plotly.express as px
import streamlit as st

from ltp.analytics import enrich, summary, curve
from ltp.auth import init_auth, current_user, sign_in, sign_out
from ltp.config import APP_NAME, MOTTO, SHERLOCK_MOTTO, STRATEGIES
from ltp.database import load_trades, insert_trade, update_trade, load_privacy, save_privacy
from ltp.client import get_supabase

st.set_page_config(page_title=APP_NAME, page_icon="🕵️", layout="wide")
init_auth()

st.markdown("""
<style>
.block-container {padding-top: 1rem; padding-bottom: 3rem;}
[data-testid="stMetric"] {border:1px solid rgba(128,128,128,.25);border-radius:14px;padding:12px;}
@media(max-width:700px){.block-container{padding-left:.7rem;padding-right:.7rem}.stButton button{min-height:44px}}
</style>
""", unsafe_allow_html=True)

try:
    get_supabase()
except Exception as exc:
    st.title(APP_NAME)
    st.error(str(exc))
    st.stop()

user = current_user()

if user is None:
    st.title(APP_NAME)
    st.caption(f"{MOTTO} · Sherlock: “{SHERLOCK_MOTTO}”")
    with st.form("login"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in", type="primary", use_container_width=True)
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
    pages = ["Dashboard","Trading Workspace","Portfolio","Analytics","Sherlock","Privacy & Sharing","What's New"]
    if user.role == "admin":
        pages.append("Admin")
    page = st.radio("Navigation", pages, label_visibility="collapsed")
    st.divider()
    st.success("Secure cloud database")
    if st.button("Sign out", use_container_width=True):
        sign_out()

def trades():
    try:
        return load_trades(user.user_id)
    except Exception as exc:
        st.error(f"Could not load trades: {exc}")
        return pd.DataFrame()

if page == "Dashboard":
    st.title(f"Welcome, {user.display_name}")
    df = trades()
    x = enrich(df)
    m = summary(df)
    open_df = x.loc[x["status"].astype(str).str.lower().eq("open") & ~x["archived"].fillna(False)] if not x.empty else x
    a,b,c,d = st.columns(4)
    a.metric("Open positions", len(open_df))
    b.metric("Realized P&L", f"${m['pnl']:,.2f}")
    c.metric("Win rate", "—" if pd.isna(m["win_rate"]) else f"{m['win_rate']:.1%}")
    d.metric("Strategy adherence", "—" if pd.isna(m["adherence"]) else f"{m['adherence']:.0f}%")
    chart = curve(df)
    if chart.empty:
        st.info("Close a trade to begin the performance chart.")
    else:
        st.plotly_chart(px.line(chart, x="Date", y="Cumulative P&L", markers=True), use_container_width=True)
    st.subheader("Open positions")
    if open_df.empty:
        st.info("No open positions.")
    else:
        st.dataframe(open_df[["ticker","account_type","strategy","entry_date","entry_price","quantity"]], hide_index=True, use_container_width=True)

elif page == "Trading Workspace":
    st.title("Trading Workspace")
    new_tab, open_tab, history_tab = st.tabs(["Open or import trade","Close open trade","History"])
    with new_tab:
        with st.form("new_trade"):
            c1,c2,c3 = st.columns(3)
            account = c1.selectbox("Account", ["Real","Paper"])
            ticker = c2.text_input("Ticker").upper().strip()
            strategy = c3.selectbox("Strategy", STRATEGIES)
            c1,c2,c3 = st.columns(3)
            entry_date = c1.date_input("Entry date", date.today())
            entry_price = c2.number_input("Entry price", min_value=0.0, step=0.01)
            quantity = c3.number_input("Shares/contracts", min_value=0.0, step=1.0)
            reason = st.text_area("Why did you enter?")
            imported = st.checkbox("This is an existing brokerage position")
            broker = st.selectbox("Broker", ["E*TRADE","Robinhood","Other"]) if imported else None
            submitted = st.form_submit_button("Save open trade", type="primary", use_container_width=True)
        if submitted:
            if not ticker or entry_price <= 0 or quantity <= 0:
                st.error("Ticker, price, and quantity are required.")
            else:
                payload = {
                    "user_id": user.user_id, "owner_name": user.display_name,
                    "account_type": account, "ticker": ticker, "strategy": strategy,
                    "entry_date": entry_date.isoformat(), "entry_price": float(entry_price),
                    "quantity": float(quantity), "exit_date": None, "exit_price": None,
                    "stop_price": None, "target_price": None, "reason": reason, "notes": "",
                    "plan_followed": "Yes", "confidence": 50, "status": "Open",
                    "archived": False, "close_reason": None, "lesson": None,
                    "imported_position": imported, "source_broker": broker,
                    "entry_rsi14": None, "entry_ema20": None, "entry_ema50": None,
                    "entry_volume_ratio": None, "reconstruction_status": "Pending",
                    "reconstructed_at": None,
                }
                try:
                    insert_trade(payload)
                    st.success("Trade saved permanently.")
                except Exception as exc:
                    st.error(f"Could not save trade: {exc}")
    with open_tab:
        x = enrich(trades())
        open_df = x.loc[x["status"].astype(str).str.lower().eq("open")] if not x.empty else x
        if open_df.empty:
            st.info("No open trades.")
        else:
            for _, row in open_df.iterrows():
                with st.container(border=True):
                    st.subheader(f"{row['ticker']} · Entry ${row['entry_price']:,.2f}")
                    with st.form(f"close_{row['id']}"):
                        c1,c2 = st.columns(2)
                        exit_date = c1.date_input("Exit date", date.today(), key=f"d{row['id']}")
                        exit_price = c2.number_input("Exit price", min_value=0.01, value=float(row["entry_price"]), key=f"p{row['id']}")
                        followed = st.selectbox("Followed plan?", ["Yes","Mostly","Partly","No"], key=f"f{row['id']}")
                        lesson = st.text_area("Lesson", key=f"l{row['id']}")
                        close = st.form_submit_button("Close trade")
                    if close:
                        update_trade(str(row["id"]), user.user_id, {
                            "exit_date": exit_date.isoformat(), "exit_price": float(exit_price),
                            "status": "Closed", "plan_followed": followed, "lesson": lesson,
                            "close_reason": "Manual decision",
                        })
                        st.success("Trade closed.")
                        st.rerun()
    with history_tab:
        x = enrich(trades())
        if x.empty:
            st.info("No trade history.")
        else:
            st.dataframe(x[["ticker","entry_date","entry_price","quantity","exit_date","exit_price","pnl","return_pct","status"]], hide_index=True, use_container_width=True)

elif page == "Portfolio":
    st.title("Portfolio")
    x = enrich(trades())
    open_df = x.loc[x["status"].astype(str).str.lower().eq("open")] if not x.empty else x
    if open_df.empty:
        st.info("No open positions.")
    else:
        st.dataframe(open_df[["ticker","quantity","entry_price","account_type","strategy"]], hide_index=True, use_container_width=True)

elif page == "Analytics":
    st.title("Analytics")
    df = trades()
    chart = curve(df)
    if chart.empty:
        st.info("Close trades to populate analytics.")
    else:
        st.plotly_chart(px.line(chart, x="Date", y="Cumulative P&L", markers=True), use_container_width=True)

elif page == "Sherlock":
    st.title("🕵️ Sherlock")
    x = enrich(trades())
    closed = x.loc[x["is_closed"].fillna(False)] if not x.empty else x
    if closed.empty:
        st.info("Close a trade to create a Sherlock review.")
    else:
        for _, row in closed.iterrows():
            with st.container(border=True):
                st.subheader(row["ticker"])
                st.write(f"Return: {row['return_pct']:+.2%}")
                st.write(f"Plan adherence: {row['plan_followed']}")
                if row["lesson"]:
                    st.success(f"Lesson: {row['lesson']}")

elif page == "Privacy & Sharing":
    st.title("Privacy & Sharing")
    privacy = load_privacy(user.user_id)
    with st.form("privacy"):
        share_balance = st.toggle("Share exact dollar results", privacy["share_balance"])
        share_holdings = st.toggle("Share holdings", privacy["share_holdings"])
        share_details = st.toggle("Share full trade details", privacy["share_trade_details"])
        submitted = st.form_submit_button("Save")
    if submitted:
        save_privacy(user.user_id, {
            "share_balance": share_balance,
            "share_holdings": share_holdings,
            "share_trade_details": share_details,
            "share_performance_summary": privacy["share_performance_summary"],
            "share_strategy_stats": privacy["share_strategy_stats"],
        })
        st.success("Privacy settings saved.")

elif page == "What's New":
    st.title("What's New")
    st.subheader("v0.5 — Supabase Foundation")
    st.write("Real Supabase login, permanent trade storage, modular code, and no demo mode.")

elif page == "Admin":
    st.title("Administrator")
    st.success("Supabase foundation is active.")
