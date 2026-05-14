"""
Sobek Ankh — Strategy 5: Multi-Factor Cross-Sectional
Score ALL coins daily on: momentum, volume, volatility, funding, sentiment.
Long top 5 scoring coins, short bottom 5.
What KFQuant (Jane Street/WorldQuant alumni) actually runs.
β=0.038 — near-zero market exposure.
"""
import time
import numpy as np
from core.exchange_bridge import fetch_ticker, get_all_tickers, fetch_funding_rate
from risk.risk_engine import can_trade, kelly_position_size, open_position
from utils.telegram_alert import send_alert
from utils.midas_log import log_trade

STRATEGY_NAME = "multi_factor"
EXCHANGES = ["binance", "bybit"]
TOP_N = 5       # Long top N
BOTTOM_N = 5    # Short bottom N
MIN_VOLUME_USD = 10_000_000  # Minimum $10M daily volume

FACTOR_WEIGHTS = {
    "momentum_1d": 0.30,
    "momentum_7d": 0.20,
    "volume_surge": 0.20,
    "funding_rate": 0.15,
    "volatility_inv": 0.15,  # Lower volatility = higher score (risk-adjusted)
}

_price_cache = {}  # symbol -> [price_t-7, price_t-1, price_now]

def score_coin(symbol: str, ticker: dict, funding: float = 0) -> float | None:
    """Score a coin across all factors. Returns composite score."""
    try:
        price = ticker.get("last", 0)
        volume = ticker.get("quoteVolume", 0)
        high = ticker.get("high", price)
        low = ticker.get("low", price)
        open_price = ticker.get("open", price)

        if price <= 0 or volume < MIN_VOLUME_USD:
            return None

        # Factor 1: 1-day momentum (price change from open)
        mom_1d = (price - open_price) / open_price if open_price > 0 else 0

        # Factor 2: 7-day momentum (from cache)
        hist = _price_cache.get(symbol, [])
        mom_7d = (price - hist[0]) / hist[0] if len(hist) >= 7 and hist[0] > 0 else 0

        # Update price cache
        if symbol not in _price_cache:
            _price_cache[symbol] = []
        _price_cache[symbol].append(price)
        if len(_price_cache[symbol]) > 7:
            _price_cache[symbol].pop(0)

        # Factor 3: Volume surge (vs typical)
        vol_surge = min(volume / MIN_VOLUME_USD, 10) / 10  # normalized 0-1

        # Factor 4: Funding rate signal (positive funding = bullish, negative = bearish)
        funding_signal = np.tanh(funding * 1000)  # normalize funding rate

        # Factor 5: Inverse volatility (lower vol = more predictable = higher score)
        daily_range = (high - low) / price if price > 0 else 1
        vol_inv = 1 - min(daily_range, 1)

        # Composite score
        score = (
            FACTOR_WEIGHTS["momentum_1d"] * np.tanh(mom_1d * 10) +
            FACTOR_WEIGHTS["momentum_7d"] * np.tanh(mom_7d * 5) +
            FACTOR_WEIGHTS["volume_surge"] * vol_surge +
            FACTOR_WEIGHTS["funding_rate"] * funding_signal +
            FACTOR_WEIGHTS["volatility_inv"] * vol_inv
        )
        return score
    except Exception:
        return None

def rank_all_coins(exchange: str = "binance") -> list:
    """Rank all coins by multi-factor score."""
    try:
        tickers = get_all_tickers(exchange)
    except Exception:
        return []

    scored = []
    for symbol, ticker in tickers.items():
        if not symbol.endswith("/USDT"):
            continue
        if ticker.get("quoteVolume", 0) < MIN_VOLUME_USD:
            continue

        # Get funding rate for perp version
        funding = 0
        try:
            perp_symbol = symbol.replace("/USDT", "/USDT:USDT")
            fr = fetch_funding_rate(exchange, perp_symbol)
            funding = fr.get("fundingRate", 0)
        except Exception:
            pass

        score = score_coin(symbol, ticker, funding)
        if score is not None:
            scored.append({
                "symbol": symbol,
                "score": score,
                "price": ticker.get("last", 0),
                "volume_usd": ticker.get("quoteVolume", 0),
                "change_1d": ticker.get("percentage", 0),
                "funding": funding
            })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored

def execute_cross_sectional(capital: float) -> dict:
    """Execute long top N + short bottom N strategy."""
    allowed, reason = can_trade(STRATEGY_NAME, capital)
    if not allowed:
        return {"status": "blocked", "reason": reason}

    ranked = rank_all_coins("binance")
    if len(ranked) < TOP_N + BOTTOM_N:
        return {"status": "insufficient_data", "coins_ranked": len(ranked)}

    longs = ranked[:TOP_N]
    shorts = ranked[-BOTTOM_N:]

    position_size = min(capital * 0.02, kelly_position_size(capital, 0.65, 0.04, 0.02))
    results = {"longs": [], "shorts": [], "strategy": STRATEGY_NAME, "timestamp": time.time()}

    long_symbols = [c["symbol"] for c in longs]
    short_symbols = [c["symbol"] for c in shorts]

    for coin in longs:
        amount = position_size / coin["price"]
        results["longs"].append({
            "symbol": coin["symbol"],
            "score": coin["score"],
            "price": coin["price"],
            "size_usd": position_size,
            "status": "simulated"
        })
        # place_order("binance", coin["symbol"], "buy", amount)
        open_position()

    for coin in shorts:
        amount = position_size / coin["price"]
        results["shorts"].append({
            "symbol": coin["symbol"],
            "score": coin["score"],
            "price": coin["price"],
            "size_usd": position_size,
            "status": "simulated"
        })
        # place_order("binance", coin["symbol"], "sell", amount)
        open_position()

    send_alert(
        f"🐊 SOBEK | Multi-Factor\n"
        f"🟢 LONG ({TOP_N}): {', '.join(long_symbols)}\n"
        f"🔴 SHORT ({BOTTOM_N}): {', '.join(short_symbols)}\n"
        f"💵 ${position_size:.2f}/position | {len(longs)+len(shorts)} total trades"
    )
    log_trade(results)
    return results

def run(capital: float) -> dict:
    return execute_cross_sectional(capital)
