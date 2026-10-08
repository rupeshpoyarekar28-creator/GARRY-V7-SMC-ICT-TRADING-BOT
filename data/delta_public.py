"""
GARRY V7 SMC ICT TRADING BOT

Delta Exchange India - Public Market Data Client

IMPORTANT:
- Public market data only.
- No API key.
- No authentication.
- No order placement.
- No trading execution.
"""

from __future__ import annotations

import json
import time
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


class DeltaPublicAPIError(Exception):
    """Raised when Delta public API request fails."""


class DeltaPublicClient:
    """
    Small dependency-free client for Delta Exchange India public APIs.

    Uses Python standard library only so the Android build chain
    does not need additional third-party packages.
    """

    BASE_URL = "https://api.india.delta.exchange"

    def __init__(self, timeout: int = 10):
        self.timeout = timeout

    # ---------------------------------------------------------
    # Internal HTTP GET
    # ---------------------------------------------------------

    def _get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        url = self.BASE_URL + path

        if params:
            clean_params = {
                key: value
                for key, value in params.items()
                if value is not None
            }

            if clean_params:
                url += "?" + urlencode(clean_params)

        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "GARRY-V7-SMC-ICT-TRADING-BOT/1.0",
            },
            method="GET",
        )

        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")

        except HTTPError as exc:
            raise DeltaPublicAPIError(
                f"HTTP error {exc.code}: {exc.reason}"
            ) from exc

        except URLError as exc:
            raise DeltaPublicAPIError(
                f"Network error: {exc.reason}"
            ) from exc

        except TimeoutError as exc:
            raise DeltaPublicAPIError(
                "Network timeout"
            ) from exc

        except Exception as exc:
            raise DeltaPublicAPIError(
                f"Unexpected network error: {exc}"
            ) from exc

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise DeltaPublicAPIError(
                "Delta returned invalid JSON"
            ) from exc

        if not isinstance(data, dict):
            raise DeltaPublicAPIError(
                "Delta returned unexpected response format"
            )

        if data.get("success") is False:
            raise DeltaPublicAPIError(
                str(data.get("error", "Delta API request failed"))
            )

        return data.get("result")

    # ---------------------------------------------------------
    # Product List
    # ---------------------------------------------------------

    def get_products(self, page_size: int = 100) -> list[dict[str, Any]]:
        """
        Get active/current product information.

        This is used later to discover the correct Delta symbol
        instead of blindly assuming BTCUSDT/BTCUSD.
        """

        result = self._get(
            "/v2/products",
            {
                "page_size": page_size,
            },
        )

        if not isinstance(result, list):
            raise DeltaPublicAPIError(
                "Unexpected products response"
            )

        return result

    # ---------------------------------------------------------
    # Find BTC perpetual product
    # ---------------------------------------------------------

    def find_btc_perpetual(self) -> dict[str, Any] | None:
        """
        Find an active BTC perpetual product.

        We intentionally do NOT hard-code BTCUSDT or BTCUSD.
        Delta's actual product metadata decides the symbol.
        """

        products = self.get_products()

        candidates = []

        for product in products:
            if not isinstance(product, dict):
                continue

            symbol = str(product.get("symbol", ""))
            contract_type = str(
                product.get("contract_type", "")
            ).lower()

            state = str(
                product.get("state", "")
            ).lower()

            underlying = str(
                product.get("underlying_asset_symbol", "")
            ).upper()

            symbol_upper = symbol.upper()

            is_btc = (
                "BTC" in symbol_upper
                or underlying == "BTC"
            )

            is_perpetual = (
                "perpetual" in contract_type
                or contract_type == "perpetual_futures"
            )

            is_active = (
                not state
                or state in {
                    "live",
                    "online",
                    "active",
                }
            )

            if is_btc and is_perpetual and is_active:
                candidates.append(product)

        if not candidates:
            return None

        # Prefer a product whose symbol contains BTCUSD/BTCUSDT.
        candidates.sort(
            key=lambda item: (
                0
                if "BTCUSD" in str(
                    item.get("symbol", "")
                ).upper()
                else 1
            )
        )

        return candidates[0]

    # ---------------------------------------------------------
    # Ticker
    # ---------------------------------------------------------

    def get_ticker(
        self,
        symbol: str,
    ) -> dict[str, Any]:
        """
        Get live ticker for one product.
        """

        result = self._get(
            f"/v2/tickers/{symbol}"
        )

        if not isinstance(result, dict):
            raise DeltaPublicAPIError(
                "Unexpected ticker response"
            )

        return result

    # ---------------------------------------------------------
    # Historical candles
    # ---------------------------------------------------------

    def get_candles(
        self,
        symbol: str,
        resolution: str,
        start: int,
        end: int,
    ) -> list[dict[str, Any]]:
        """
        Get historical OHLCV candles.

        Example resolutions:
        5m
        15m
        1h

        Delta allows up to 2000 candles per response.
        """

        allowed_resolutions = {
            "1m",
            "3m",
            "5m",
            "15m",
            "30m",
            "1h",
            "2h",
            "4h",
            "6h",
            "1d",
            "1w",
        }

        if resolution not in allowed_resolutions:
            raise ValueError(
                f"Unsupported resolution: {resolution}"
            )

        if start >= end:
            raise ValueError(
                "start must be less than end"
            )

        result = self._get(
            "/v2/history/candles",
            {
                "resolution": resolution,
                "symbol": symbol,
                "start": int(start),
                "end": int(end),
            },
        )

        if not isinstance(result, list):
            raise DeltaPublicAPIError(
                "Unexpected candles response"
            )

        return result

    # ---------------------------------------------------------
    # Recent candles helper
    # ---------------------------------------------------------

    def get_recent_candles(
        self,
        symbol: str,
        resolution: str = "5m",
        count: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Fetch recent candles.

        count is capped to Delta's documented 2000 candle
        maximum per response.
        """

        count = max(1, min(int(count), 2000))

        resolution_seconds = {
            "1m": 60,
            "3m": 180,
            "5m": 300,
            "15m": 900,
            "30m": 1800,
            "1h": 3600,
            "2h": 7200,
            "4h": 14400,
            "6h": 21600,
            "1d": 86400,
            "1w": 604800,
        }

        seconds = resolution_seconds.get(resolution)

        if seconds is None:
            raise ValueError(
                f"Unsupported resolution: {resolution}"
            )

        end = int(time.time())
        start = end - (seconds * count)

        return self.get_candles(
            symbol=symbol,
            resolution=resolution,
            start=start,
            end=end,
        )


# -------------------------------------------------------------
# Simple manual test
# -------------------------------------------------------------

def test_public_connection() -> dict[str, Any]:
    """
    Basic diagnostic test.

    This function does NOT place orders.
    """

    client = DeltaPublicClient(timeout=10)

    product = client.find_btc_perpetual()

    if not product:
        return {
            "success": False,
            "error": "BTC perpetual product not found",
        }

    symbol = str(product.get("symbol"))

    ticker = client.get_ticker(symbol)

    return {
        "success": True,
        "symbol": symbol,
        "product": product,
        "ticker": ticker,
    }


if __name__ == "__main__":
    try:
        result = test_public_connection()

        print(
            json.dumps(
                result,
                indent=2,
                default=str,
            )
        )

    except Exception as exc:
        print(
            json.dumps(
                {
                    "success": False,
                    "error": str(exc),
                },
                indent=2,
            )
        )
