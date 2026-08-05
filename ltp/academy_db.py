from __future__ import annotations

from datetime import datetime
import pandas as pd

from ltp.client import get_supabase


def load_paper_trades(user_id: str) -> pd.DataFrame:
    result = (
        get_supabase()
        .table("paper_trades")
        .select("*")
        .eq("user_id", user_id)
        .order("entry_date", desc=True)
        .execute()
    )
    return pd.DataFrame(result.data or [])


def insert_paper_trade(payload: dict) -> None:
    get_supabase().table("paper_trades").insert(payload).execute()


def close_paper_trade(trade_id: str, user_id: str, changes: dict) -> None:
    (
        get_supabase()
        .table("paper_trades")
        .update(changes)
        .eq("id", trade_id)
        .eq("user_id", user_id)
        .execute()
    )


def load_academy_progress(user_id: str) -> pd.DataFrame:
    result = (
        get_supabase()
        .table("academy_progress")
        .select("*")
        .eq("user_id", user_id)
        .execute()
    )
    return pd.DataFrame(result.data or [])


def mark_lesson_complete(user_id: str, lesson_key: str) -> None:
    get_supabase().table("academy_progress").upsert(
        {
            "user_id": user_id,
            "lesson_key": lesson_key,
            "completed": True,
            "completed_at": datetime.utcnow().isoformat(),
        },
        on_conflict="user_id,lesson_key",
    ).execute()
