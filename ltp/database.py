from datetime import datetime
import pandas as pd
from ltp.client import get_supabase

TRADE_COLUMNS = [
    "id","user_id","owner_name","account_type","ticker","strategy",
    "entry_date","entry_price","quantity","exit_date","exit_price",
    "stop_price","target_price","reason","notes","plan_followed",
    "confidence","status","archived","close_reason","lesson",
    "imported_position","source_broker","entry_rsi14","entry_ema20",
    "entry_ema50","entry_volume_ratio","reconstruction_status",
    "reconstructed_at","created_at"
]

def load_trades(user_id: str) -> pd.DataFrame:
    result = (
        get_supabase().table("trades").select("*")
        .eq("user_id", user_id).order("entry_date", desc=True).execute()
    )
    return pd.DataFrame(result.data or [], columns=TRADE_COLUMNS)

def insert_trade(payload: dict):
    get_supabase().table("trades").insert(payload).execute()

def update_trade(trade_id: str, user_id: str, changes: dict):
    (
        get_supabase().table("trades").update(changes)
        .eq("id", trade_id).eq("user_id", user_id).execute()
    )

def load_privacy(user_id: str):
    defaults = {
        "share_balance": False,
        "share_holdings": False,
        "share_trade_details": False,
        "share_performance_summary": True,
        "share_strategy_stats": True,
    }
    result = (
        get_supabase().table("privacy_settings").select("*")
        .eq("user_id", user_id).maybe_single().execute()
    )
    return {**defaults, **(result.data or {})}

def save_privacy(user_id: str, settings: dict):
    get_supabase().table("privacy_settings").upsert({
        "user_id": user_id,
        **settings,
        "updated_at": datetime.utcnow().isoformat(),
    }).execute()
