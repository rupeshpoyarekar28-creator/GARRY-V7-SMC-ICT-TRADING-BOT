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

if __name__ == "__main__":
    # Local development server. For phone access, use a hosting provider
    # or run on a computer on the same Wi-Fi network.
    import os
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False)
