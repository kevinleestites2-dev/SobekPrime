"""
Sobek Ankh — Strategy 2: Cross-Exchange Arbitrage
Same pair, different price on different exchanges.
Buy low on Exchange A, sell high on Exchange B.
Pure spread capture. Zero directional risk.
"""
import time
from core.exchange_bridge import fetch_ticker, place_order
from risk.risk_engine import can_trade, kelly_position_size, open_position, record_trade_result
from utils.telegram_alert import send_alert
from utils.midas_log import log_trade

STRATEGY_NAME = "cross_exchange_arb"
SCAN_PAIRS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "DOGE/USDT"]
EXCHANGES = ["binance", "bybit", "okx", "kraken"]
MIN_SPREAD_PCT = 0.003  # 0.3% minimum spread to cover fees and still profit
FEE_ESTIMATE = 0.001    # 0.1% per leg = 0.2% round trip

def scan_arbitrage_opportunities() -> list:
    """Find price discrepancies across exchanges."""
    opportunities = []

    for pair in SCAN_PAIRS:
        prices = {}
        for exchange in EXCHANGES:
            try:
                ticker = fetch_ticker(exchange, pair)
                prices[exchange] = {
                    "bid": ticker.get("bid", 0),
                    "ask": ticker.get("ask", 0),
                    "last": ticker.get("last", 0)
                }
            except Exception:
                continue

        if len(prices) < 2:
            continue

        # Find best buy (lowest ask) and best sell (highest bid)
        best_buy = min(prices.items(), key=lambda x: x[1]["ask"] if x[1]["ask"] > 0 else float("inf"))
        best_sell = max(prices.items(), key=lambda x: x[1]["bid"])

        buy_exchange, buy_data = best_buy
        sell_exchange, sell_data = best_sell

        if buy_exchange == sell_exchange:
            continue

        buy_price = buy_data["ask"]
        sell_price = sell_data["bid"]

        if buy_price <= 0 or sell_price <= 0:
            continue

        spread_pct = (sell_price - buy_price) / buy_price
        net_spread = spread_pct - (FEE_ESTIMATE * 2)

        if net_spread >= MIN_SPREAD_PCT:
            opportunities.append({
                "pair": pair,
                "buy_exchange": buy_exchange,
                "sell_exchange": sell_exchange,
                "buy_price": buy_price,
                "sell_price": sell_price,
                "spread_pct": spread_pct,
                "net_spread_pct": net_spread,
                "profit_per_1k": net_spread * 1000
            })

    opportunities.sort(key=lambda x: x["net_spread_pct"], reverse=True)
    return opportunities

def execute_arb(opportunity: dict, capital: float) -> dict:
    """Execute cross-exchange arbitrage."""
    allowed, reason = can_trade(STRATEGY_NAME, capital)
    if not allowed:
        return {"status": "blocked", "reason": reason}

    position_size = kelly_position_size(capital, win_rate=0.85, avg_win=opportunity["net_spread_pct"], avg_loss=0.001)
    position_size = min(position_size, capital * 0.15)

    amount = position_size / opportunity["buy_price"]
    expected_profit = position_size * opportunity["net_spread_pct"]

    result = {
        "strategy": STRATEGY_NAME,
        "pair": opportunity["pair"],
        "buy_exchange": opportunity["buy_exchange"],
        "sell_exchange": opportunity["sell_exchange"],
        "buy_price": opportunity["buy_price"],
        "sell_price": opportunity["sell_price"],
        "spread_pct": opportunity["spread_pct"],
        "net_spread_pct": opportunity["net_spread_pct"],
        "position_size_usd": position_size,
        "expected_profit_usd": expected_profit,
        "status": "simulated",
        "timestamp": time.time()
    }

    # Live execution:
    # buy_order = place_order(opportunity["buy_exchange"], opportunity["pair"], "buy", amount)
    # sell_order = place_order(opportunity["sell_exchange"], opportunity["pair"], "sell", amount)

    open_position()
    send_alert(
        f"🐊 SOBEK | Cross-Exchange Arb\n"
        f"📊 {opportunity['pair']}\n"
        f"🟢 Buy @ {opportunity['buy_exchange']}: ${opportunity['buy_price']:.4f}\n"
        f"🔴 Sell @ {opportunity['sell_exchange']}: ${opportunity['sell_price']:.4f}\n"
        f"💰 Net Spread: {opportunity['net_spread_pct']:.3%}\n"
        f"💵 Expected Profit: ${expected_profit:.2f}"
    )
    log_trade(result)
    return result

def run(capital: float) -> list:
    opportunities = scan_arbitrage_opportunities()
    results = []
    for opp in opportunities[:2]:
        r = execute_arb(opp, capital)
        results.append(r)
        time.sleep(0.5)
    return results
