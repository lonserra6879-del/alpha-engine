
# Londoño Trading Platform — Sprint 1

## Built
- Separate Santiago and Tommy logins
- Santiago administrator role; Tommy investor role
- Real and paper trade journals
- Privacy controls
- Mobile-responsive dashboard
- Performance, strategy adherence, strategy P&L, drawdown, confidence and family-comparison views
- CSV export
- Alpha Academy starter lessons

## Upload to GitHub
Upload:
- `app.py`
- `requirements.txt`
- `supabase_schema.sql`
- `.streamlit/secrets.toml.example`
- `README.md`

Streamlit redeploys automatically.

## Demo mode
Until Supabase is connected:
- Santiago: `santiago@demo.local` / `Santiago123!`
- Tommy: `tommy@demo.local` / `Tommy123!`

Demo data is temporary. Do not enter real financial information in demo mode.

## Secure database setup
1. Create a free Supabase project.
2. Open SQL Editor and run `supabase_schema.sql`.
3. In Authentication → Users, create Santiago and Tommy.
4. Copy both user UUIDs.
5. Run:

```sql
insert into public.profiles(id,display_name,role) values
('SANTIAGO-UUID','Santiago','admin'),
('TOMMY-UUID','Tommy','investor');

insert into public.privacy_settings(user_id) values
('SANTIAGO-UUID'),('TOMMY-UUID');
```

6. In Streamlit → App settings → Secrets, add:

```toml
SUPABASE_URL="https://YOUR-PROJECT.supabase.co"
SUPABASE_ANON_KEY="YOUR-ANON-KEY"
```

Find these in Supabase Project Settings → API. Never use the service-role key.

## Phone access
Open the Streamlit link in Safari or Chrome. Use **Add to Home Screen** to make it behave like an app.

## Sprint 2
- Secure family-sharing database function
- Read-only E*TRADE connection
- Robinhood/Plaid or CSV synchronization
- Portfolio balances and holdings
- Expanded Academy and trade review
