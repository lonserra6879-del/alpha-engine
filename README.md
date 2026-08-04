# Londoño Trading Platform v0.6 — Sherlock Case Files

## New

- Automatic historical entry reconstruction
- EMA 9, EMA 20, EMA 50, and EMA 200
- RSI 14
- MACD, signal, and histogram
- ATR 14
- Relative volume
- Entry-day gap
- Five-session momentum
- Evidence Score from 0 to 100
- Sherlock verdict and evidence list
- Permanent JSON case snapshot saved to Supabase
- Weekend and holiday dates use the last available market session

## Files

Upload or replace:

- `ltp/market_data.py`
- `ltp/sherlock.py`
- `ltp/database.py`

The file `APP_PATCH.txt` contains the exact Sherlock-page code and the small import/payload changes needed in `app.py`.

Run `supabase_v0_6_upgrade.sql` once in Supabase SQL Editor.

## Important

The analysis uses daily end-of-day market data. It reconstructs the general setup but cannot reproduce exact intraday indicator values.
