
from datetime import datetime
from flask import Flask, render_template, jsonify, request
import requests
import re
import time
import logging

app = Flask(__name__)

DELTA_API = "https://api.india.delta.exchange"
TIMEOUT = 15

CONTRACT_TYPES = {
    "futures",
    "perpetual_futures"
}

SESSION = requests.Session()
SESSION.headers.update({
    "Accept": "application/json"
})

logging.basicConfig(level=logging.INFO)


def delta_get(path, params=None):

    response = SESSION.get(
        DELTA_API + path,
        params=params,
        timeout=TIMEOUT
    )

    response.raise_for_status()

    data = response.json()

    if data.get("success") is not True:
        raise ValueError(
            str(data.get("error", "Delta API error"))
        )

    return data


def get_all_products():

    all_products = []
    after = None
    seen = set()

    for page_number in range(100):

        params = {
            "page_size": 100
        }

        if after:
            params["after"] = after

        data = delta_get(
            "/v2/products",
            params=params
        )

        page = data.get("result", [])

        if not isinstance(page, list):
            raise ValueError(
                "Products response is not a list"
            )

        all_products.extend(page)

        meta = data.get("meta") or {}
        next_cursor = meta.get("after")

        if not next_cursor:
            break

        if next_cursor in seen:
            break

        if not page:
            break

        seen.add(next_cursor)
        after = next_cursor

    return all_products


def get_contract_type(product):

    value = (
        product.get("contract_type")
        or product.get("product_type")
        or product.get("type")
        or ""
    )

    return str(value).strip().lower()


def get_active_futures(products):

    selected = []

    for product in products:

        if not isinstance(product, dict):
            continue

        state = str(
            product.get("state", "")
        ).lower()

        contract_type = get_contract_type(product)

        if state != "live":
            continue

        if contract_type not in CONTRACT_TYPES:
            continue

        if not product.get("symbol"):
            continue

        selected.append(product)

    unique = {
        str(item["symbol"]).upper(): item
        for item in selected
    }

    return list(unique.values())


def get_all_tickers():

    data = delta_get("/v2/tickers")

    result = data.get("result", [])

    if not isinstance(result, list):
        raise ValueError(
            "Ticker response is not a list"
        )

    return result


@app.route("/")
def dashboard():

    return render_template(
        "index.html",
        year=datetime.now().year
    )


@app.route("/api/markets")
def markets():

    try:

        # Step 1: Fetch all products without filters
        all_products = get_all_products()

        # Step 2: Select live Futures and Perpetual Futures
        active_products = get_active_futures(
            all_products
        )

        # Step 3: Fetch all public tickers
        all_tickers = get_all_tickers()

        ticker_map = {
            str(item.get("symbol", "")).upper(): item
            for item in all_tickers
            if isinstance(item, dict)
            and item.get("symbol")
        }

        market_data = []

        for product in active_products:

            symbol = str(
                product["symbol"]
            ).upper()

            ticker = ticker_map.get(
                symbol,
                {}
            )

            market_data.append({

                "symbol": symbol,

                "product_id": product.get("id"),

                "contract_type": get_contract_type(
                    product
                ),

                "state": product.get("state"),

                "trading_status": product.get(
                    "trading_status"
                ),

                "underlying_asset": product.get(
                    "underlying_asset"
                ),

                "mark_price": ticker.get(
                    "mark_price"
                ),

                "close": ticker.get("close"),

                "last_price": ticker.get(
                    "last_price"
                ),

                "volume": ticker.get("volume"),

                "turnover": ticker.get("turnover"),

                "open_interest": ticker.get(
                    "open_interest"
                ),

                "high": ticker.get("high"),

                "low": ticker.get("low")

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

            "total_products": len(all_products),

            "count": len(market_data),

            "ticker_count": ticker_count,

            "contract_types": list(
                CONTRACT_TYPES
            ),

            "markets": market_data

        })

    except requests.RequestException:

        app.logger.exception(
            "Delta API connection failed"
        )

        return jsonify({
            "ok": False,
            "error": "Delta API connection failed"
        }), 502

    except (ValueError, TypeError, KeyError):

        app.logger.exception(
            "Market processing failed"
        )

        return jsonify({
            "ok": False,
            "error": "Market data processing failed"
        }), 502


@app.route("/api/markets/debug")
def markets_debug():

    try:

        products = get_all_products()

        type_counts = {}
        state_counts = {}

        for product in products:

            if not isinstance(product, dict):
                continue

            contract_type = get_contract_type(
                product
            ) or "missing"

            state = str(
                product.get("state", "missing")
            ).lower()

            type_counts[contract_type] = (
                type_counts.get(contract_type, 0) + 1
            )

            state_counts[state] = (
                state_counts.get(state, 0) + 1
            )

        active = get_active_futures(products)

        tickers = get_all_tickers()

        return jsonify({

            "ok": True,

            "updated_at": datetime.now().astimezone().isoformat(),

            "total_products": len(products),

            "active_futures_and_perpetuals": len(active),

            "total_tickers": len(tickers),

            "contract_type_counts": type_counts,

            "state_counts": state_counts,

            "sample_products": products[:5],

            "sample_tickers": tickers[:5]

        })

    except requests.RequestException:

        app.logger.exception(
            "Debug API connection failed"
        )

        return jsonify({
            "ok": False,
            "error": "Delta API connection failed"
        }), 502

    except (ValueError, TypeError, KeyError):

        app.logger.exception(
            "Debug processing failed"
        )

        return jsonify({
            "ok": False,
            "error": "Debug processing failed"
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

    if not re.fullmatch(
        r"[A-Z0-9-]{2,40}",
        symbol
    ):

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
            request.args.get(
                "end",
                time.time()
            )
        )

        start = int(
            request.args.get(
                "start",
                end - 7 * 86400
            )
        )

        if (
            start >= end
            or end - start > 2 * 365 * 86400
        ):

            return jsonify({
                "ok": False,
                "error": "Invalid time range"
            }), 400

        data = delta_get(
            "/v2/history/candles",
            params={
                "symbol": symbol,
                "resolution": resolution,
                "start": start,
                "end": end
            }
        )

        candles = data.get("result", [])

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
        port=int(
            os.environ.get("PORT", "5000")
        ),
        debug=False
    )
