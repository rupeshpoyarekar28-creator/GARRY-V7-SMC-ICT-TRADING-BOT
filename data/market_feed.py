import os
import ssl
import requests
import certifi
import logging

# --- ANDROID SSL FIX - HA KHUP MAHATVACHA AHE ---
os.environ['SSL_CERT_FILE'] = certifi.where()
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
try:
    ssl._create_default_https_context = lambda: ssl.create_default_context(cafile=certifi.where())
except:
    pass

logger = logging.getLogger(__name__)

class DeltaMarketFeed:
    BASE_URL = "https://api.india.delta.exchange"

    def __init__(self):
        self.session = requests.Session()
        self.session.verify = certifi.where()

    def _make_request(self, endpoint):
        url = f"{self.BASE_URL}{endpoint}"
        try:
            # Pehla try certifi ne
            resp = self.session.get(url, timeout=15, verify=certifi.where())
            resp.raise_for_status()
            return resp.json()
        except Exception as e1:
            logger.warning(f"SSL certifi fail, trying without verify: {e1}")
            try:
                # Dusra try - verify band karun (Android sathi)
                resp = self.session.get(url, timeout=15, verify=False)
                resp.raise_for_status()
                return resp.json()
            except Exception as e2:
                raise Exception(f"NETWORK ERROR [SSL: {str(e2)}]")

    def get_ticker(self, symbol="BTCUSD"):
        # symbol la Delta format madhe convert
        try:
            data = self._make_request(f"/v2/tickers/{symbol}")
            return data
        except Exception as e:
            # Fallback - sagle tickers madhun shodh
            all_data = self._make_request("/v2/tickers")
            if 'result' in all_data:
                for t in all_data['result']:
                    if t.get('symbol') == symbol or symbol in t.get('symbol',''):
                        return t
            raise e

    def get_all_tickers(self):
        return self._make_request("/v2/tickers")

# Singleton instance
market_feed = DeltaMarketFeed()
