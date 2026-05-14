"""
Sobek Ankh — Strategy 1: Funding Rate Arbitrage
Long spot + short perp simultaneously. Collect funding every 8h.
Zero directional risk. 10-164% APY documented.
"""
import time
from core.exchange_bridge import fetch_funding_rate, fetch_ticker, place_order, fetch_balance
from risk.risk_engine import can_trade, kelly_position_size, open_position, record_trade_result, get_stop_loss, get_take_profit
from utils.telegram_alert import send_alert
from utils.midas_log import log_trade

STRATEGY_NAME = "funding_rate_arb"
TARGET_PAIRS = ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT", "BNB/USDT:USDT"]
MIN_FUNDING_RATE = 0.0005  # 0.05% per 8h = ~5.4% APY minimum threshold
EXCHANGES = ["binance", "bybit", "okx"]

def scan_funding_opportunities() -> list:
    """Find pairs with high funding rates across all exchanges."""
    opportunities = []
    for exchange in EXCHANGES:
        for pair in TARGET_PAIRS:
            try:
                fr_data = fetch_funding_rate(exchange, pair)
                rate = fr_data.get("fundingRate", 0)
                if abs(rate) >= MIN_FUNDING_RATE:
                    opportunities.append({
                        "exchange": exchange,
                        "pair": pair,
                        "rate": rate,
                        "direction": "short_perp" if rate > 0 else "long_perp",
                        "apy_estimate": abs(rate) * 3 * 365 * 100  # 3 fundings/day * 365
                    })
            except Exception as e:
                pass
    opportunities.sort(key=lambda x: abs(x["rate"]), reverse=True)
    return opportunities

def execute_funding_arb(opportunity: dict, capital: float) -> dict:
    """Execute funding rate arb: long spot + short perp (or inverse)."""
    allowed, reason = can_trade(STRATEGY_NAME, capital)
    if not allowed:
        return {"status": "blocked", "reason": reason}

    exchange = opportunity["exchange"]
    pair = opportunity["pair"]
    spot_pair = pair.replace(":USDT", "").replace("/USDT", "/USDT")
    rate = opportunity["rate"]

    # Position sizing via Kelly (conservative win_rate=0.75 for funding arb)
    position_size = kelly_position_size(capital, win_rate=0.75, avg_win=abs(rate)*3, avg_loss=abs(rate)*0.5)
    position_size = min(position_size, capital * 0.10)  # max 10% of capital per trade

    ticker = fetch_ticker(exchange, spot_pair)
    price = ticker["last"]
    amount = position_size / price

    result = {
        "strategy": STRATEGY_NAME,
        "exchange": exchange,
        "pair": pair,
        "funding_rate": rate,
        "apy_estimate": opportunity["apy_estimate"],
        "position_size_usd": position_size,
        "amount": amount,
        "entry_price": price,
        "stop_loss": get_stop_loss(price, "buy"),
        "take_profit": get_take_profit(price, "buy", pct=0.06),  # 6% TP for funding arb
        "status": "simulated",  # change to "live" when ready
        "timestamp": time.time()
    }

    # In live mode: place spot long + perp short simultaneously
    # spot_order = place_order(exchange, spot_pair, "buy", amount)
    # perp_order = place_order(exchange, pair, "sell", amount)

    open_position()
    send_alert(f"🐊 SOBEK | Funding Arb\n📈 {pair} @ {exchange}\n💰 Rate: {rate:.4%} ({opportunity['apy_estimate']:.1f}% APY est.)\n💵 Size: ${position_size:.2f}")
    log_trade(result)

    return result

def run(capital: float) -> list:
    """Main entry: scan and execute best funding rate opportunities."""
    opportunities = scan_funding_opportunities()
    results = []
    for opp in opportunities[:2]:  # max 2 funding arb positions
        r = execute_funding_arb(opp, capital)
        results.append(r)
        time.sleep(1)
    return results
