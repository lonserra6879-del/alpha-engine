
from __future__ import annotations

from datetime import date, datetime
from typing import Any
import uuid

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

try:
    import yfinance as yf
except Exception:
    yf = None

try:
    from supabase import create_client, Client
except Exception:
    create_client = None
    Client = Any

st.set_page_config(
    page_title="Londoño Trading Platform",
    page_icon="🕵️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .block-container {padding-top: 1rem; padding-bottom: 3rem;}
    [data-testid="stMetric"] {
        border: 1px solid rgba(128,128,128,.25);
        border-radius: 14px;
        padding: 12px;
    }
    .trade-card {
        border: 1px solid rgba(128,128,128,.25);
        border-radius: 16px;
        padding: 16px;
        margin-bottom: 12px;
    }
    .muted {opacity:.72;}
    @media (max-width: 700px) {
        .block-container {padding-left:.7rem;padding-right:.7rem;}
        h1 {font-size:1.7rem!important;}
        .stButton button {min-height:44px;}
    }
    </style>
    """,
    unsafe_allow_html=True,
)

APP_NAME = "Londoño Trading Platform"
MOTTO = "Evidence Over Emotion"
SHERLOCK_MOTTO = "I don't guess. I investigate."

STRATEGIES = [
    "EMA Pullback",
    "RSI Mean Reversion",
    "Breakout",
    "Friday Reversal",
    "Earnings Momentum",
    "Covered Call",
    "Cash-Secured Put",
    "Other",
]

DEMO_USERS = {
    "santiago@demo.local": {
        "password": "Santiago123!",
        "display_name": "Santiago",
        "role": "admin",
        "user_id": "demo-santiago",
    },
    "tommy@demo.local": {
        "password": "Tommy123!",
        "display_name": "Tommy",
        "role": "investor",
        "user_id": "demo-tommy",
    },
}


def get_supabase() -> Client | None:
    if create_client is None:
        return None
    try:
        return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_ANON_KEY"])
    except Exception:
        return None


def demo_mode() -> bool:
    return get_supabase() is None


for key, value in {
    "auth": None,
    "demo_trades": [],
    "demo_privacy": {},
    "edit_trade_id": None,
    "close_trade_id": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = value


def sign_in(email: str, password: str) -> tuple[bool, str]:
    sb = get_supabase()
    if sb is None:
        account = DEMO_USERS.get(email.strip().lower())
        if account and account["password"] == password:
            st.session_state.auth = account.copy()
            return True, "Signed in."
        return False, "Incorrect email or password."

    try:
        result = sb.auth.sign_in_with_password({"email": email, "password": password})
        profile = (
            sb.table("profiles")
            .select("id,display_name,role")
            .eq("id", result.user.id)
            .single()
            .execute()
            .data
        )
        st.session_state.auth = {
            "user_id": result.user.id,
            "email": result.user.email,
            "display_name": profile["display_name"],
            "role": profile["role"],
        }
        return True, "Signed in."
    except Exception as exc:
        return False, f"Sign-in failed: {exc}"


def sign_out() -> None:
    sb = get_supabase()
    if sb is not None:
        try:
            sb.auth.sign_out()
        except Exception:
            pass
    st.session_state.auth = None
    st.rerun()


def load_trades(user_id: str | None = None, all_users: bool = False) -> pd.DataFrame:
    columns = [
        "id","user_id","owner_name","account_type","ticker","strategy",
        "entry_date","entry_price","quantity","exit_date","exit_price",
        "stop_price","target_price","reason","notes","plan_followed",
        "confidence","status","archived","close_reason","lesson",
        "imported_position","source_broker","entry_rsi14","entry_ema20",
        "entry_ema50","entry_volume_ratio","reconstruction_status",
        "reconstructed_at","created_at",
    ]
    sb = get_supabase()
    if sb is None:
        data = st.session_state.demo_trades
        if not all_users and user_id:
            data = [r for r in data if r.get("user_id") == user_id]
        return pd.DataFrame(data, columns=columns)

    try:
        query = sb.table("trades").select("*").order("entry_date", desc=True)
        if not all_users and user_id:
            query = query.eq("user_id", user_id)
        result = query.execute()
        return pd.DataFrame(result.data or [], columns=columns)
    except Exception as exc:
        st.warning(f"Could not load trades: {exc}")
        return pd.DataFrame(columns=columns)


def insert_trade(payload: dict) -> None:
    sb = get_supabase()
    if sb is None:
        row = payload.copy()
        row["id"] = str(uuid.uuid4())
        row["created_at"] = datetime.utcnow().isoformat()
        st.session_state.demo_trades.append(row)
        return
    sb.table("trades").insert(payload).execute()


def update_trade(trade_id: str, user_id: str, changes: dict) -> None:
    sb = get_supabase()
    if sb is None:
        for row in st.session_state.demo_trades:
            if str(row.get("id")) == str(trade_id) and row.get("user_id") == user_id:
                row.update(changes)
                return
        raise RuntimeError("Trade was not found.")
    (
        sb.table("trades")
        .update(changes)
        .eq("id", trade_id)
        .eq("user_id", user_id)
        .execute()
    )


def delete_trade(trade_id: str, user_id: str) -> None:
    sb = get_supabase()
    if sb is None:
        st.session_state.demo_trades = [
            r for r in st.session_state.demo_trades
            if not (str(r.get("id")) == str(trade_id) and r.get("user_id") == user_id)
        ]
        return
    sb.table("trades").delete().eq("id", trade_id).eq("user_id", user_id).execute()


def load_privacy(user_id: str) -> dict:
    defaults = {
        "share_balance": False,
        "share_holdings": False,
        "share_trade_details": False,
        "share_performance_summary": True,
        "share_strategy_stats": True,
    }
    sb = get_supabase()
    if sb is None:
        return st.session_state.demo_privacy.get(user_id, defaults.copy())
    try:
        result = sb.table("privacy_settings").select("*").eq("user_id", user_id).maybe_single().execute()
        return {**defaults, **(result.data or {})}
    except Exception:
        return defaults


def save_privacy(user_id: str, settings: dict) -> None:
    sb = get_supabase()
    if sb is None:
        st.session_state.demo_privacy[user_id] = settings.copy()
        return
    sb.table("privacy_settings").upsert({"user_id": user_id, **settings}).execute()


@st.cache_data(ttl=900, show_spinner=False)
def current_price(ticker: str) -> float | None:
    if yf is None or not ticker:
        return None
    try:
        hist = yf.download(ticker, period="5d", interval="1d", progress=False, auto_adjust=False)
        if hist.empty:
            return None
        close = hist["Close"]
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]
        return float(close.dropna().iloc[-1])
    except Exception:
        return None


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)
    avg_gain = gains.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = losses.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


@st.cache_data(ttl=3600, show_spinner=False)
def reconstruct_entry_snapshot(ticker: str, entry_date_value: date) -> dict:
    """Reconstruct end-of-day indicators using only information available by entry date."""
    if yf is None:
        return {"status": "Unavailable", "message": "Market-data package is unavailable."}

    start = pd.Timestamp(entry_date_value) - pd.Timedelta(days=180)
    end = pd.Timestamp(entry_date_value) + pd.Timedelta(days=7)

    try:
        hist = yf.download(
            ticker,
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
            auto_adjust=False,
            progress=False,
            actions=False,
            threads=False,
        )
        if hist.empty:
            return {"status": "Unavailable", "message": "No historical prices were returned."}

        if isinstance(hist.columns, pd.MultiIndex):
            hist.columns = hist.columns.get_level_values(0)

        hist.index = pd.to_datetime(hist.index).tz_localize(None)
        hist = hist.sort_index()
        cutoff = pd.Timestamp(entry_date_value)
        available = hist.loc[hist.index <= cutoff].copy()

        if available.empty:
            return {"status": "Unavailable", "message": "The entry date predates available price history."}

        available["EMA20"] = available["Close"].ewm(span=20, adjust=False).mean()
        available["EMA50"] = available["Close"].ewm(span=50, adjust=False).mean()
        available["RSI14"] = _rsi(available["Close"], 14)
        available["Volume20"] = available["Volume"].rolling(20).mean()
        available["VolumeRatio"] = available["Volume"] / available["Volume20"]

        row = available.iloc[-1]
        actual_market_date = available.index[-1]

        return {
            "status": "Complete",
            "market_date": actual_market_date.date().isoformat(),
            "close": float(row["Close"]),
            "rsi14": None if pd.isna(row["RSI14"]) else float(row["RSI14"]),
            "ema20": None if pd.isna(row["EMA20"]) else float(row["EMA20"]),
            "ema50": None if pd.isna(row["EMA50"]) else float(row["EMA50"]),
            "volume_ratio": None if pd.isna(row["VolumeRatio"]) else float(row["VolumeRatio"]),
            "above_ema20": bool(row["Close"] > row["EMA20"]) if pd.notna(row["EMA20"]) else None,
            "above_ema50": bool(row["Close"] > row["EMA50"]) if pd.notna(row["EMA50"]) else None,
            "message": (
                "Reconstructed from end-of-day market data available on or before "
                f"{actual_market_date.date().isoformat()}."
            ),
        }
    except Exception as exc:
        return {"status": "Unavailable", "message": f"Historical reconstruction failed: {exc}"}


def estimated_entry_score(snapshot: dict) -> int | None:
    if snapshot.get("status") != "Complete":
        return None

    score = 50
    rsi = snapshot.get("rsi14")
    volume_ratio = snapshot.get("volume_ratio")

    if rsi is not None:
        if 35 <= rsi <= 50:
            score += 14
        elif rsi < 30:
            score += 7
        elif rsi >= 75:
            score -= 12

    if snapshot.get("above_ema20"):
        score += 10
    else:
        score -= 5

    if snapshot.get("above_ema50"):
        score += 10
    else:
        score -= 7

    if volume_ratio is not None:
        if 1.1 <= volume_ratio <= 2.5:
            score += 8
        elif volume_ratio >= 3:
            score -= 3

    return int(np.clip(score, 0, 100))


def enrich_trades(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        x = df.copy()
        for c in ["is_closed","cost_basis","pnl","return_pct","holding_days","adherence_score"]:
            x[c] = pd.Series(dtype=float)
        return x

    x = df.copy()
    for col in ["entry_price","quantity","exit_price","stop_price","target_price","confidence"]:
        x[col] = pd.to_numeric(x[col], errors="coerce")
    for col in ["entry_date","exit_date"]:
        x[col] = pd.to_datetime(x[col], errors="coerce")

    x["archived"] = x["archived"].fillna(False).astype(bool)
    x["is_closed"] = x["status"].astype(str).str.lower().eq("closed") & x["exit_price"].notna()
    x["cost_basis"] = x["entry_price"] * x["quantity"]
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


def metrics(df: pd.DataFrame) -> dict:
    x = enrich_trades(df)
    closed = x[x["is_closed"]]
    if closed.empty:
        return {
            "closed":0,"pnl":0.0,"win_rate":np.nan,"avg_return":np.nan,
            "adherence":x["adherence_score"].mean() if not x.empty else np.nan,
        }
    return {
        "closed":len(closed),
        "pnl":closed["pnl"].sum(),
        "win_rate":(closed["pnl"] > 0).mean(),
        "avg_return":closed["return_pct"].mean(),
        "adherence":x["adherence_score"].mean(),
    }


def performance_curve(df: pd.DataFrame) -> pd.DataFrame:
    x = enrich_trades(df)
    closed = x[x["is_closed"]].dropna(subset=["exit_date"]).sort_values("exit_date")
    if closed.empty:
        return pd.DataFrame(columns=["Date","Cumulative P&L"])
    closed["Cumulative P&L"] = closed["pnl"].cumsum()
    return closed[["exit_date","Cumulative P&L"]].rename(columns={"exit_date":"Date"})


def sherlock_review(row: pd.Series) -> tuple[str, list[str]]:
    evidence = []
    score = 70

    if row.get("plan_followed") == "Yes":
        score += 15
        evidence.append("You followed the original plan.")
    elif row.get("plan_followed") == "No":
        score -= 20
        evidence.append("The trade departed substantially from the written plan.")

    rr = None
    if pd.notna(row.get("stop_price")) and pd.notna(row.get("target_price")):
        risk = row["entry_price"] - row["stop_price"]
        reward = row["target_price"] - row["entry_price"]
        if risk > 0:
            rr = reward / risk
            evidence.append(f"Planned reward-to-risk was {rr:.2f}:1.")
            score += 8 if rr >= 2 else -5

    if row.get("is_closed"):
        if row["pnl"] > 0:
            score += 8
            evidence.append(f"The position closed with a gain of {row['return_pct']:.2%}.")
        else:
            evidence.append(f"The position closed with a loss of {row['return_pct']:.2%}.")
        if row["holding_days"] <= 1:
            evidence.append("The holding period was very short; review whether the setup had time to develop.")

    score = int(np.clip(score, 0, 100))
    grade = "A" if score >= 90 else "B" if score >= 80 else "C" if score >= 65 else "D"
    return grade, evidence


# Login
if st.session_state.auth is None:
    st.title(APP_NAME)
    st.caption(f"{MOTTO} · Sherlock: “{SHERLOCK_MOTTO}”")
    if demo_mode():
        st.warning("Demo mode is active. Data lasts only for the current browser session.")
        st.code(
            "Santiago: santiago@demo.local / Santiago123!\n"
            "Tommy: tommy@demo.local / Tommy123!"
        )
    with st.form("login"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in", type="primary", use_container_width=True)
    if submitted:
        ok, msg = sign_in(email, password)
        if ok:
            st.rerun()
        st.error(msg)
    st.stop()

user = st.session_state.auth

with st.sidebar:
    st.markdown(f"### {APP_NAME}")
    st.caption(MOTTO)
    st.write(f"**{user['display_name']}**")
    st.caption("Administrator" if user["role"] == "admin" else "Investor")
    pages = [
        "Dashboard","Trading Workspace","Portfolio","Analytics",
        "Sherlock","Privacy & Sharing","Alpha Academy","What's New",
    ]
    if user["role"] == "admin":
        pages.append("Admin")
    page = st.radio("Navigation", pages, label_visibility="collapsed")
    st.divider()
    st.caption("Demo mode" if demo_mode() else "Secure cloud database")
    if st.button("Sign out", use_container_width=True):
        sign_out()


if page == "Dashboard":
    st.title(f"Welcome, {user['display_name']}")
    st.caption("The market is uncertain. Your process doesn't have to be.")

    trades = load_trades(user["user_id"])
    x = enrich_trades(trades)
    m = metrics(trades)
    open_count = int((x["status"].astype(str).str.lower() == "open").sum()) if not x.empty else 0

    a,b,c,d = st.columns(4)
    a.metric("Open positions", open_count)
    b.metric("Realized P&L", f"${m['pnl']:,.2f}")
    c.metric("Win rate", "—" if pd.isna(m["win_rate"]) else f"{m['win_rate']:.1%}")
    d.metric("Strategy adherence", "—" if pd.isna(m["adherence"]) else f"{m['adherence']:.0f}%")

    left,right = st.columns([1.45,1])
    with left:
        st.subheader("Performance")
        curve = performance_curve(trades)
        if curve.empty:
            st.info("Close a trade to begin the performance chart.")
        else:
            fig = px.line(curve, x="Date", y="Cumulative P&L", markers=True)
            fig.update_layout(height=360, margin=dict(l=10,r=10,t=20,b=10))
            st.plotly_chart(fig, use_container_width=True)
    with right:
        st.subheader("Sherlock's briefing")
        if x.empty:
            st.info("No case files yet. Record your first trade.")
        else:
            adherence = m["adherence"]
            if pd.notna(adherence) and adherence < 70:
                st.warning("A recurring process issue may be developing: strategy adherence is below 70%.")
            elif open_count:
                st.success(f"I found {open_count} open position(s) worth monitoring.")
            else:
                st.info("No open cases. Review your closed trades for lessons.")

    st.subheader("Open positions")
    open_positions = x[(x["status"].astype(str).str.lower() == "open") & (~x["archived"])] if not x.empty else x
    if open_positions.empty:
        st.info("No open positions.")
    else:
        for _, row in open_positions.iterrows():
            price = current_price(str(row["ticker"]))
            unrealized = None if price is None else (price - row["entry_price"]) * row["quantity"]
            pct = None if price is None else price / row["entry_price"] - 1
            st.markdown(
                f"""
                <div class="trade-card">
                <b>{row['ticker']}</b> · {row['account_type']} · {row['strategy']}<br>
                Entry: ${row['entry_price']:,.2f} · Qty: {row['quantity']:g} · Held: {int(row['holding_days'])} days<br>
                Current: {"Unavailable" if price is None else f"${price:,.2f}"} ·
                P&L: {"Unavailable" if unrealized is None else f"${unrealized:,.2f} ({pct:+.2%})"}
                </div>
                """,
                unsafe_allow_html=True,
            )


elif page == "Trading Workspace":
    st.title("Trading Workspace")
    st.caption("Open, edit, close, archive, and review every trade.")

    import_tab, new_tab, open_tab, history_tab = st.tabs(["Import existing position","Open a new trade","Manage open trades","History"])

    with import_tab:
        st.subheader("Import a position you already own")
        st.caption(
            "Enter only what you know from your brokerage statement. Sherlock will reconstruct "
            "the technical conditions using historical end-of-day data."
        )

        with st.form("import_existing_position"):
            c1, c2, c3 = st.columns(3)
            broker = c1.selectbox("Broker", ["E*TRADE", "Robinhood", "Other"])
            imported_ticker = c2.text_input("Ticker", key="import_ticker").upper().strip()
            imported_date = c3.date_input("Original purchase date", value=date.today())

            c1, c2, c3 = st.columns(3)
            average_cost = c1.number_input("Average cost per share", min_value=0.0, step=0.01)
            imported_quantity = c2.number_input("Current shares / contracts", min_value=0.0, step=1.0)
            imported_account = c3.selectbox("Position type", ["Real", "Paper"], index=0)

            original_reason = st.selectbox(
                "Why did you originally buy it?",
                [
                    "Long-term investment",
                    "Technical setup",
                    "AI growth opportunity",
                    "News or recommendation",
                    "Earnings opportunity",
                    "I do not remember",
                    "Other",
                ],
            )
            import_notes = st.text_area("Anything else you remember? (optional)")
            investigate = st.checkbox(
                "Have Sherlock reconstruct RSI, EMA20, EMA50, and volume conditions",
                value=True,
            )
            import_position = st.form_submit_button(
                "Import position", type="primary", use_container_width=True
            )

        if import_position:
            if not imported_ticker or average_cost <= 0 or imported_quantity <= 0:
                st.error("Ticker, average cost, and quantity are required.")
            else:
                snapshot = (
                    reconstruct_entry_snapshot(imported_ticker, imported_date)
                    if investigate
                    else {"status": "Not requested", "message": "Reconstruction was not requested."}
                )
                entry_score = estimated_entry_score(snapshot)

                payload = {
                    "user_id": user["user_id"],
                    "owner_name": user["display_name"],
                    "account_type": imported_account,
                    "ticker": imported_ticker,
                    "strategy": "Imported Existing Position",
                    "entry_date": imported_date.isoformat(),
                    "entry_price": float(average_cost),
                    "quantity": float(imported_quantity),
                    "exit_date": None,
                    "exit_price": None,
                    "stop_price": None,
                    "target_price": None,
                    "reason": original_reason,
                    "notes": import_notes,
                    "plan_followed": "Yes",
                    "confidence": int(entry_score or 50),
                    "status": "Open",
                    "archived": False,
                    "close_reason": None,
                    "lesson": None,
                    "imported_position": True,
                    "source_broker": broker,
                    "entry_rsi14": snapshot.get("rsi14"),
                    "entry_ema20": snapshot.get("ema20"),
                    "entry_ema50": snapshot.get("ema50"),
                    "entry_volume_ratio": snapshot.get("volume_ratio"),
                    "reconstruction_status": snapshot.get("status"),
                    "reconstructed_at": datetime.utcnow().isoformat(),
                }

                try:
                    insert_trade(payload)
                    st.success("Existing position imported.")
                    if snapshot.get("status") == "Complete":
                        score_text = "—" if entry_score is None else f"{entry_score}/100"
                        st.markdown("### 🕵️ Sherlock's reconstructed evidence")
                        a, b, c, d = st.columns(4)
                        a.metric("Estimated entry score", score_text)
                        b.metric(
                            "RSI 14",
                            "—" if snapshot.get("rsi14") is None else f"{snapshot['rsi14']:.1f}",
                        )
                        c.metric(
                            "EMA20",
                            "—" if snapshot.get("ema20") is None else f"${snapshot['ema20']:,.2f}",
                        )
                        d.metric(
                            "EMA50",
                            "—" if snapshot.get("ema50") is None else f"${snapshot['ema50']:,.2f}",
                        )
                        volume_text = (
                            "—"
                            if snapshot.get("volume_ratio") is None
                            else f"{snapshot['volume_ratio']:.2f}×"
                        )
                        st.write(
                            f"Entry-day close: **${snapshot['close']:,.2f}** · "
                            f"Volume versus 20-day average: **{volume_text}**"
                        )
                        st.caption(snapshot["message"])
                        st.info(
                            "This is reconstructed evidence, not information that was documented at the time. "
                            "It should remain labeled as reconstructed in future trade reviews."
                        )
                    else:
                        st.warning(snapshot.get("message", "The position was saved without reconstructed indicators."))
                except Exception as exc:
                    st.error(f"Could not import position: {exc}")

    with new_tab:
        with st.form("new_trade", clear_on_submit=True):
            c1,c2,c3 = st.columns(3)
            account_type = c1.selectbox("Account", ["Real","Paper"])
            ticker = c2.text_input("Ticker").upper().strip()
            strategy = c3.selectbox("Strategy", STRATEGIES)

            c1,c2,c3 = st.columns(3)
            entry_date = c1.date_input("Entry date", date.today())
            entry_price = c2.number_input("Entry price", min_value=0.0, step=0.01)
            quantity = c3.number_input("Shares / contracts", min_value=0.0, step=1.0)

            c1,c2,c3 = st.columns(3)
            stop_price = c1.number_input("Planned stop", min_value=0.0, step=0.01)
            target_price = c2.number_input("Planned target", min_value=0.0, step=0.01)
            confidence = c3.slider("Confidence", 0, 100, 70)

            reason = st.text_area("Why are you entering?")
            notes = st.text_area("Notes")
            save = st.form_submit_button("Open trade", type="primary", use_container_width=True)

        if save:
            if not ticker or entry_price <= 0 or quantity <= 0:
                st.error("Ticker, entry price, and quantity are required.")
            else:
                insert_trade({
                    "user_id":user["user_id"],
                    "owner_name":user["display_name"],
                    "account_type":account_type,
                    "ticker":ticker,
                    "strategy":strategy,
                    "entry_date":entry_date.isoformat(),
                    "entry_price":float(entry_price),
                    "quantity":float(quantity),
                    "exit_date":None,
                    "exit_price":None,
                    "stop_price":float(stop_price) if stop_price > 0 else None,
                    "target_price":float(target_price) if target_price > 0 else None,
                    "reason":reason,
                    "notes":notes,
                    "plan_followed":"Yes",
                    "confidence":int(confidence),
                    "status":"Open",
                    "archived":False,
                    "close_reason":None,
                    "lesson":None,
                    "imported_position":False,
                    "source_broker":None,
                    "entry_rsi14":None,
                    "entry_ema20":None,
                    "entry_ema50":None,
                    "entry_volume_ratio":None,
                    "reconstruction_status":"Not reconstructed",
                    "reconstructed_at":None,
                })
                st.success("Trade opened.")

    with open_tab:
        trades = enrich_trades(load_trades(user["user_id"]))
        open_df = trades[(trades["status"].astype(str).str.lower()=="open") & (~trades["archived"])] if not trades.empty else trades

        if open_df.empty:
            st.info("No open trades.")
        else:
            for _, row in open_df.iterrows():
                price = current_price(str(row["ticker"]))
                pnl = None if price is None else (price-row["entry_price"])*row["quantity"]
                pct = None if price is None else price/row["entry_price"]-1
                with st.container(border=True):
                    st.subheader(f"{row['ticker']} · {row['account_type']}")
                    a,b,c,d = st.columns(4)
                    a.metric("Entry", f"${row['entry_price']:,.2f}")
                    b.metric("Current", "—" if price is None else f"${price:,.2f}")
                    c.metric("Unrealized P&L", "—" if pnl is None else f"${pnl:,.2f}")
                    d.metric("Return", "—" if pct is None else f"{pct:+.2%}")
                    st.caption(f"{row['strategy']} · {int(row['holding_days'])} days held")

                    action1,action2,action3 = st.columns(3)
                    if action1.button("Close trade", key=f"close_{row['id']}", use_container_width=True):
                        st.session_state.close_trade_id = str(row["id"])
                    if action2.button("Edit trade", key=f"edit_{row['id']}", use_container_width=True):
                        st.session_state.edit_trade_id = str(row["id"])
                    if action3.button("Archive", key=f"archive_{row['id']}", use_container_width=True):
                        update_trade(str(row["id"]), user["user_id"], {"archived":True})
                        st.success("Trade archived.")
                        st.rerun()

                    if st.session_state.close_trade_id == str(row["id"]):
                        with st.form(f"close_form_{row['id']}"):
                            st.markdown("#### Close this trade")
                            x1,x2 = st.columns(2)
                            exit_date = x1.date_input("Exit date", date.today(), key=f"ed_{row['id']}")
                            exit_price = x2.number_input(
                                "Exit price", min_value=0.01,
                                value=float(price or row["entry_price"]),
                                step=0.01, key=f"ep_{row['id']}"
                            )
                            close_reason = st.selectbox(
                                "Reason for closing",
                                ["Target reached","Stop loss","Trend changed","Earnings risk",
                                 "Portfolio rebalance","Manual decision","Other"],
                                key=f"cr_{row['id']}"
                            )
                            followed = st.selectbox(
                                "Did you follow the plan?",
                                ["Yes","Mostly","Partly","No"],
                                key=f"pf_{row['id']}"
                            )
                            lesson = st.text_area("Biggest lesson", key=f"lesson_{row['id']}")
                            confirm = st.form_submit_button("Confirm close", type="primary")
                        if confirm:
                            update_trade(str(row["id"]), user["user_id"], {
                                "exit_date":exit_date.isoformat(),
                                "exit_price":float(exit_price),
                                "status":"Closed",
                                "close_reason":close_reason,
                                "plan_followed":followed,
                                "lesson":lesson,
                            })
                            st.session_state.close_trade_id = None
                            st.success("Trade closed. Dashboard and analytics updated.")
                            st.rerun()

                    if st.session_state.edit_trade_id == str(row["id"]):
                        with st.form(f"edit_form_{row['id']}"):
                            st.markdown("#### Edit trade")
                            e1,e2,e3 = st.columns(3)
                            edit_strategy = e1.selectbox(
                                "Strategy", STRATEGIES,
                                index=STRATEGIES.index(row["strategy"]) if row["strategy"] in STRATEGIES else 0,
                                key=f"es_{row['id']}"
                            )
                            edit_stop = e2.number_input(
                                "Stop", min_value=0.0,
                                value=float(row["stop_price"] or 0),
                                step=0.01, key=f"estop_{row['id']}"
                            )
                            edit_target = e3.number_input(
                                "Target", min_value=0.0,
                                value=float(row["target_price"] or 0),
                                step=0.01, key=f"etarget_{row['id']}"
                            )
                            edit_reason = st.text_area(
                                "Original reason", value=str(row["reason"] or ""),
                                key=f"er_{row['id']}"
                            )
                            edit_notes = st.text_area(
                                "Notes", value=str(row["notes"] or ""),
                                key=f"en_{row['id']}"
                            )
                            confirm_edit = st.form_submit_button("Save changes")
                        if confirm_edit:
                            update_trade(str(row["id"]), user["user_id"], {
                                "strategy":edit_strategy,
                                "stop_price":float(edit_stop) if edit_stop > 0 else None,
                                "target_price":float(edit_target) if edit_target > 0 else None,
                                "reason":edit_reason,
                                "notes":edit_notes,
                            })
                            st.session_state.edit_trade_id = None
                            st.success("Trade updated.")
                            st.rerun()

    with history_tab:
        trades = enrich_trades(load_trades(user["user_id"]))
        if trades.empty:
            st.info("No trade history.")
        else:
            show_archived = st.toggle("Show archived trades", False)
            view = trades if show_archived else trades[~trades["archived"]]
            cols = [
                "id","account_type","ticker","strategy","entry_date","entry_price",
                "quantity","exit_date","exit_price","pnl","return_pct",
                "holding_days","plan_followed","status"
            ]
            st.dataframe(
                view[cols],
                hide_index=True,
                use_container_width=True,
                column_config={
                    "entry_price":st.column_config.NumberColumn(format="$%.2f"),
                    "exit_price":st.column_config.NumberColumn(format="$%.2f"),
                    "pnl":st.column_config.NumberColumn(format="$%.2f"),
                    "return_pct":st.column_config.NumberColumn(format="percent"),
                },
            )
            if user["role"] == "admin":
                with st.expander("Administrator deletion"):
                    delete_id = st.selectbox("Trade ID", view["id"].astype(str).tolist())
                    if st.button("Permanently delete selected trade"):
                        delete_trade(delete_id, user["user_id"])
                        st.success("Trade deleted.")
                        st.rerun()


elif page == "Portfolio":
    st.title("Portfolio")
    trades = enrich_trades(load_trades(user["user_id"]))
    open_df = trades[(trades["status"].astype(str).str.lower()=="open") & (~trades["archived"])] if not trades.empty else trades

    if open_df.empty:
        st.info("Open trades appear here automatically.")
    else:
        rows = []
        for _, row in open_df.iterrows():
            price = current_price(str(row["ticker"]))
            rows.append({
                "Ticker":row["ticker"],
                "Account":row["account_type"],
                "Quantity":row["quantity"],
                "Average cost":row["entry_price"],
                "Current price":price,
                "Market value":None if price is None else price*row["quantity"],
                "Unrealized P&L":None if price is None else (price-row["entry_price"])*row["quantity"],
                "Return":None if price is None else price/row["entry_price"]-1,
                "Days held":row["holding_days"],
            })
        portfolio = pd.DataFrame(rows)
        st.dataframe(
            portfolio, hide_index=True, use_container_width=True,
            column_config={
                "Average cost":st.column_config.NumberColumn(format="$%.2f"),
                "Current price":st.column_config.NumberColumn(format="$%.2f"),
                "Market value":st.column_config.NumberColumn(format="$%.2f"),
                "Unrealized P&L":st.column_config.NumberColumn(format="$%.2f"),
                "Return":st.column_config.NumberColumn(format="percent"),
            }
        )
        if portfolio["Market value"].notna().any():
            allocation = portfolio.dropna(subset=["Market value"])
            fig = px.pie(allocation, names="Ticker", values="Market value", title="Open-position allocation")
            st.plotly_chart(fig, use_container_width=True)


elif page == "Analytics":
    st.title("Analytics Center")
    trades = enrich_trades(load_trades(user["user_id"]))
    m = metrics(trades)

    a,b,c,d = st.columns(4)
    a.metric("Closed trades", m["closed"])
    b.metric("Realized P&L", f"${m['pnl']:,.2f}")
    c.metric("Average return", "—" if pd.isna(m["avg_return"]) else f"{m['avg_return']:.2%}")
    d.metric("Adherence", "—" if pd.isna(m["adherence"]) else f"{m['adherence']:.0f}%")

    tabs = st.tabs(["Performance","Monthly results","Strategy adherence","Strategies","Holding period"])
    with tabs[0]:
        curve = performance_curve(trades)
        if curve.empty:
            st.info("Close trades to populate this chart.")
        else:
            st.plotly_chart(px.line(curve,x="Date",y="Cumulative P&L",markers=True),use_container_width=True)

    with tabs[1]:
        closed = trades[trades["is_closed"]].copy()
        if closed.empty:
            st.info("No closed trades.")
        else:
            closed["Month"] = closed["exit_date"].dt.to_period("M").astype(str)
            monthly = closed.groupby("Month",as_index=False)["pnl"].sum()
            st.plotly_chart(px.bar(monthly,x="Month",y="pnl",title="Monthly realized P&L"),use_container_width=True)

    with tabs[2]:
        if trades.empty:
            st.info("No trades.")
        else:
            adherence = (
                trades.assign(Month=trades["entry_date"].dt.to_period("M").astype(str))
                .groupby("Month",as_index=False)["adherence_score"].mean()
            )
            fig = px.line(adherence,x="Month",y="adherence_score",markers=True)
            fig.update_yaxes(range=[0,100],title="Adherence score")
            st.plotly_chart(fig,use_container_width=True)

    with tabs[3]:
        closed = trades[trades["is_closed"]]
        if closed.empty:
            st.info("No closed trades.")
        else:
            stats = closed.groupby("strategy",as_index=False).agg(
                Trades=("id","count"),
                PnL=("pnl","sum"),
                WinRate=("pnl",lambda s:(s>0).mean()),
                AvgReturn=("return_pct","mean"),
            )
            st.plotly_chart(px.bar(stats,x="strategy",y="PnL",title="P&L by strategy"),use_container_width=True)
            st.dataframe(stats,hide_index=True,use_container_width=True)

    with tabs[4]:
        closed = trades[trades["is_closed"]]
        if closed.empty:
            st.info("No closed trades.")
        else:
            st.plotly_chart(
                px.scatter(closed,x="holding_days",y="return_pct",color="strategy",
                           hover_data=["ticker"],title="Holding period versus return"),
                use_container_width=True
            )


elif page == "Sherlock":
    st.title("🕵️ Sherlock's Office")
    st.caption(SHERLOCK_MOTTO)
    trades = enrich_trades(load_trades(user["user_id"]))

    tab_open, tab_closed = st.tabs(["Open cases","Closed case reviews"])

    with tab_open:
        open_df = trades[trades["status"].astype(str).str.lower()=="open"] if not trades.empty else trades
        if open_df.empty:
            st.info("No open cases.")
        else:
            for _, row in open_df.iterrows():
                with st.container(border=True):
                    st.subheader(f"Case: {row['ticker']}")
                    findings = []
                    if pd.notna(row["stop_price"]) and pd.notna(row["target_price"]):
                        risk = row["entry_price"] - row["stop_price"]
                        reward = row["target_price"] - row["entry_price"]
                        if risk > 0:
                            findings.append(f"Planned reward-to-risk: {reward/risk:.2f}:1.")
                    findings.append(f"Confidence at entry: {int(row['confidence'])}%.")
                    findings.append(f"Held for {int(row['holding_days'])} day(s).")
                    for item in findings:
                        st.write(f"• {item}")
                    st.info(f"Original reason: {row['reason'] or 'Not recorded'}")
                    if bool(row.get("imported_position", False)):
                        st.caption(f"Imported from {row.get('source_broker') or 'broker'} · Reconstructed evidence")
                        i1, i2, i3 = st.columns(3)
                        i1.metric(
                            "Entry RSI",
                            "—" if pd.isna(row.get("entry_rsi14")) else f"{float(row['entry_rsi14']):.1f}",
                        )
                        i2.metric(
                            "Entry EMA20",
                            "—" if pd.isna(row.get("entry_ema20")) else f"${float(row['entry_ema20']):,.2f}",
                        )
                        i3.metric(
                            "Entry EMA50",
                            "—" if pd.isna(row.get("entry_ema50")) else f"${float(row['entry_ema50']):,.2f}",
                        )

    with tab_closed:
        closed = trades[trades["is_closed"]] if not trades.empty else trades
        if closed.empty:
            st.info("Close a trade to create Sherlock's first review.")
        else:
            for _, row in closed.sort_values("exit_date",ascending=False).iterrows():
                grade,evidence = sherlock_review(row)
                with st.container(border=True):
                    st.subheader(f"{row['ticker']} · Grade {grade}")
                    st.write(f"Result: ${row['pnl']:,.2f} ({row['return_pct']:+.2%})")
                    for item in evidence:
                        st.write(f"• {item}")
                    if row["lesson"]:
                        st.success(f"Recorded lesson: {row['lesson']}")


elif page == "Privacy & Sharing":
    st.title("Privacy & Sharing")
    p = load_privacy(user["user_id"])
    with st.form("privacy"):
        share_balance = st.toggle("Share exact dollar results",p["share_balance"])
        share_holdings = st.toggle("Share holdings and position sizes",p["share_holdings"])
        share_trade_details = st.toggle("Share full trade details",p["share_trade_details"])
        share_performance = st.toggle("Share performance percentages",p["share_performance_summary"])
        share_strategy = st.toggle("Share strategy statistics",p["share_strategy_stats"])
        saved = st.form_submit_button("Save settings",type="primary")
    if saved:
        save_privacy(user["user_id"],{
            "share_balance":share_balance,
            "share_holdings":share_holdings,
            "share_trade_details":share_trade_details,
            "share_performance_summary":share_performance,
            "share_strategy_stats":share_strategy,
        })
        st.success("Privacy settings saved.")


elif page == "Alpha Academy":
    st.title("Alpha Academy")
    lesson = st.selectbox("Lesson",["RSI","Moving averages","Volume","Risk/reward"])
    if lesson == "RSI":
        st.header("Relative Strength Index")
        st.write("RSI is a momentum speedometer. It measures recent buying and selling pressure.")
        st.dataframe(pd.DataFrame([
            {"Range":"70–100","Meaning":"Strong momentum; possibly extended"},
            {"Range":"50–70","Meaning":"Positive momentum"},
            {"Range":"30–50","Meaning":"Weak momentum"},
            {"Range":"0–30","Meaning":"Heavy selling; possibly oversold"},
        ]),hide_index=True,use_container_width=True)
        st.warning("RSI does not guarantee a reversal. Strong stocks can remain above 70.")
    elif lesson == "Moving averages":
        st.write("Moving averages smooth price to reveal trend. The 20-day is short-term, 50-day intermediate, and 200-day long-term.")
    elif lesson == "Volume":
        st.write("Volume measures participation. Large price moves on high volume usually carry more information than quiet moves.")
    else:
        st.write("Reward-to-risk compares potential upside with planned downside. A 2:1 setup risks $1 for a planned $2 reward.")


elif page == "What's New":
    st.title("What's New")
    st.subheader("Version 0.3 — Sherlock Import")
    st.markdown(
        """
        **New**
        - Import an existing E*TRADE, Robinhood, or other brokerage position
        - Sherlock reconstructs entry-date RSI, EMA20, EMA50, and volume context
        - Reconstructed evidence remains clearly labeled
        - Close an existing open trade
        - Edit strategy, stop, target, reason, and notes
        - Archive trades
        - Portfolio page with current-price estimates
        - Unrealized profit/loss
        - Holding-period calculations
        - Monthly performance chart
        - Sherlock's first open-case and closed-trade reviews
        - Improved mobile controls

        **Improved**
        - Empty-account handling
        - Trade-history workflow
        - Dashboard open-position cards
        """
    )


elif page == "Admin":
    st.title("Administrator")
    st.caption("Only Santiago can access this page.")
    st.dataframe(pd.DataFrame([
        {"Capability":"Record and close own trades","Santiago":"Yes","Tommy":"Yes"},
        {"Capability":"Manage own privacy","Santiago":"Yes","Tommy":"Yes"},
        {"Capability":"Archive own trades","Santiago":"Yes","Tommy":"Yes"},
        {"Capability":"Permanently delete trades","Santiago":"Yes","Tommy":"No"},
        {"Capability":"Change platform strategy","Santiago":"Yes","Tommy":"No"},
        {"Capability":"Approve machine-learning updates","Santiago":"Yes","Tommy":"No"},
    ]),hide_index=True,use_container_width=True)
