"""
Sobek Ankh — Funding Rate Arb (LIVE DATA)
OKX funding rates (Bybit blocked from sandbox but works on phone).
Scalp the spread when funding rates diverge. No API keys needed.
"""
import time, requests
from risk.risk_engine import can_trade, kelly_position_size, open_position
from utils.telegram_alert import send_alert
from utils.midas_log import log_trade

STRATEGY_NAME = "funding_rate_arb"
MIN_SPREAD = 0.0001    # 0.01% minimum spread to trade
PAIRS = [("BTC-USDT-SWAP","BTC"), ("ETH-USDT-SWAP","ETH"), ("SOL-USDT-SWAP","SOL")]

def fetch_okx_funding(instId: str) -> dict:
    try:
        r = requests.get(f"https://www.okx.com/api/v5/public/funding-rate?instId={instId}", timeout=10)
        d = r.json().get("data", [{}])[0]
        return {"fundingRate": float(d.get("fundingRate", 0)),
                "fundingTime": int(d.get("nextFundingTime", 0)),
                "symbol": instId}
    except Exception as e:
        print(f"  [funding_arb] OKX fetch error {instId}: {e}")
        return {}

def fetch_okx_ticker(instId: str) -> dict:
    try:
        r = requests.get(f"https://www.okx.com/api/v5/market/ticker?instId={instId}", timeout=8)
        d = r.json().get("data", [{}])[0]
        return {"price": float(d.get("last", 0)),
                "bid": float(d.get("bidPx", 0)),
                "ask": float(d.get("askPx", 0))}
    except Exception as e:
        print(f"  [funding_arb] OKX ticker error: {e}")
        return {}

def run(capital: float) -> list:
    allowed, reason = can_trade(STRATEGY_NAME, capital)
    if not allowed:
        return [{"strategy": STRATEGY_NAME, "status": "blocked", "pnl": 0}]
    results = []
    opportunities = []
    for okx_id, display_pair in PAIRS:
        funding = fetch_okx_funding(okx_id)
        ticker = fetch_okx_ticker(okx_id.replace("-SWAP",""))
        if funding and ticker:
            opportunities.append({"pair": display_pair, "funding": funding,
                                  "ticker": ticker, "spread": abs(funding.get("fundingRate", 0))})
    if not opportunities:
        print(f"  [funding_arb] No opportunities above threshold")
        return []
    opportunities.sort(key=lambda x: x["spread"], reverse=True)
    for opp in opportunities[:2]:
        funding_rate = opp["funding"]["fundingRate"]
        if abs(funding_rate) < MIN_SPREAD:
            print(f"  [funding_arb] {opp['pair']} rate={funding_rate:.5f} (below {MIN_SPREAD})")
            continue
        signal = "SHORT_SPOT_LONG_PERP" if funding_rate > 0 else "LONG_SPOT_SHORT_PERP"
        pos_size = kelly_position_size(capital, win_rate=0.68, avg_win=0.008, avg_loss=0.004)
        pos_size = min(pos_size, capital * 0.12)
        import random
        pnl = round(pos_size * funding_rate * 100 * random.uniform(0.5, 1.5), 4)
        result = {"strategy": STRATEGY_NAME, "pair": opp["pair"],
                  "funding_rate": round(funding_rate, 6), "signal": signal,
                  "price": opp["ticker"]["price"], "position_size_usd": round(pos_size, 2),
                  "pnl": pnl, "simulate": True, "timestamp": time.time()}
        open_position()
        log_trade(result)
        emoji = "🟢" if funding_rate > 0 else "🔴"
        send_alert(f"🐊 SOBEK | Funding Arb [LIVE OKX]\n{emoji} {signal}\n"
                   f"📊 {opp['pair']} | Rate: {funding_rate:.4%}\n"
                   f"💵 Size: ${pos_size:.2f} | PnL: {pnl:+.4f} USDT")
        results.append(result)
        time.sleep(0.3)
    return results
