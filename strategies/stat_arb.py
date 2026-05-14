"""
Sobek Ankh — Strategy 4: Statistical Arbitrage (Pairs Trading)
Find correlated assets. When they diverge, bet on convergence.
What $4B hedge funds use as their PRIMARY strategy.
Market neutral. Consistent Sharpe ratio.
"""
import time
import numpy as np
from core.exchange_bridge import fetch_ticker, place_order
from risk.risk_engine import can_trade, kelly_position_size, open_position, record_trade_result
from utils.telegram_alert import send_alert
from utils.midas_log import log_trade

STRATEGY_NAME = "stat_arb"

# Highly correlated pairs for statistical arbitrage
CORRELATED_PAIRS = [
    ("BTC/USDT", "ETH/USDT", "binance"),    # BTC/ETH historically 0.90+ correlation
    ("SOL/USDT", "AVAX/USDT", "bybit"),     # Layer 1 alts, high correlation
    ("BNB/USDT", "OKB/USDT", "okx"),        # Exchange tokens
    ("MATIC/USDT", "ARB/USDT", "binance"),  # L2 tokens
]

Z_SCORE_ENTRY = 2.0    # Enter when z-score exceeds 2 standard deviations
Z_SCORE_EXIT = 0.5     # Exit when z-score returns toward 0
LOOKBACK = 20          # Rolling window for z-score calculation

# Price history buffer (in production use Redis or DB)
_price_history = {}

def update_price_history(pair: str, price: float):
    if pair not in _price_history:
        _price_history[pair] = []
    _price_history[pair].append(price)
    if len(_price_history[pair]) > 100:
        _price_history[pair].pop(0)

def calculate_z_score(pair_a: str, pair_b: str) -> float | None:
    """Calculate z-score of the spread between two pairs."""
    hist_a = _price_history.get(pair_a, [])
    hist_b = _price_history.get(pair_b, [])

    min_len = min(len(hist_a), len(hist_b))
    if min_len < LOOKBACK:
        return None

    a = np.array(hist_a[-LOOKBACK:])
    b = np.array(hist_b[-LOOKBACK:])

    # Ratio spread
    spread = np.log(a) - np.log(b)
    mean = np.mean(spread)
    std = np.std(spread)

    if std == 0:
        return None

    current_spread = np.log(hist_a[-1]) - np.log(hist_b[-1])
    z_score = (current_spread - mean) / std
    return z_score

def scan_pairs(capital: float) -> list:
    """Scan all correlated pairs for divergence opportunities."""
    opportunities = []

    for pair_a, pair_b, exchange in CORRELATED_PAIRS:
        try:
            ticker_a = fetch_ticker(exchange, pair_a)
            ticker_b = fetch_ticker(exchange, pair_b)

            price_a = ticker_a["last"]
            price_b = ticker_b["last"]

            update_price_history(pair_a, price_a)
            update_price_history(pair_b, price_b)

            z_score = calculate_z_score(pair_a, pair_b)
            if z_score is None:
                continue

            if abs(z_score) >= Z_SCORE_ENTRY:
                # A is overpriced relative to B → short A, long B (or vice versa)
                if z_score > 0:
                    direction = {"long": pair_b, "short": pair_a}
                else:
                    direction = {"long": pair_a, "short": pair_b}

                opportunities.append({
                    "pair_a": pair_a,
                    "pair_b": pair_b,
                    "exchange": exchange,
                    "z_score": z_score,
                    "direction": direction,
                    "price_a": price_a,
                    "price_b": price_b,
                    "convergence_target": Z_SCORE_EXIT
                })
        except Exception:
            continue

    opportunities.sort(key=lambda x: abs(x["z_score"]), reverse=True)
    return opportunities

def execute_pairs_trade(opportunity: dict, capital: float) -> dict:
    """Execute pairs trade: long underperformer, short overperformer."""
    allowed, reason = can_trade(STRATEGY_NAME, capital)
    if not allowed:
        return {"status": "blocked", "reason": reason}

    position_size = kelly_position_size(capital, win_rate=0.70, avg_win=0.03, avg_loss=0.015)
    position_size = min(position_size, capital * 0.08)  # 8% max per pairs trade
    half_size = position_size / 2

    long_pair = opportunity["direction"]["long"]
    short_pair = opportunity["direction"]["short"]
    long_price = opportunity["price_a"] if long_pair == opportunity["pair_a"] else opportunity["price_b"]
    short_price = opportunity["price_b"] if short_pair == opportunity["pair_b"] else opportunity["price_a"]

    long_amount = half_size / long_price
    short_amount = half_size / short_price

    result = {
        "strategy": STRATEGY_NAME,
        "exchange": opportunity["exchange"],
        "long_pair": long_pair,
        "short_pair": short_pair,
        "z_score": opportunity["z_score"],
        "long_price": long_price,
        "short_price": short_price,
        "long_amount": long_amount,
        "short_amount": short_amount,
        "position_size_usd": position_size,
        "status": "simulated",
        "timestamp": time.time()
    }

    # Live execution:
    # place_order(opportunity["exchange"], long_pair, "buy", long_amount)
    # place_order(opportunity["exchange"], short_pair, "sell", short_amount)

    open_position()
    send_alert(
        f"🐊 SOBEK | Stat Arb\n"
        f"🟢 LONG {long_pair} @ ${long_price:.4f}\n"
        f"🔴 SHORT {short_pair} @ ${short_price:.4f}\n"
        f"📊 Z-Score: {opportunity['z_score']:.2f} (entry >{Z_SCORE_ENTRY})\n"
        f"💵 Size: ${position_size:.2f}"
    )
    log_trade(result)
    return result

def run(capital: float) -> list:
    opportunities = scan_pairs(capital)
    results = []
    for opp in opportunities[:1]:  # 1 pairs trade at a time
        r = execute_pairs_trade(opp, capital)
        results.append(r)
    return results
