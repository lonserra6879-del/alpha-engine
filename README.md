# Londoño Trading Platform v0.5

This release replaces Demo Mode with permanent Supabase authentication and storage.

## Upload to GitHub

Upload all files and folders from this package, including the complete `ltp` folder.

Required:
- `app.py`
- `requirements.txt`
- `supabase_schema.sql`
- `README.md`
- `ltp/`
- `.streamlit/secrets.toml.example`

Keep the real keys only in Streamlit Cloud Secrets.

## Test persistence

1. Log in with the real Supabase email and password.
2. Save a small test trade.
3. Sign out.
4. Refresh.
5. Sign in again.
6. Verify the trade is still present.
