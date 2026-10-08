"""
GARRY V7 SMC ICT TRADING BOT

Delta Exchange India - Public Market/Product Data Client.

STEP 3:
- Exact 7 approved trading pairs
- Live perpetual-futures validation
- Dynamic contract specifications
- No API key
- No authentication
- No order placement
"""

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Optional


BASE_URL = "https://api.india.delta.exchange"

# ------------------------------------------------------------
# LOCKED USER-APPROVED PAIRS
# Do not add/remove symbols without explicit user approval.
# ------------------------------------------------------------

APPROVED_SYMBOLS = (
    "BTCUSD",
    "XAUTUSD",
    "ETHUSD",
    "PAXGUSD",
    "SOLUSD",
    "XRPUSD",
    "UNIUSD",
)


@dataclass
class DeltaProduct:
    product_id: int
    symbol: str
    description: str

    contract_type: str
    state: str
    trading_status: str

    contract_value: float
    contract_unit_currency: str
    tick_size: float

    position_size_limit: float
    default_leverage: float

    maker_commission_rate: float
    taker_commission_rate: float

    funding_method: str
    annualized_funding: float

    is_quanto: bool


class DeltaAPIError(Exception):
    """Raised when Delta public API communication fails."""


class DeltaPublicClient:
    """
    Dependency-free Delta Exchange India public REST client.

    This client:
    - reads public market/product data
    - validates approved contracts
    - never authenticates
    - never places orders
    """

    def __init__(
        self,
        base_url: str = BASE_URL,
        timeout: int = 10,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    # ============================================================
    # HTTP
    # ============================================================

    def _get(
        self,
        path: str,
        params: Optional[dict[str, Any]] = None,
    ) -> Any:
        if params:
            query = urllib.parse.urlencode(params)
            url = f"{self.base_url}{path}?{query}"
        else:
            url = f"{self.base_url}{path}"

        request = urllib.request.Request(
            url=url,
            method="GET",
            headers={
                "Accept": "application/json",
                "User-Agent": "GARRY-V7/1.0",
            },
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=self.timeout,
            ) as response:

                raw = response.read().decode("utf-8")

        except urllib.error.HTTPError as exc:
            raise DeltaAPIError(
                f"HTTP ERROR {exc.code}"
            ) from exc

        except urllib.error.URLError as exc:
            raise DeltaAPIError(
                f"NETWORK ERROR: {exc.reason}"
            ) from exc

        except TimeoutError as exc:
            raise DeltaAPIError(
                "DELTA API TIMEOUT"
            ) from exc

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise DeltaAPIError(
                "INVALID JSON RESPONSE FROM DELTA"
            ) from exc

        if isinstance(payload, dict):
            if payload.get("success") is False:
                raise DeltaAPIError(
                    str(
                        payload.get(
                            "error",
                            "DELTA API REQUEST FAILED",
                        )
                    )
                )

        return payload

    # ============================================================
    # PRODUCTS
    # ============================================================

    def get_products(
        self,
        page_size: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Return live perpetual-futures products.
        """

        payload = self._get(
            "/v2/products",
            params={
                "contract_types": "perpetual_futures",
                "states": "live",
                "page_size": page_size,
            },
        )

        result = payload.get("result", [])

        if not isinstance(result, list):
            raise DeltaAPIError(
                "INVALID PRODUCTS RESPONSE"
            )

        return result

    def get_product(
        self,
        symbol: str,
    ) -> Optional[DeltaProduct]:
        """
        Fetch and validate one product by symbol.

        The product must be:
        - approved
        - perpetual_futures
        - live
        - operational
        """

        symbol = str(symbol).upper().strip()

        if symbol not in APPROVED_SYMBOLS:
            return None

        try:
            payload = self._get(
                f"/v2/products/{urllib.parse.quote(symbol)}"
            )
        except DeltaAPIError:
            return None

        raw = payload.get("result")

        if not isinstance(raw, dict):
            return None

        if raw.get("symbol") != symbol:
            return None

        if raw.get("contract_type") != "perpetual_futures":
            return None

        if raw.get("state") != "live":
            return None

        if raw.get("trading_status") != "operational":
            return None

        return self._parse_product(raw)

    def get_approved_products(
        self,
    ) -> dict[str, DeltaProduct]:
        """
        Validate all 7 locked symbols.

        Only valid/live/operational perpetual contracts
        are returned.
        """

        products = self.get_products()

        product_map: dict[str, DeltaProduct] = {}

        for raw in products:

            if not isinstance(raw, dict):
                continue

            symbol = str(
                raw.get("symbol", "")
            ).upper()

            if symbol not in APPROVED_SYMBOLS:
                continue

            if raw.get("contract_type") != "perpetual_futures":
                continue

            if raw.get("state") != "live":
                continue

            if raw.get("trading_status") != "operational":
                continue

            product = self._parse_product(raw)

            if product is not None:
                product_map[symbol] = product

        return product_map

    # ============================================================
    # PRODUCT PARSER
    # ============================================================

    def _parse_product(
        self,
        raw: dict[str, Any],
    ) -> Optional[DeltaProduct]:

        try:
            return DeltaProduct(
                product_id=int(raw["id"]),
                symbol=str(raw["symbol"]),
                description=str(
                    raw.get("description", "")
                ),
                contract_type=str(
                    raw["contract_type"]
                ),
                state=str(
                    raw["state"]
                ),
                trading_status=str(
                    raw["trading_status"]
                ),
                contract_value=float(
                    raw["contract_value"]
                ),
                contract_unit_currency=str(
                    raw.get(
                        "contract_unit_currency",
                        "",
                    )
                ),
                tick_size=float(
                    raw["tick_size"]
                ),
                position_size_limit=float(
                    raw.get(
                        "position_size_limit",
                        0,
                    )
                ),
                default_leverage=float(
                    raw.get(
                        "default_leverage",
                        0,
                    )
                ),
                maker_commission_rate=float(
                    raw.get(
                        "maker_commission_rate",
                        0,
                    )
                ),
                taker_commission_rate=float(
                    raw.get(
                        "taker_commission_rate",
                        0,
                    )
                ),
                funding_method=str(
                    raw.get(
                        "funding_method",
                        "",
                    )
                ),
                annualized_funding=float(
                    raw.get(
                        "annualized_funding",
                        0,
                    )
                ),
                is_quanto=bool(
                    raw.get(
                        "is_quanto",
                        False,
                    )
                ),
            )

        except (
            KeyError,
            TypeError,
            ValueError,
        ):
            return None

    # ============================================================
    # TICKER
    # ============================================================

    def get_ticker(
        self,
        symbol: str,
    ) -> dict[str, Any]:

        symbol = str(symbol).upper().strip()

        if symbol not in APPROVED_SYMBOLS:
            raise DeltaAPIError(
                "SYMBOL NOT APPROVED"
            )

        return self._get(
            f"/v2/tickers/{urllib.parse.quote(symbol)}"
        )

    # ============================================================
    # CANDLES
    # ============================================================

    def get_candles(
        self,
        symbol: str,
        resolution: str = "5m",
        start: Optional[int] = None,
        end: Optional[int] = None,
    ) -> dict[str, Any]:

        symbol = str(symbol).upper().strip()

        if symbol not in APPROVED_SYMBOLS:
            raise DeltaAPIError(
                "SYMBOL NOT APPROVED"
            )

        params: dict[str, Any] = {
            "resolution": resolution,
        }

        if start is not None:
            params["start"] = start

        if end is not None:
            params["end"] = end

        return self._get(
            "/v2/history/candles",
            params=params,
        )

    # ============================================================
    # CONNECTION TEST
    # ============================================================

    def test_public_connection(self) -> bool:
        """
        Confirm Delta public API is reachable.
        """

        try:
            self.get_products(page_size=10)
            return True

        except DeltaAPIError:
            return False


# ================================================================
# BACKWARD-COMPATIBILITY HELPERS
# ================================================================

_default_client = DeltaPublicClient()


def get_products(
    page_size: int = 100,
) -> list[dict[str, Any]]:
    return _default_client.get_products(
        page_size=page_size
    )


def find_btc_perpetual() -> Optional[DeltaProduct]:
    return _default_client.get_product("BTCUSD")


def get_ticker(
    symbol: str,
) -> dict[str, Any]:
    return _default_client.get_ticker(symbol)


def get_recent_candles(
    symbol: str,
    resolution: str = "5m",
    start: Optional[int] = None,
    end: Optional[int] = None,
) -> dict[str, Any]:
    return _default_client.get_candles(
        symbol=symbol,
        resolution=resolution,
        start=start,
        end=end,
    )


def test_public_connection() -> bool:
    return _default_client.test_public_connection()
