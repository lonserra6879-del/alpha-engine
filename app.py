
from datetime import date, datetime
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

try:
    from supabase import create_client
except Exception:
    create_client = None

st.set_page_config(page_title="Londoño Trading Platform", page_icon="📈", layout="wide")
st.markdown("""
<style>
.block-container{padding-top:1rem;padding-bottom:3rem}
[data-testid="stMetric"]{border:1px solid rgba(128,128,128,.25);border-radius:14px;padding:12px}
@media(max-width:700px){.block-container{padding-left:.7rem;padding-right:.7rem}h1{font-size:1.8rem!important}}
</style>
""", unsafe_allow_html=True)

DEMO_USERS={
 "santiago@demo.local":{"password":"Santiago123!","display_name":"Santiago","role":"admin","user_id":"demo-santiago"},
 "tommy@demo.local":{"password":"Tommy123!","display_name":"Tommy","role":"investor","user_id":"demo-tommy"},
}
STRATEGIES=["EMA Pullback","RSI Mean Reversion","Breakout","Friday Reversal","Earnings Momentum","Covered Call","Cash-Secured Put","Other"]

for k,v in {"auth":None,"demo_trades":[],"demo_privacy":{}}.items():
    if k not in st.session_state: st.session_state[k]=v

def sb():
    if create_client is None: return None
    try: return create_client(st.secrets["SUPABASE_URL"],st.secrets["SUPABASE_ANON_KEY"])
    except Exception: return None

def demo(): return sb() is None

def sign_in(email,password):
    if demo():
        u=DEMO_USERS.get(email.lower().strip())
        if u and u["password"]==password:
            st.session_state.auth=u.copy(); return True,"Signed in"
        return False,"Incorrect email or password"
    try:
        client=sb()
        r=client.auth.sign_in_with_password({"email":email,"password":password})
        p=client.table("profiles").select("id,display_name,role").eq("id",r.user.id).single().execute().data
        st.session_state.auth={"user_id":r.user.id,"display_name":p["display_name"],"role":p["role"],"email":r.user.email}
        return True,"Signed in"
    except Exception as e: return False,str(e)

def privacy(user_id):
    default={"share_balance":False,"share_holdings":False,"share_trade_details":False,"share_performance_summary":True,"share_strategy_stats":True}
    if demo(): return st.session_state.demo_privacy.get(user_id,default.copy())
    try:
        x=sb().table("privacy_settings").select("*").eq("user_id",user_id).maybe_single().execute().data
        return {**default,**(x or {})}
    except Exception: return default

def save_privacy(user_id,data):
    if demo(): st.session_state.demo_privacy[user_id]=data; return
    sb().table("privacy_settings").upsert({"user_id":user_id,**data,"updated_at":datetime.utcnow().isoformat()}).execute()

COLS=["id","user_id","owner_name","account_type","ticker","strategy","entry_date","entry_price","quantity","exit_date","exit_price","stop_price","target_price","reason","notes","plan_followed","confidence","status","created_at"]

def trades(user_id=None,all_users=False):
    if demo():
        data=st.session_state.demo_trades
        if user_id and not all_users: data=[x for x in data if x.get("user_id")==user_id]
        return pd.DataFrame(data,columns=COLS)
    try:
        q=sb().table("trades").select("*").order("entry_date",desc=True)
        if user_id and not all_users: q=q.eq("user_id",user_id)
        return pd.DataFrame(q.execute().data or [],columns=COLS)
    except Exception as e:
        st.warning(f"Could not load trades: {e}"); return pd.DataFrame(columns=COLS)

def add_trade(p):
    if demo():
        p={**p,"id":len(st.session_state.demo_trades)+1,"created_at":datetime.utcnow().isoformat()}
        st.session_state.demo_trades.append(p); return
    sb().table("trades").insert(p).execute()

def delete_trade(tid,uid):
    if demo():
        st.session_state.demo_trades=[x for x in st.session_state.demo_trades if not(str(x.get("id"))==str(tid) and x.get("user_id")==uid)]
    else:
        sb().table("trades").delete().eq("id",tid).eq("user_id",uid).execute()

def enrich(df):
    if df.empty: return df.copy()
    x=df.copy()
    for c in ["entry_price","quantity","exit_price","confidence"]: x[c]=pd.to_numeric(x[c],errors="coerce")
    x["entry_date"]=pd.to_datetime(x["entry_date"],errors="coerce")
    x["exit_date"]=pd.to_datetime(x["exit_date"],errors="coerce")
    x["is_closed"]=x["exit_price"].notna() & x["status"].astype(str).str.lower().eq("closed")
    x["pnl"]=np.where(x["is_closed"],(x["exit_price"]-x["entry_price"])*x["quantity"],np.nan)
    x["return_pct"]=np.where(x["is_closed"],x["exit_price"]/x["entry_price"]-1,np.nan)
    x["adherence_score"]=x["plan_followed"].map({"Yes":100,"Mostly":75,"Partly":50,"No":0}).fillna(50)
    return x

def metrics(df):
    x=enrich(df); closed=x[x.get("is_closed",False)] if not x.empty else x
    if closed.empty:
        return {"closed":0,"pnl":0.0,"win":np.nan,"avg":np.nan,"pf":np.nan,"adh":x["adherence_score"].mean() if not x.empty else np.nan}
    wins=closed.loc[closed.pnl>0,"pnl"].sum(); losses=-closed.loc[closed.pnl<0,"pnl"].sum()
    return {"closed":len(closed),"pnl":closed.pnl.sum(),"win":(closed.pnl>0).mean(),"avg":closed.return_pct.mean(),"pf":wins/losses if losses>0 else np.nan,"adh":x.adherence_score.mean()}

def curve(df):
    x=enrich(df); c=x[x.get("is_closed",False)].dropna(subset=["exit_date"]).sort_values("exit_date")
    if c.empty:return pd.DataFrame(columns=["Date","Cumulative P&L"])
    c["Cumulative P&L"]=c.pnl.cumsum()
    return c[["exit_date","Cumulative P&L"]].rename(columns={"exit_date":"Date"})

if st.session_state.auth is None:
    st.title("Londoño Trading Platform")
    st.caption("Evidence Over Emotion")
    if demo(): st.warning("Demo mode: data lasts only for this browser session until Supabase is connected.")
    c1,c2=st.columns(2)
    with c1:
        st.subheader("Family investing, built around evidence")
        st.write("Separate profiles, private portfolios, real and paper trades, learning, and mobile-friendly analytics.")
        if demo(): st.code("Santiago: santiago@demo.local / Santiago123!\nTommy: tommy@demo.local / Tommy123!")
    with c2:
        with st.form("login"):
            email=st.text_input("Email"); password=st.text_input("Password",type="password")
            go=st.form_submit_button("Sign in",type="primary",use_container_width=True)
        if go:
            ok,msg=sign_in(email,password)
            if ok: st.rerun()
            else: st.error(msg)
    st.stop()

u=st.session_state.auth
with st.sidebar:
    st.markdown("### Londoño Trading Platform"); st.caption("Evidence Over Emotion")
    st.write(f"**{u['display_name']}**"); st.caption("Administrator" if u["role"]=="admin" else "Investor")
    pages=["Dashboard","Trade Journal","Analytics","Privacy & Sharing","Alpha Academy"]+(["Admin"] if u["role"]=="admin" else [])
    page=st.radio("Navigation",pages,label_visibility="collapsed")
    st.caption("Demo mode" if demo() else "Secure cloud database")
    if st.button("Sign out",use_container_width=True): st.session_state.auth=None; st.rerun()

if page=="Dashboard":
    st.title(f"Welcome, {u['display_name']}")
    df=trades(u["user_id"]); m=metrics(df); x=enrich(df)
    c1,c2,c3,c4=st.columns(4)
    c1.metric("Closed trades",m["closed"]); c2.metric("Realized P&L",f"${m['pnl']:,.2f}")
    c3.metric("Win rate","—" if pd.isna(m["win"]) else f"{m['win']:.1%}")
    c4.metric("Strategy adherence","—" if pd.isna(m["adh"]) else f"{m['adh']:.0f}%")
    st.subheader("Performance")
    cv=curve(df)
    if cv.empty: st.info("Close at least one trade to begin the performance chart.")
    else: st.plotly_chart(px.line(cv,x="Date",y="Cumulative P&L",markers=True),use_container_width=True)
    st.subheader("Recent activity")
    if df.empty: st.info("Record your first real or paper trade.")
    else: st.dataframe(df[["account_type","ticker","strategy","entry_date","entry_price","quantity","status","plan_followed"]].head(10),hide_index=True,use_container_width=True)

elif page=="Trade Journal":
    st.title("Trade Journal")
    t1,t2,t3=st.tabs(["New trade","History","Import / export"])
    with t1:
        with st.form("trade",clear_on_submit=True):
            a,b,c=st.columns(3)
            account=a.selectbox("Account",["Real","Paper"]); ticker=b.text_input("Ticker").upper().strip(); strategy=c.selectbox("Strategy",STRATEGIES)
            a,b,c=st.columns(3)
            ed=a.date_input("Entry date",date.today()); ep=b.number_input("Entry price",min_value=0.0,step=.01); qty=c.number_input("Shares / contracts",min_value=0.0,step=1.0)
            a,b,c=st.columns(3)
            status=a.selectbox("Status",["Open","Closed"]); xd=b.date_input("Exit date",date.today()); xp=c.number_input("Exit price",min_value=0.0,step=.01)
            a,b,c=st.columns(3)
            stop=a.number_input("Planned stop",min_value=0.0,step=.01); target=b.number_input("Planned target",min_value=0.0,step=.01); conf=c.slider("Confidence",0,100,70)
            reason=st.text_area("Why are you entering?"); notes=st.text_area("Notes / lesson"); followed=st.selectbox("Did you follow the plan?",["Yes","Mostly","Partly","No"])
            save=st.form_submit_button("Save trade",type="primary",use_container_width=True)
        if save:
            if not ticker or ep<=0 or qty<=0 or(status=="Closed" and xp<=0): st.error("Enter ticker, entry price, quantity, and exit price for closed trades.")
            else:
                add_trade({"user_id":u["user_id"],"owner_name":u["display_name"],"account_type":account,"ticker":ticker,"strategy":strategy,"entry_date":ed.isoformat(),"entry_price":float(ep),"quantity":float(qty),"exit_date":xd.isoformat() if status=="Closed" else None,"exit_price":float(xp) if status=="Closed" else None,"stop_price":float(stop) if stop else None,"target_price":float(target) if target else None,"reason":reason,"notes":notes,"plan_followed":followed,"confidence":conf,"status":status})
                st.success("Trade saved.")
    with t2:
        df=enrich(trades(u["user_id"]))
        if df.empty: st.info("No trades yet.")
        else:
            st.dataframe(df[["id","account_type","ticker","strategy","entry_date","entry_price","quantity","exit_date","exit_price","pnl","return_pct","plan_followed","status"]],hide_index=True,use_container_width=True)
            with st.expander("Delete a trade"):
                tid=st.selectbox("Trade ID",df.id.astype(str).tolist())
                if st.button("Delete selected"): delete_trade(tid,u["user_id"]); st.rerun()
    with t3:
        df=trades(u["user_id"])
        st.download_button("Download my journal CSV",df.to_csv(index=False).encode(),f"{u['display_name']}_trades.csv","text/csv",use_container_width=True)
        st.file_uploader("Upload CSV (preview only in Sprint 1)",type=["csv"])

elif page=="Analytics":
    st.title("Analytics Center")
    df=trades(u["user_id"]); x=enrich(df); m=metrics(df)
    c1,c2,c3,c4=st.columns(4)
    c1.metric("Realized P&L",f"${m['pnl']:,.2f}"); c2.metric("Average return","—" if pd.isna(m["avg"]) else f"{m['avg']:.2%}")
    c3.metric("Profit factor","—" if pd.isna(m["pf"]) else f"{m['pf']:.2f}"); c4.metric("Adherence","—" if pd.isna(m["adh"]) else f"{m['adh']:.0f}%")
    tabs=st.tabs(["Performance","Strategy adherence","Strategies","Drawdown","Confidence","Family comparison"])
    with tabs[0]:
        cv=curve(df)
        if cv.empty: st.info("Close trades to create this chart.")
        else: st.plotly_chart(px.line(cv,x="Date",y="Cumulative P&L",markers=True,title="Cumulative realized P&L"),use_container_width=True)
    with tabs[1]:
        if x.empty: st.info("Record trades first.")
        else:
            ad=x.assign(Month=x.entry_date.dt.to_period("M").astype(str)).groupby("Month",as_index=False).adherence_score.mean()
            fig=px.line(ad,x="Month",y="adherence_score",markers=True,title="Strategy adherence over time"); fig.update_yaxes(range=[0,100])
            st.plotly_chart(fig,use_container_width=True)
    with tabs[2]:
        closed=x[x.get("is_closed",False)] if not x.empty else x
        if closed.empty: st.info("Close trades to compare strategies.")
        else:
            s=closed.groupby("strategy",as_index=False).agg(Trades=("id","count"),Win_Rate=("pnl",lambda z:(z>0).mean()),Average_Return=("return_pct","mean"),Total_PnL=("pnl","sum"),Adherence=("adherence_score","mean"))
            st.plotly_chart(px.bar(s,x="strategy",y="Total_PnL",title="P&L by strategy"),use_container_width=True); st.dataframe(s,hide_index=True,use_container_width=True)
    with tabs[3]:
        cv=curve(df)
        if cv.empty: st.info("Close trades to calculate drawdown.")
        else:
            cv["Drawdown"]=cv["Cumulative P&L"]-cv["Cumulative P&L"].cummax().clip(lower=0)
            st.plotly_chart(px.area(cv,x="Date",y="Drawdown",title="Realized drawdown"),use_container_width=True)
    with tabs[4]:
        closed=x[x.get("is_closed",False)].dropna(subset=["confidence","return_pct"]) if not x.empty else x
        if closed.empty: st.info("Close trades to compare confidence with results.")
        else: st.plotly_chart(px.scatter(closed,x="confidence",y="return_pct",color="strategy",hover_data=["ticker"],title="Confidence vs realized return"),use_container_width=True)
    with tabs[5]:
        all_df=trades(all_users=True)
        if all_df.empty: st.info("No family trade data yet.")
        else:
            rows=[]
            for owner,g in all_df.groupby("owner_name"):
                p=privacy(str(g.iloc[0].user_id)); mm=metrics(g)
                if owner==u["display_name"] or p["share_performance_summary"]:
                    rows.append({"Investor":owner,"Closed trades":mm["closed"],"Dollar P&L":f"${mm['pnl']:,.2f}" if(owner==u["display_name"] or p["share_balance"]) else "Private","Win rate":"—" if pd.isna(mm["win"]) else f"{mm['win']:.1%}","Adherence":"—" if pd.isna(mm["adh"]) else f"{mm['adh']:.0f}%"})
            st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True)

elif page=="Privacy & Sharing":
    st.title("Privacy & Sharing"); p=privacy(u["user_id"])
    with st.form("privacy"):
        bal=st.toggle("Share exact balance or dollar P&L",value=p["share_balance"])
        hold=st.toggle("Share holdings and sizes",value=p["share_holdings"])
        detail=st.toggle("Share full trade details",value=p["share_trade_details"])
        perf=st.toggle("Share performance percentages and win rate",value=p["share_performance_summary"])
        stats=st.toggle("Share strategy statistics",value=p["share_strategy_stats"])
        go=st.form_submit_button("Save settings",type="primary")
    if go:
        save_privacy(u["user_id"],{"share_balance":bal,"share_holdings":hold,"share_trade_details":detail,"share_performance_summary":perf,"share_strategy_stats":stats}); st.success("Saved.")
    st.info("Private by default. Each person controls what the other can see.")

elif page=="Alpha Academy":
    st.title("Alpha Academy")
    lesson=st.selectbox("Lesson",["RSI","Moving averages","Volume","Support and resistance","Risk management"])
    if lesson=="RSI":
        st.header("Relative Strength Index (RSI)")
        st.write("RSI is a momentum speedometer. It measures recent buying and selling pressure; it does not tell you whether the company is good.")
        st.dataframe(pd.DataFrame([["70–100","Strong momentum; possibly extended"],["50–70","Positive momentum"],["Around 50","Neutral"],["30–50","Weak momentum"],["0–30","Heavy selling; possibly oversold"]],columns=["RSI","Typical interpretation"]),hide_index=True,use_container_width=True)
        st.warning("A strong stock can remain above 70, and a weak stock can remain below 30. Context matters.")
    elif lesson=="Moving averages":
        st.header("Moving averages"); st.write("They smooth price to help reveal trend. The 20-day is short-term, 50-day intermediate, and 200-day long-term. They lag price.")
    elif lesson=="Volume":
        st.header("Volume"); st.write("Volume measures participation. A move on unusually high volume often carries more information than the same move on quiet volume.")
    elif lesson=="Support and resistance":
        st.header("Support and resistance"); st.write("These are zones where demand or supply previously changed. They are not exact magical prices.")
    else:
        st.header("Risk management"); st.write("Position size, planned exits, and diversification determine whether your strategy survives inevitable wrong trades.")

elif page=="Admin":
    st.title("Administrator")
    st.dataframe(pd.DataFrame([
        ["Record real and paper trades","Yes","Yes"],["Manage own privacy","Yes","Yes"],["Change scoring formulas","Yes","No"],["Approve model updates","Yes","No"],["Manage users","Yes","No"]
    ],columns=["Capability","Santiago","Tommy"]),hide_index=True,use_container_width=True)
    st.subheader("Sprint 1")
    st.write("✅ Logins and roles\n\n✅ Real and paper journals\n\n✅ Privacy controls\n\n✅ Mobile dashboard\n\n✅ Performance, adherence, strategy, drawdown and confidence charts\n\n⏳ Read-only brokerage connections: Sprint 2")
    if demo(): st.warning("Connect Supabase before entering real financial information.")
