# Londoño Trading Platform v1.0 — Professional Visual Release

Complete drop-in release with:

- Premium navy, gold, and green visual system
- Branded login screen using the LTP logo
- Modern icon navigation
- Professional command-center dashboard
- Live delayed portfolio quotes and unrealized P&L
- Sherlock Case Files
- Mobile-responsive layout
- Existing Supabase authentication and permanent storage

## Update GitHub

Replace the repository contents with this release while keeping your real Supabase values only in Streamlit Cloud Secrets.

Run `database_upgrade_v1.sql` only if you did not already run the v0.6 Sherlock database upgrade. It is safe because it uses `add column if not exists`.

## Important

Market quotes are delayed third-party data and are not execution quotes.
