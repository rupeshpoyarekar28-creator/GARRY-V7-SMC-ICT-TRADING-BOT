from datetime import datetime
from flask import Flask, render_template, jsonify, request
import requests
import re
import time

app = Flask(__name__)

DELTA_API = "https://api.india.delta.exchange"
TIMEOUT_SECONDS = 12

CONTRACT_TYPES = (
    "futures",
    "perpetual_futures"
)

SESSION = requests.Session()
SESSION.headers.update({
    "Accept": "application/json"
})


def delta_get(path, params=None):

    response = SESSION.get(
        f"{DELTA_API}{path}",
        params=params,
        timeout=TIMEOUT_SECONDS
    )

    response.raise_for_status()

    payload = response.json()

    if payload.get("success") is not True:
        raise ValueError("Delta API error")

    return payload


def get_all_active_products():

    products = []
    after = None
    seen = set()

    for _ in range(30):

        params = {
            "contract_types": ",".join(CONTRACT_TYPES),
            "states": "live",
            "page_size": 100
        }

        if after:
            params["after"] = after

        payload = delta_get(
            "/v2/products",
            params=params
        )

        page = payload.get("result", [])

        if not isinstance(page, list):
            raise ValueError("Invalid products response")

        for product in page:

            if (
                isinstance(product, dict)
                and product.get("state") == "live"
                and product.get("product_type") in CONTRACT_TYPES
                and product.get("symbol")
            ):

                products.append(product)

        cursor = (payload.get("meta") or {}).get("after")

        if not cursor or cursor in seen or not page:
            break

        seen.add(cursor)
        after = cursor

    unique = {
        item["symbol"]: item
        for item in products
    }

    return list(unique.values())


@app.route("/")
def dashboard():

    return render_template(
        "index.html",
        year=datetime.now().year
    )


@app.route("/api/markets")
def markets():

    try:

        products = get_all_active_products()

        payload = delta_get(
            "/v2/tickers",
            params={
                "contract_types": ",".join(CONTRACT_TYPES)
            }
        )

        tickers = payload.get("result", [])

        if not isinstance(tickers, list):
            raise ValueError("Invalid ticker response")

        ticker_map = {
            str(item.get("symbol", "")).upper(): item
            for item in tickers
            if isinstance(item, dict) and item.get("symbol")
        }

        market_data = []

        for product in products:

            symbol = product["symbol"].upper()

            ticker = ticker_map.get(symbol, {})

            market_data.append({

                "symbol": symbol,

                "product_id": product.get("id"),

                "contract_type": product.get("product_type"),

                "underlying_asset": product.get("underlying_asset"),

                "state": product.get("state"),

                "mark_price": ticker.get("mark_price"),

                "close": ticker.get("close"),

                "last_price": ticker.get("last_price"),

                "volume": ticker.get("volume"),

                "turnover": ticker.get("turnover"),

                "open_interest": ticker.get("open_interest")

            })

        market_data.sort(
            key=lambda x: x["symbol"]
        )

        ticker_count = sum(
            1 for item in market_data
            if any(
                item[key] is not None
                for key in (
                    "mark_price",
                    "close",
                    "last_price"
                )
            )
        )

        return jsonify({

            "ok": True,

            "updated_at": datetime.now().astimezone().isoformat(),

            "count": len(market_data),

            "ticker_count": ticker_count,

            "contract_types": list(CONTRACT_TYPES),

            "markets": market_data

        })

    except requests.Timeout:

        return jsonify({
            "ok": False,
            "error": "Delta API timeout"
        }), 504

    except requests.RequestException:

        app.logger.exception("Delta API connection error")

        return jsonify({
            "ok": False,
            "error": "Delta Exchange connection failed"
        }), 502

    except (ValueError, TypeError, KeyError):

        app.logger.exception("Market data processing error")

        return jsonify({
            "ok": False,
            "error": "Market data processing failed"
        }), 502


@app.route("/api/candles")
def historical_candles():

    symbol = request.args.get(
        "symbol",
        "BTCUSD"
    ).upper()

    resolution = request.args.get(
        "resolution",
        "1h"
    )

    allowed = {
        "1m", "3m", "5m", "15m",
        "30m", "1h", "2h", "4h",
        "6h", "12h", "1d", "1w"
    }

    if not re.fullmatch(r"[A-Z0-9-]{2,40}", symbol):
        return jsonify({
            "ok": False,
            "error": "Invalid symbol"
        }), 400

    if resolution not in allowed:
        return jsonify({
            "ok": False,
            "error": "Invalid resolution"
        }), 400

    try:

        end = int(
            request.args.get("end", time.time())
        )

        start = int(
            request.args.get(
                "start",
                end - 7 * 86400
            )
        )

        if start >= end or end - start > 2 * 365 * 86400:

            return jsonify({
                "ok": False,
                "error": "Invalid time range"
            }), 400

        payload = delta_get(
            "/v2/history/candles",
            params={
                "symbol": symbol,
                "resolution": resolution,
                "start": start,
                "end": end
            }
        )

        candles = payload.get("result")

        if not isinstance(candles, list):

            return jsonify({
                "ok": False,
                "error": "Invalid candle response"
            }), 502

        return jsonify({

            "ok": True,

            "symbol": symbol,

            "resolution": resolution,

            "count": len(candles),

            "candles": candles

        })

    except (ValueError, TypeError):

        return jsonify({
            "ok": False,
            "error": "Invalid timestamps"
        }), 400

    except requests.RequestException:

        return jsonify({
            "ok": False,
            "error": "Historical data unavailable"
        }), 502


if __name__ == "__main__":

    import os

    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "5000")),
        debug=False
    )
