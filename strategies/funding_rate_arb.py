"""
Sobek Ankh — Strategy 1: Funding Rate Arbitrage (LIVE DATA)
Fetches REAL funding rates from Binance/Bybit public APIs.
No API key needed — funding rates are public.
Long spot + short perp. Collect funding every 8h.
Zero directional risk. 10-164% APY documented.
"""
import time
import requests as req
from risk.risk_engine import can_trade, kelly_position_size, open_position, get_stop_loss, get_take_profit
from utils.telegram_alert import send_alert
from utils.midas_log import log_trade

STRATEGY_NAME = "funding_rate_arb"
MIN_FUNDING_RATE = 0.0003  # 0.03% per 8h = ~3.3% APY minimum
MAX_POSITIONS = 3

# Public funding rate endpoints (no API key needed)
def fetch_binance_funding_rates() -> list:
    """Fetch all perpetual funding rates from Binance public API."""
    try:
        url = "https://fapi.binance.com/fapi/v1/premiumIndex"
        r = req.get(url, timeout=10)
        data = r.json()
        results = []
        for item in data:
            try:
                rate = float(item.get("lastFundingRate", 0))
                symbol = item.get("symbol", "")
                if "USDT" in symbol and abs(rate) >= MIN_FUNDING_RATE:
                    results.append({
                        "exchange": "binance",
                        "symbol": symbol,
                        "pair": symbol.replace("USDT", "/USDT"),
                        "rate": rate,
                        "mark_price": float(item.get("markPrice", 0)),
                        "apy_estimate": abs(rate) * 3 * 365 * 100
                    })
            except Exception:
                continue
        return sorted(results, key=lambda x: abs(x["rate"]), reverse=True)
    except Exception as e:
        print(f"  [funding_arb] Binance fetch error: {e}")
        return []

def fetch_bybit_funding_rates() -> list:
    """Fetch funding rates from Bybit public API."""
    try:
        url = "https://api.bybit.com/v5/market/tickers?category=linear"
        r = req.get(url, timeout=10)
        data = r.json()
        results = []
        items = data.get("result", {}).get("list", [])
        for item in items:
            try:
                rate = float(item.get("fundingRate", 0))
                symbol = item.get("symbol", "")
                if "USDT" in symbol and abs(rate) >= MIN_FUNDING_RATE:
                    results.append({
                        "exchange": "bybit",
                        "symbol": symbol,
                        "pair": symbol.replace("USDT", "/USDT"),
                        "rate": rate,
                        "mark_price": float(item.get("markPrice", 0)),
                        "apy_estimate": abs(rate) * 3 * 365 * 100
                    })
            except Exception:
                continue
        return sorted(results, key=lambda x: abs(x["rate"]), reverse=True)
    except Exception as e:
        print(f"  [funding_arb] Bybit fetch error: {e}")
        return []

def scan_funding_opportunities() -> list:
    """Merge and rank all funding rate opportunities."""
    binance_opps = fetch_binance_funding_rates()
    bybit_opps = fetch_bybit_funding_rates()
    all_opps = binance_opps + bybit_opps
    all_opps.sort(key=lambda x: abs(x["rate"]), reverse=True)
    return all_opps[:10]  # top 10 across both exchanges

def execute_funding_arb(opp: dict, capital: float) -> dict:
    """Simulate funding arb execution with real rate data."""
    allowed, reason = can_trade(STRATEGY_NAME, capital)
    if not allowed:
        return {"strategy": STRATEGY_NAME, "status": "blocked", "reason": reason, "pnl": 0}

    rate = opp["rate"]
    pair = opp["pair"]
    exchange = opp["exchange"]
    mark_price = opp["mark_price"]
    apy = opp["apy_estimate"]

    # Position sizing — kelly conservative for funding arb
    position_size = kelly_position_size(capital, win_rate=0.80, avg_win=abs(rate)*3, avg_loss=abs(rate)*0.3)
    position_size = min(position_size, capital * 0.10)

    # PnL = funding rate collected this period (8h window)
    pnl = round(position_size * abs(rate), 4)

    direction = "SHORT_PERP" if rate > 0 else "LONG_PERP"

    result = {
        "strategy": STRATEGY_NAME,
        "exchange": exchange,
        "pair": pair,
        "funding_rate": round(rate, 6),
        "apy_estimate": round(apy, 2),
        "direction": direction,
        "position_size_usd": round(position_size, 2),
        "mark_price": mark_price,
        "pnl": pnl,
        "simulate": True,
        "timestamp": time.time()
    }

    open_position()
    send_alert(
        f"🐊 SOBEK | Funding Arb [LIVE DATA]\n"
        f"📈 {pair} @ {exchange}\n"
        f"💰 Rate: {rate:.4%} ({apy:.1f}% APY)\n"
        f"📊 Direction: {direction}\n"
        f"💵 Size: ${position_size:.2f} | PnL: +{pnl:.4f} USDT"
    )
    log_trade(result)
    return result

def run(capital: float) -> list:
    """Main entry: scan real funding rates and simulate execution."""
    opportunities = scan_funding_opportunities()
    if not opportunities:
        print("  [funding_arb] No opportunities above threshold")
        return []

    print(f"  [funding_arb] Found {len(opportunities)} real opportunities")
    results = []
    for opp in opportunities[:MAX_POSITIONS]:
        r = execute_funding_arb(opp, capital)
        results.append(r)
        time.sleep(0.5)
    return results
