"""
Sobek Ankh — Strategy 2: Cross-Exchange Arbitrage (LIVE DATA)
Fetches REAL prices from Binance, Bybit, OKX, Kraken — all public APIs.
No API key needed. Pure spread capture. Zero directional risk.
Buy low on Exchange A, sell high on Exchange B.
"""
import time
import requests as req
from concurrent.futures import ThreadPoolExecutor, as_completed
from risk.risk_engine import can_trade, kelly_position_size, open_position
from utils.telegram_alert import send_alert
from utils.midas_log import log_trade

STRATEGY_NAME = "cross_exchange_arb"
MIN_SPREAD_PCT = 0.002   # 0.2% minimum — covers fees and still profits
FEE_ESTIMATE   = 0.0008  # 0.08% per leg (taker fee avg)
MAX_POSITIONS  = 2

SCAN_PAIRS = {
    "BTC/USDT": {
        "binance": "BTCUSDT",
        "bybit":   "BTCUSDT",
        "okx":     "BTC-USDT",
        "kraken":  "XBTUSD",
    },
    "ETH/USDT": {
        "binance": "ETHUSDT",
        "bybit":   "ETHUSDT",
        "okx":     "ETH-USDT",
        "kraken":  "ETHUSD",
    },
    "SOL/USDT": {
        "binance": "SOLUSDT",
        "bybit":   "SOLUSDT",
        "okx":     "SOL-USDT",
        "kraken":  "SOLUSD",
    },
    "BNB/USDT": {
        "binance": "BNBUSDT",
        "bybit":   "BNBUSDT",
        "okx":     "BNB-USDT",
    },
    "AVAX/USDT": {
        "binance": "AVAXUSDT",
        "bybit":   "AVAXUSDT",
        "okx":     "AVAX-USDT",
    },
}

def fetch_binance_price(symbol: str) -> dict:
    try:
        url = f"https://api.binance.com/api/v3/ticker/bookTicker?symbol={symbol}"
        r = req.get(url, timeout=5)
        d = r.json()
        return {"bid": float(d["bidPrice"]), "ask": float(d["askPrice"])}
    except Exception:
        return {}

def fetch_bybit_price(symbol: str) -> dict:
    try:
        url = f"https://api.bybit.com/v5/market/tickers?category=spot&symbol={symbol}"
        r = req.get(url, timeout=5)
        item = r.json()["result"]["list"][0]
        bid = float(item.get("bid1Price", 0))
        ask = float(item.get("ask1Price", 0))
        return {"bid": bid, "ask": ask}
    except Exception:
        return {}

def fetch_okx_price(symbol: str) -> dict:
    try:
        url = f"https://www.okx.com/api/v5/market/ticker?instId={symbol}"
        r = req.get(url, timeout=5)
        d = r.json()["data"][0]
        return {"bid": float(d["bidPx"]), "ask": float(d["askPx"])}
    except Exception:
        return {}

def fetch_kraken_price(symbol: str) -> dict:
    try:
        url = f"https://api.kraken.com/0/public/Ticker?pair={symbol}"
        r = req.get(url, timeout=5)
        result = r.json().get("result", {})
        if not result:
            return {}
        data = list(result.values())[0]
        return {"bid": float(data["b"][0]), "ask": float(data["a"][0])}
    except Exception:
        return {}

FETCHERS = {
    "binance": fetch_binance_price,
    "bybit":   fetch_bybit_price,
    "okx":     fetch_okx_price,
    "kraken":  fetch_kraken_price,
}

def fetch_all_prices(pair: str, exchange_symbols: dict) -> dict:
    """Fetch prices from all exchanges in parallel."""
    prices = {}
    def fetch_one(exchange):
        symbol = exchange_symbols.get(exchange)
        if not symbol:
            return exchange, {}
        fn = FETCHERS.get(exchange)
        if not fn:
            return exchange, {}
        return exchange, fn(symbol)

    with ThreadPoolExecutor(max_workers=4) as ex:
        futures = {ex.submit(fetch_one, exch): exch for exch in exchange_symbols}
        for future in as_completed(futures):
            exch, data = future.result()
            if data and data.get("bid", 0) > 0 and data.get("ask", 0) > 0:
                prices[exch] = data
    return prices

def find_arb_opportunity(pair: str, prices: dict) -> dict:
    """Find best buy/sell combination across exchanges."""
    if len(prices) < 2:
        return {}

    # Best buy = lowest ask
    best_buy_ex  = min(prices, key=lambda x: prices[x]["ask"])
    # Best sell = highest bid
    best_sell_ex = max(prices, key=lambda x: prices[x]["bid"])

    if best_buy_ex == best_sell_ex:
        return {}

    buy_price  = prices[best_buy_ex]["ask"]
    sell_price = prices[best_sell_ex]["bid"]

    if buy_price <= 0 or sell_price <= 0:
        return {}

    spread_pct = (sell_price - buy_price) / buy_price
    net_spread = spread_pct - (FEE_ESTIMATE * 2)

    if net_spread < MIN_SPREAD_PCT:
        return {}

    return {
        "pair":          pair,
        "buy_exchange":  best_buy_ex,
        "sell_exchange": best_sell_ex,
        "buy_price":     buy_price,
        "sell_price":    sell_price,
        "spread_pct":    round(spread_pct, 6),
        "net_spread_pct": round(net_spread, 6),
        "all_prices":    {ex: prices[ex]["bid"] for ex in prices},
    }

def scan_arbitrage_opportunities() -> list:
    """Scan all pairs for real cross-exchange arb opportunities."""
    opportunities = []
    for pair, exchange_symbols in SCAN_PAIRS.items():
        try:
            prices = fetch_all_prices(pair, exchange_symbols)
            opp = find_arb_opportunity(pair, prices)
            if opp:
                opportunities.append(opp)
                print(f"  [cross_arb] 🟢 {pair} | {opp['buy_exchange']} → {opp['sell_exchange']} | spread: {opp['net_spread_pct']:.3%}")
            else:
                # Show tightest spread found even if below threshold
                if len(prices) >= 2:
                    asks = {ex: prices[ex]["ask"] for ex in prices}
                    bids = {ex: prices[ex]["bid"] for ex in prices}
                    low_ask = min(asks.values())
                    high_bid = max(bids.values())
                    raw = (high_bid - low_ask) / low_ask if low_ask > 0 else 0
                    print(f"  [cross_arb] ⚪ {pair} | raw spread: {raw:.4%} (below threshold)")
        except Exception as e:
            print(f"  [cross_arb] Error scanning {pair}: {e}")

    opportunities.sort(key=lambda x: x["net_spread_pct"], reverse=True)
    return opportunities

def execute_arb(opp: dict, capital: float) -> dict:
    """Simulate arb execution with real spread data."""
    allowed, reason = can_trade(STRATEGY_NAME, capital)
    if not allowed:
        return {"strategy": STRATEGY_NAME, "status": "blocked", "pnl": 0}

    position_size = kelly_position_size(
        capital, win_rate=0.85,
        avg_win=opp["net_spread_pct"],
        avg_loss=0.001
    )
    position_size = min(position_size, capital * 0.15)

    pnl = round(position_size * opp["net_spread_pct"], 4)

    result = {
        "strategy":       STRATEGY_NAME,
        "pair":           opp["pair"],
        "buy_exchange":   opp["buy_exchange"],
        "sell_exchange":  opp["sell_exchange"],
        "buy_price":      opp["buy_price"],
        "sell_price":     opp["sell_price"],
        "spread_pct":     opp["spread_pct"],
        "net_spread_pct": opp["net_spread_pct"],
        "position_size_usd": round(position_size, 2),
        "pnl":            pnl,
        "simulate":       True,
        "timestamp":      time.time()
    }

    open_position()
    log_trade(result)
    send_alert(
        f"🐊 SOBEK | Cross-Exchange Arb [LIVE PRICES]\n"
        f"📊 {opp['pair']}\n"
        f"🟢 Buy  @ {opp['buy_exchange']}: ${opp['buy_price']:,.4f}\n"
        f"🔴 Sell @ {opp['sell_exchange']}: ${opp['sell_price']:,.4f}\n"
        f"💰 Net Spread: {opp['net_spread_pct']:.3%}\n"
        f"💵 Size: ${position_size:.2f} | PnL: +{pnl:.4f} USDT"
    )
    return result

def run(capital: float) -> list:
    """Main entry: scan real prices, execute best arb opportunities."""
    opportunities = scan_arbitrage_opportunities()
    if not opportunities:
        print("  [cross_arb] No arb opportunities above threshold right now")
        return []

    print(f"  [cross_arb] {len(opportunities)} live opportunities found")
    results = []
    for opp in opportunities[:MAX_POSITIONS]:
        r = execute_arb(opp, capital)
        results.append(r)
        time.sleep(0.5)
    return results
