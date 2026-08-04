from __future__ import annotations

import json
import pandas as pd

from ltp.market_data import reconstruct_case


def case_from_trade(row: pd.Series) -> dict:
    entry_date = pd.to_datetime(row["entry_date"]).date()
    return reconstruct_case(str(row["ticker"]), entry_date)


def snapshot_to_json(snapshot: dict) -> str:
    return json.dumps(snapshot, default=str)
