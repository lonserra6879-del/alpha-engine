# Londoño Trading Platform v0.2

## Main update

This version adds the complete basic trade lifecycle:

- Open trade
- Edit trade
- Close trade
- Archive trade
- Administrator deletion
- Automatic realized P&L
- Current-price estimates for open positions
- Unrealized P&L
- Holding period
- Portfolio allocation
- Sherlock's first trade reviews
- Mobile-friendly controls

## Updating GitHub

Replace:

- `app.py`
- `requirements.txt`
- `supabase_schema.sql`
- `README.md`

with the files in this package.

Streamlit should redeploy automatically.

## Demo accounts

Santiago:
- `santiago@demo.local`
- `Santiago123!`

Tommy:
- `tommy@demo.local`
- `Tommy123!`

Demo data is temporary.

## Existing Supabase project

Run the new `supabase_schema.sql` in Supabase SQL Editor. The `add column if not exists` commands upgrade the existing trades table without deleting saved records.

## Mobile use

Open the Streamlit URL in Safari or Chrome and choose **Add to Home Screen**.