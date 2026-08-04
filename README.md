# Londoño Trading Platform v0.4 — Import Center

## New

- Dedicated Import Center
- E*TRADE CSV processing
- Robinhood CSV processing
- Generic CSV template
- Preview before import
- Duplicate detection
- Optional Sherlock entry-date reconstruction
- Existing-position workflow remains available in Trading Workspace

## Important limitation

Broker CSV exports do not always identify which sale belongs to which purchase lot. This release imports brokerage activity safely as separate records and warns when manual reconciliation may be needed.

## GitHub update

Replace:

- `app.py`
- `README.md`

The existing `requirements.txt` already contains the required packages.

## Demo credentials

Santiago:
- `santiago@demo.local`
- `Santiago123!`

Tommy:
- `tommy@demo.local`
- `Tommy123!`

Demo data disappears when the session resets.