from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import pandas as pd


STRATEGY_LIBRARY = [
    {
        "name": "EMA20 Pullback",
        "difficulty": "Beginner",
        "definition": "A stock in an established uptrend pulls back toward a rising 20-day EMA and then shows evidence of support.",
        "best_conditions": [
            "Price remains above the 50- and 200-day averages",
            "EMA20 is rising",
            "RSI is often between roughly 45 and 65",
            "Volume contracts during the pullback and expands on the bounce",
        ],
        "avoid_when": [
            "EMA20 is flat or falling",
            "The stock repeatedly closes below EMA20",
            "Earnings or major news is imminent",
            "The broader market trend is weak",
        ],
        "checklist": [
            "Uptrend intact",
            "Pullback near EMA20",
            "Support confirmed",
            "Risk/reward at least 2:1",
            "Stop placed below structural support",
        ],
        "case_ticker": "NVDA",
        "case_period": "2023-11 to 2024-03",
    },
    {
        "name": "Volume Breakout",
        "difficulty": "Intermediate",
        "definition": "Price moves above a clearly defined resistance level while participation rises materially above normal.",
        "best_conditions": [
            "Tight consolidation before the breakout",
            "Relative volume above 1.5×",
            "Close near the session high",
            "Strong sector and market backdrop",
        ],
        "avoid_when": [
            "Breakout volume is below average",
            "Price is already far above EMA20",
            "The breakout runs directly into nearby resistance",
            "The stock reverses below the breakout level",
        ],
        "checklist": [
            "Resistance clearly identified",
            "Volume confirms",
            "Entry is not excessively extended",
            "Invalidation level is defined",
            "Reward exceeds planned risk",
        ],
        "case_ticker": "PLTR",
        "case_period": "2024 historical breakout study",
    },
    {
        "name": "Momentum Continuation",
        "difficulty": "Intermediate",
        "definition": "A strong stock pauses briefly and resumes higher while trend, volume, and momentum remain constructive.",
        "best_conditions": [
            "EMA20 above EMA50",
            "MACD histogram positive or improving",
            "RSI strong but not extremely extended",
            "Short consolidation with controlled volatility",
        ],
        "avoid_when": [
            "Price is more than 8–10% above EMA20",
            "Momentum weakens while price rises",
            "Volume fades sharply",
            "Risk/reward falls below 1.5:1",
        ],
        "checklist": [
            "Trend aligned",
            "Momentum improving",
            "Pause is orderly",
            "Volume supports the move",
            "Stop and target are defined",
        ],
        "case_ticker": "AMD",
        "case_period": "2023–2024 historical continuation study",
    },
    {
        "name": "Trend Following",
        "difficulty": "Beginner",
        "definition": "Hold or add only while price structure, moving averages, and risk controls continue to support the prevailing trend.",
        "best_conditions": [
            "Price above EMA20, EMA50, and EMA200",
            "Higher highs and higher lows",
            "Pullbacks remain controlled",
            "Trailing stop follows structural support",
        ],
        "avoid_when": [
            "Major support breaks",
            "EMA20 and EMA50 roll over",
            "Fundamentals or news materially change the thesis",
            "Position risk becomes too concentrated",
        ],
        "checklist": [
            "Trend intact",
            "Position size appropriate",
            "Stop updated",
            "Earnings risk understood",
            "Exit rules written",
        ],
        "case_ticker": "MSFT",
        "case_period": "Long-term historical trend study",
    },
]


def academy_progress(completed_lessons: int, reviewed_cases: int, closed_paper_trades: int) -> dict:
    score = completed_lessons * 10 + reviewed_cases * 5 + closed_paper_trades * 15
    if score >= 150:
        rank = "Chief Investigator"
    elif score >= 100:
        rank = "Senior Detective"
    elif score >= 60:
        rank = "Detective"
    elif score >= 25:
        rank = "Analyst"
    else:
        rank = "Cadet"
    return {"score": score, "rank": rank}
