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
        raise RuntimeError("SUPABASE_URL must end in .supabase.co")

    if "supabase_client" not in st.session_state:
        st.session_state.supabase_client = create_client(url, key)

    return st.session_state.supabase_client

def clear_supabase_client() -> None:
    st.session_state.pop("supabase_client", None)
