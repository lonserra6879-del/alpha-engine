# Alpha Engine Web

A browser-based stock research dashboard designed for NBIS and other high-volatility AI stocks.

## Included stocks

NBIS, CRWV, NVDA, AMD, AVGO, PLTR, SMCI, ARM, IREN and APLD.

You can also enter any other Yahoo Finance ticker.

## Features

- Alpha Score from 0 to 100
- RSI, trend, pullback, streak, volume and volatility analysis
- Friday reversal study
- Historical pattern backtests over 1, 3, 5, 10 and 20 trading days
- AI-stock scanner
- Interactive price chart
- Conversational research box
- Excel report download

## Easiest deployment: Streamlit Community Cloud

1. Create a free GitHub account if you do not already have one.
2. Create a new GitHub repository.
3. Upload these files:
   - `app.py`
   - `requirements.txt`
4. Sign in to Streamlit Community Cloud using GitHub.
5. Select **Create app**.
6. Choose the repository and set the main file to `app.py`.
7. Deploy.

The service will provide a browser link you can bookmark. The computer used to access it does not need Python or administrator rights.

## Local testing, optional

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Important

This is an analytical research tool. It does not guarantee future returns and is not personalized financial advice. Newly listed stocks have limited samples, so apparent patterns may be unreliable.