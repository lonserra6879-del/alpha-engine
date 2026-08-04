from dataclasses import dataclass
import streamlit as st
from ltp.client import get_supabase

@dataclass
class AppUser:
    user_id: str
    email: str
    display_name: str
    role: str

def init_auth():
    if "app_user" not in st.session_state:
        st.session_state.app_user = None

def current_user():
    init_auth()
    return st.session_state.app_user

def sign_in(email: str, password: str):
    try:
        sb = get_supabase()
        result = sb.auth.sign_in_with_password({
            "email": email.strip().lower(),
            "password": password,
        })
        if not result.user or not result.session:
            return False, "Supabase did not return a valid session."
        profile_result = (
            sb.table("profiles")
            .select("id,display_name,role")
            .eq("id", result.user.id)
            .maybe_single()
            .execute()
        )
        profile = profile_result.data
        if not profile:
            return False, "Login worked, but your profiles table record was not found."
        st.session_state.app_user = AppUser(
            user_id=str(result.user.id),
            email=str(result.user.email or email),
            display_name=str(profile["display_name"]),
            role=str(profile["role"]),
        )
        return True, "Signed in."
    except Exception as exc:
        message = str(exc)
        if "invalid login credentials" in message.lower():
            return False, "The email or password is incorrect."
        return False, f"Sign-in failed: {message}"

def sign_out():
    try:
        get_supabase().auth.sign_out()
    except Exception:
        pass
    st.session_state.app_user = None
    st.rerun()
