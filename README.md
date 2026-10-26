# GARRY V7 Mobile Browser Dashboard

This is a mobile-friendly Flask web dashboard for Android browsers. It is a read-only starter.

## Included
- Responsive dark navy / teal UI with centered GARRY V7 header.
- Local $100 demo display (not a funded exchange account, not a simulated P&L engine).
- Flask endpoint that fetches public Delta Exchange India tickers with timeout and response validation.
- Explicit connection/error status; no fabricated fallback prices.
- No private API keys, no order placement, no live trading.

## Run on Android
A browser cannot run a Python Flask server by itself. You need a Python runtime app/environment that can run Flask, or host this app on a server and open its HTTPS URL in Chrome.

If using Termux:
1. Install Termux from a trusted official source.
2. In Termux, run:
   pkg update
   pkg install python
   pip install -r requirements.txt
3. Change into the extracted project directory and run:
   python app.py
4. Open http://127.0.0.1:5000 in Chrome on the same phone.

If your Android Python environment does not support Flask or local networking, deploy this project to a Python web host and open its HTTPS URL on your phone. Do not expose Flask's development server to the public internet.

## API
Public endpoint:
GET https://api.india.delta.exchange/v2/tickers?contract_types=perpetual_futures,futures

Check current official documentation at https://docs.delta.exchange/ before relying on endpoint fields. Instrument availability can change; the BTC/ETH/XAU/GOLD filter is only a convenience and does not guarantee Gold contracts are listed.

## Production work still required
Authentication, secure API credential storage, strategy engine, validated two-year historical candle retrieval, realistic backtesting with fees/slippage/funding, risk controls, and order execution. Live orders are not implemented.


## Deploy online so it opens on any phone/laptop
Recommended easiest path: Render + GitHub.

1. Upload the contents of this project to a GitHub repository (keep it private if preferred).
2. Sign in at https://render.com and create a **New Web Service**.
3. Connect the GitHub repository.
4. Use build command `pip install -r requirements.txt`.
5. Use start command `gunicorn app:app`.
6. Deploy, then use the HTTPS `onrender.com` URL Render provides. Open that URL on any device with internet.
7. Note: free hosting may sleep when idle and the first request may take longer. Confirm current pricing and plan limits before relying on it.

This ZIP includes a Render blueprint file and Procfile as deployment aids. A public URL has not been created by generating this source package; deployment requires your own hosting/GitHub account and explicit action.
