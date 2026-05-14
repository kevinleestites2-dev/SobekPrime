"""
SobekPrime — Exchange Bridge
CCXT unified interface to 100+ exchanges
"""
import ccxt
import os
from dotenv import load_dotenv

load_dotenv()

EXCHANGE_CONFIGS = {
    "binance": {
        "apiKey": os.getenv("BINANCE_API_KEY", ""),
        "secret": os.getenv("BINANCE_SECRET", ""),
        "options": {"defaultType": "future"},
    },
    "bybit": {
        "apiKey": os.getenv("BYBIT_API_KEY", ""),
        "secret": os.getenv("BYBIT_SECRET", ""),
        "options": {"defaultType": "linear"},
    },
    "okx": {
        "apiKey": os.getenv("OKX_API_KEY", ""),
        "secret": os.getenv("OKX_SECRET", ""),
        "password": os.getenv("OKX_PASSPHRASE", ""),
    },
    "kraken": {
        "apiKey": os.getenv("KRAKEN_API_KEY", ""),
        "secret": os.getenv("KRAKEN_SECRET", ""),
    },
}

_exchanges = {}

def get_exchange(name: str, sandbox: bool = False):
    if name not in _exchanges:
        config = EXCHANGE_CONFIGS.get(name, {})
        ex = getattr(ccxt, name)(config)
        if sandbox and ex.has.get("sandbox"):
            ex.set_sandbox_mode(True)
        _exchanges[name] = ex
    return _exchanges[name]

def fetch_ticker(exchange_name: str, symbol: str) -> dict:
    ex = get_exchange(exchange_name)
    return ex.fetch_ticker(symbol)

def fetch_orderbook(exchange_name: str, symbol: str, limit: int = 20) -> dict:
    ex = get_exchange(exchange_name)
    return ex.fetch_order_book(symbol, limit)

def fetch_funding_rate(exchange_name: str, symbol: str) -> dict:
    ex = get_exchange(exchange_name)
    if ex.has.get("fetchFundingRate"):
        return ex.fetch_funding_rate(symbol)
    return {}

def fetch_balance(exchange_name: str) -> dict:
    ex = get_exchange(exchange_name)
    return ex.fetch_balance()

def place_order(exchange_name: str, symbol: str, side: str, amount: float,
                order_type: str = "market", price: float = None) -> dict:
    ex = get_exchange(exchange_name)
    if order_type == "market":
        return ex.create_market_order(symbol, side, amount)
    elif order_type == "limit" and price:
        return ex.create_limit_order(symbol, side, amount, price)

def get_all_tickers(exchange_name: str) -> dict:
    ex = get_exchange(exchange_name)
    if ex.has.get("fetchTickers"):
        return ex.fetch_tickers()
    return {}
