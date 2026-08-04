from typing import Any
import streamlit as st
try:
    from supabase import create_client, Client
except Exception:
    create_client = None
    Client = Any

def get_supabase() -> Client:
    if create_client is None:
        raise RuntimeError("Supabase package is not installed.")
    try:
        url = str(st.secrets["SUPABASE_URL"]).strip().rstrip("/")
        key = str(st.secrets["SUPABASE_ANON_KEY"]).strip()
    except Exception as exc:
        raise RuntimeError("Streamlit Supabase secrets are missing.") from exc
    if not url.startswith("https://") or not url.endswith(".supabase.co"):
        raise RuntimeError("SUPABASE_URL must be the base project URL ending in .supabase.co")
    return create_client(url, key)
