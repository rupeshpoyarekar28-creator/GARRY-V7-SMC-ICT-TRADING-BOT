from datetime import datetime
from flask import Flask, render_template, jsonify
import requests

app = Flask(__name__)

DELTA_API = "https://api.india.delta.exchange"
TIMEOUT_SECONDS = 8

@app.route("/")
def dashboard():
    return render_template("index.html", year=datetime.now().year)

@app.route("/api/markets")
def markets():
    """Read-only public market data. This route never places orders."""
    try:
        response = requests.get(
            f"{DELTA_API}/v2/tickers",
            params={"contract_types": "perpetual_futures,futures"},
            headers={"Accept": "application/json"},
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()

        if payload.get("success") is not True or not isinstance(payload.get("result"), list):
            return jsonify({
                "ok": False,
                "error": "Unexpected response from exchange API.",
                "updated_at": datetime.now().astimezone().isoformat(timespec="seconds")
            }), 502

        results = payload["result"]
        keywords = ("BTC", "ETH", "XAU", "GOLD")
        selected = []
        for item in results:
            symbol = str(item.get("symbol", "")).upper()
            if any(key in symbol for key in keywords):
                selected.append({
                    "symbol": item.get("symbol", "Unknown"),
                    "mark_price": item.get("mark_price"),
                    "close": item.get("close"),
                    "last_price": item.get("last_price"),
                    "volume": item.get("volume"),
                })

        # If the filter finds no matching instruments, show a small sample
        # rather than implying that BTC/Gold instruments must exist.
        if not selected:
            for item in results[:10]:
                selected.append({
                    "symbol": item.get("symbol", "Unknown"),
                    "mark_price": item.get("mark_price"),
                    "close": item.get("close"),
                    "last_price": item.get("last_price"),
                    "volume": item.get("volume"),
                })

        return jsonify({
            "ok": True,
            "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "count": len(selected),
            "markets": selected[:20],
        })
    except requests.Timeout:
        return jsonify({"ok": False, "error": "Exchange request timed out. Try again."}), 504
    except requests.RequestException:
        return jsonify({"ok": False, "error": "Could not connect to Delta Exchange India."}), 502
    except (ValueError, TypeError):
        return jsonify({"ok": False, "error": "Could not read exchange response."}), 502


from flask import request
import re
import time

@app.route("/api/candles")
def historical_candles():
    symbol = request.args.get("symbol", "BTCUSD").upper()
    resolution = request.args.get("resolution", "1h")

    allowed_resolutions = {
        "1m", "3m", "5m", "15m", "30m",
        "1h", "2h", "4h", "6h", "1d", "1w"
    }

    if not re.fullmatch(r"[A-Z0-9-]{2,40}", symbol):
        return jsonify({"ok": False, "error": "Invalid symbol"}), 400

    if resolution not in allowed_resolutions:
        return jsonify({"ok": False, "error": "Invalid resolution"}), 400

    try:
        end = int(request.args.get("end", time.time()))
        start = int(request.args.get("start", end - 7 * 86400))

        if start >= end or end - start > 2 * 365 * 86400:
            return jsonify({
                "ok": False,
                "error": "Invalid time range; maximum 2 years"
            }), 400

        response = requests.get(
            f"{DELTA_API}/v2/history/candles",
            params={
                "symbol": symbol,
                "resolution": resolution,
                "start": start,
                "end": end
            },
            headers={"Accept": "application/json"},
            timeout=TIMEOUT_SECONDS
        )
        response.raise_for_status()
        payload = response.json()

        if payload.get("success") is not True:
            return jsonify({
                "ok": False,
                "error": "Exchange did not return candle data"
            }), 502

        candles = payload.get("result")
        if not isinstance(candles, list):
            return jsonify({
                "ok": False,
                "error": "Unexpected candle response"
            }), 502

        return jsonify({
            "ok": True,
            "symbol": symbol,
            "resolution": resolution,
            "count": len(candles),
            "candles": candles
        })

    except (ValueError, TypeError):
        return jsonify({"ok": False, "error": "Invalid timestamps"}), 400
    except requests.RequestException:
        return jsonify({
            "ok": False,
            "error": "Historical market data unavailable"
        }), 502

if __name__ == "__main__":
    # Local development server. For phone access, use a hosting provider
    # or run on a computer on the same Wi-Fi network.
    import os
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False)
