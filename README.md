# Londoño Trading Platform v0.3 — Sherlock Import

This release adds the first imported-position workflow.

## New workflow

Go to:

**Trading Workspace → Import existing position**

Enter:

- Broker
- Ticker
- Original purchase date
- Average cost
- Current shares
- What you remember about the reason for buying

Sherlock then reconstructs:

- RSI 14
- EMA 20
- EMA 50
- Volume relative to its 20-day average
- A preliminary estimated entry score

The evidence is always labeled **Reconstructed**, because it was calculated later and was not documented at the time of entry.

## GitHub update

Replace:

- `app.py`
- `requirements.txt`
- `supabase_schema.sql`
- `README.md`

Streamlit will redeploy automatically.

## Demo use

Demo records disappear when the app session resets.

Santiago:
- Email: `santiago@demo.local`
- Password: `Santiago123!`

Tommy:
- Email: `tommy@demo.local`
- Password: `Tommy123!`

## Supabase users

Run the new `supabase_schema.sql` in the Supabase SQL editor before using this release with permanent data. The upgrade statements add fields without deleting existing trades.

## Data limitation

Historical technical values use daily end-of-day prices. If a trade was entered intraday, these values approximate the market conditions and do not reproduce the exact intraday indicator reading.