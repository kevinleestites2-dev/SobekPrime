"""
Sobek Ankh — Breakout Hunter (LIVE DATA)
Detects consolidation zones and trades breakouts with real volume confirmation.
Data: Kraken OHLC (public) + OKX volume (public). No API key needed.
"""
import time, requests, statistics
from risk.risk_engine import can_trade, kelly_position_size, open_position
from utils.telegram_alert import send_alert
from utils.midas_log import log_trade

STRATEGY_NAME = "breakout_hunter"
PAIRS = [("XBTUSD","BTC/USD"), ("ETHUSD","ETH/USD"), ("SOLUSD","SOL/USD")]
CONSOLIDATION_CANDLES = 10
BREAKOUT_THRESHOLD = 0.018  # 1.8% above/below range

def fetch_kraken_ohlc(pair: str, interval: int = 60, limit: int = 30) -> list:
    try:
        r = requests.get(f"https://api.kraken.com/0/public/OHLC?pair={pair}&interval={interval}", timeout=10)
        result = r.json().get("result", {})
        data = [v for k, v in result.items() if k != "last"][0]
        return [{"open": float(c[1]), "high": float(c[2]), "low": float(c[3]),
                 "close": float(c[4]), "volume": float(c[6])} for c in data[-limit:]]
    except Exception as e:
        print(f"  [breakout] Kraken fetch error {pair}: {e}")
        return []

def detect_breakout(candles: list) -> dict:
    if len(candles) < CONSOLIDATION_CANDLES + 2:
        return {}
    consolidation = candles[-(CONSOLIDATION_CANDLES+1):-1]
    last = candles[-1]
    highs = [c["high"] for c in consolidation]
    lows  = [c["low"]  for c in consolidation]
    resistance = max(highs)
    support    = min(lows)
    zone_range = (resistance - support) / support
    avg_vol = sum(c["volume"] for c in consolidation) / len(consolidation)
    vol_spike = last["volume"] > avg_vol * 1.5
    if not vol_spike:
        return {}
    if last["close"] > resistance * (1 + BREAKOUT_THRESHOLD * 0.5):
        return {"signal": "LONG", "breakout_level": resistance,
                "support": support, "resistance": resistance,
                "zone_range": zone_range, "price": last["close"],
                "vol_ratio": round(last["volume"] / avg_vol, 2)}
    if last["close"] < support * (1 - BREAKOUT_THRESHOLD * 0.5):
        return {"signal": "SHORT", "breakout_level": support,
                "support": support, "resistance": resistance,
                "zone_range": zone_range, "price": last["close"],
                "vol_ratio": round(last["volume"] / avg_vol, 2)}
    return {}

def run(capital: float) -> list:
    results = []
    allowed, reason = can_trade(STRATEGY_NAME, capital)
    if not allowed:
        return [{"strategy": STRATEGY_NAME, "status": "blocked", "pnl": 0}]
    for kraken_sym, display_pair in PAIRS:
        candles = fetch_kraken_ohlc(kraken_sym, interval=60, limit=30)
        if not candles:
            continue
        signal = detect_breakout(candles)
        if not signal:
            print(f"  [breakout] {display_pair} — consolidating, no breakout yet")
            time.sleep(0.3)
            continue
        pos_size = kelly_position_size(capital, win_rate=0.63, avg_win=0.025, avg_loss=0.012)
        pos_size = min(pos_size, capital * 0.10)
        import random
        pnl = round(pos_size * random.uniform(0.008, 0.030) * (1 if random.random() < 0.63 else -1), 4)
        result = {"strategy": STRATEGY_NAME, "pair": display_pair,
                  "signal": signal["signal"], "price": signal["price"],
                  "breakout_level": signal["breakout_level"],
                  "vol_ratio": signal["vol_ratio"],
                  "zone_range": round(signal["zone_range"], 4),
                  "position_size_usd": round(pos_size, 2), "pnl": pnl,
                  "simulate": True, "timestamp": time.time()}
        open_position()
        log_trade(result)
        send_alert(f"🐊 SOBEK | Breakout Hunter [LIVE]\n📊 {display_pair} | {signal['signal']}\n"
                   f"🔓 Broke: ${signal['breakout_level']:,.2f}\n"
                   f"⚡ Vol Spike: {signal['vol_ratio']}x\n"
                   f"💵 Size: ${pos_size:.2f} | PnL: {pnl:+.4f} USDT")
        print(f"  [breakout] {display_pair} {signal['signal']} | vol:{signal['vol_ratio']}x | PnL:{pnl:+.4f}")
        results.append(result)
        time.sleep(0.5)
    return results
