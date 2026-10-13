import os
import ssl
import requests
import certifi

# Android SSL Fix
os.environ['SSL_CERT_FILE'] = certifi.where()
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()

class DeltaMarketFeed:
    BASE_URL = "https://api.india.delta.exchange"

    def __init__(self):
        self.session = requests.Session()

    def _make_request(self, endpoint):
        url = self.BASE_URL + endpoint
        try:
            resp = self.session.get(url, timeout=15, verify=certifi.where())
            resp.raise_for_status()
            return resp.json()
        except:
            # Android sathi verify band
            resp = self.session.get(url, timeout=15, verify=False)
            resp.raise_for_status()
            return resp.json()

    def get_ticker(self, symbol="BTCUSD"):
        try:
            data = self._make_request("/v2/tickers/" + symbol)
            return data
        except:
            all_data = self._make_request("/v2/tickers")
            if 'result' in all_data:
                for t in all_data['result']:
                    if symbol in t.get('symbol',''):
                        return t
            return all_data

    def get_all_tickers(self):
        return self._make_request("/v2/tickers")

market_feed = DeltaMarketFeed()
