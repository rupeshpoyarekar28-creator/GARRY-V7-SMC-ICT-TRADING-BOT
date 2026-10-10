def _handle_ticker_message(self, payload: dict) -> None:
    """Parse both standard and compact Delta Exchange ticker messages."""
    if not isinstance(payload, dict):
        return

    data = payload.get("data", payload.get("result", payload))

    # Delta compact ticker format can send data as a list.
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        nested = data.get("d")
        if isinstance(nested, list):
            items = nested
        elif isinstance(nested, dict):
            items = [nested]
        else:
            items = [data]
    else:
        items = [payload]

    for item in items:
        if not isinstance(item, dict):
            continue

        symbol = self._extract_symbol(item)
        if not symbol:
            symbol = self._extract_symbol(payload)
        if symbol not in self.symbols:
            continue

        nested = item.get("d")
        if isinstance(nested, dict):
            item = {**item, **nested}

        price = self._first_positive(
            item,
            (
                "close", "mark_price", "last_traded_price",
                "last_price", "price", "sp", "m", "p",
            ),
        )

        # Compact ticker may publish its close inside OHLC data.
        if price <= 0:
            ohlc = item.get("ohlc")
            if isinstance(ohlc, dict):
                price = self._first_positive(
                    ohlc, ("close", "c", "4")
                )
            elif isinstance(ohlc, (list, tuple)) and len(ohlc) >= 4:
                price = self._to_float(ohlc[3])

        quotes = item.get("quotes")
        if not isinstance(quotes, dict):
            quotes = {}

        bid = self._first_positive(
            item, ("best_bid", "bid", "bp", "b")
        )
        ask = self._first_positive(
            item, ("best_ask", "ask", "ap", "a")
        )
        volume = self._first_positive(
            item, ("volume", "v", "volume_24h")
        )

        bid = bid or self._first_positive(
            quotes, ("best_bid", "bid", "buy")
        )
        ask = ask or self._first_positive(
            quotes, ("best_ask", "ask", "sell")
        )

        # Compact quote arrays may contain bid/ask values.
        if isinstance(quotes, (list, tuple)):
            if len(quotes) >= 2:
                bid = bid or self._to_float(quotes[0])
                ask = ask or self._to_float(quotes[1])

        if price <= 0:
            continue

        self._update_market_snapshot(
            symbol=symbol,
            price=price,
            bid=bid,
            ask=ask,
            volume=volume,
            source="WEBSOCKET",
        )
