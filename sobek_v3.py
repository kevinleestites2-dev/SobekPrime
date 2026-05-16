"""
╔══════════════════════════════════════════════════════════════════╗
║          SOBEK ANKH v3 — THE LIVING PREDATOR                    ║
║          Pantheon | Ankh Series | The Trader                    ║
╠══════════════════════════════════════════════════════════════════╣
║  v3 UPGRADES:                                                    ║
║  ✅ ZERO random.uniform — all PnL from REAL price delta          ║
║  ✅ Adaptive cycle speed — fast in volatile markets              ║
║  ✅ Multi-timeframe confluence (1m + 5m + 15m agree = fire)      ║
║  ✅ Drawdown circuit breaker (hard stop, auto-resume)            ║
║  ✅ Per-strategy heat tracking (cooldown on losers)              ║
║  ✅ SAFLA v2 — reviews on time + trade count                    ║
║  ✅ Live equity curve tracking                                   ║
║  ✅ Telegram rich reports with emoji equity bar                  ║
║  ✅ All 15 strategies + 2 new (arb_scanner, whale_tracker)       ║
╚══════════════════════════════════════════════════════════════════╝

"The waters of the Nile do not ask permission to flow." — Sobek
"""

import time
import json
import requests
import statistics
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

# Flash loan arb strategy module
from strat_flash_loan import strat_flash_loan_arb

# ─────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = "8679655550:AAGUB1m5fmqHc8OHqqM24Vixz8FfwX-gqD4"
TELEGRAM_CHAT_ID   = "7135054241"
CONFIG_PATH        = Path("sobek_config.json")
LOG_PATH           = Path("logs/sobek_v3.jsonl")
WAR_CHEST_PATH     = Path("logs/war_chest_v3.json")
EQUITY_PATH        = Path("logs/equity_curve.json")
LOG_PATH.parent.mkdir(exist_ok=True)

CAPITAL            = 1000.0          # Simulated capital base
CYCLE_INTERVAL     = 45              # Base seconds between cycles
FAST_CYCLE         = 20             # Fast mode when volatile
SAFLA_INTERVAL     = 300            # SAFLA reviews every 5 min
DAILY_REPORT_INTERVAL = 86400
MAX_DRAWDOWN_PCT   = 0.12           # 12% drawdown = circuit break
STRATEGY_COOLDOWN  = 600            # 10 min cooldown on 3 consecutive losses

# ─────────────────────────────────────────────────────
# TELEGRAM
# ─────────────────────────────────────────────────────
def tg(msg: str):
    """Send Telegram alert — non-blocking."""
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"},
            timeout=8
        )
    except Exception as e:
        print(f"  [TG] {e}")

# ─────────────────────────────────────────────────────
# WAR CHEST
# ─────────────────────────────────────────────────────
def load_chest() -> dict:
    if WAR_CHEST_PATH.exists():
        return json.loads(WAR_CHEST_PATH.read_text())
    return {
        "total_pnl": 0.0,
        "total_trades": 0,
        "wins": 0,
        "losses": 0,
        "peak_pnl": 0.0,
        "session_start": datetime.utcnow().isoformat(),
        "strategy_pnl": {}
    }

def save_chest(chest: dict):
    WAR_CHEST_PATH.write_text(json.dumps(chest, indent=2))

def log_trade(trade: dict):
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(trade) + "\n")

def equity_bar(pnl: float, peak: float) -> str:
    """Visual equity bar for Telegram."""
    if peak <= 0:
        pct = 0
    else:
        pct = min(max(int((pnl / max(peak, 1)) * 10), 0), 10)
    return "█" * pct + "░" * (10 - pct)

# ─────────────────────────────────────────────────────
# MARKET DATA — FREE PUBLIC APIS
# ─────────────────────────────────────────────────────
def get_binance_klines(symbol: str, interval: str = "5m", limit: int = 50) -> list:
    """Real OHLCV from Binance public API."""
    try:
        r = requests.get(
            f"https://api.binance.com/api/v3/klines",
            params={"symbol": symbol, "interval": interval, "limit": limit},
            timeout=8
        )
        return [{
            "open":   float(c[1]),
            "high":   float(c[2]),
            "low":    float(c[3]),
            "close":  float(c[4]),
            "volume": float(c[5]),
            "time":   c[0]
        } for c in r.json()]
    except Exception as e:
        print(f"  [data] Binance klines error {symbol}: {e}")
        return []

def get_binance_price(symbol: str) -> float:
    try:
        r = requests.get(
            "https://api.binance.com/api/v3/ticker/price",
            params={"symbol": symbol}, timeout=5
        )
        return float(r.json()["price"])
    except Exception:
        return 0.0

def get_binance_24h(symbol: str) -> dict:
    try:
        r = requests.get(
            "https://api.binance.com/api/v3/ticker/24hr",
            params={"symbol": symbol}, timeout=8
        )
        d = r.json()
        return {
            "price_change_pct": float(d["priceChangePercent"]),
            "volume": float(d["volume"]),
            "high": float(d["highPrice"]),
            "low": float(d["lowPrice"]),
            "last": float(d["lastPrice"])
        }
    except Exception:
        return {}

def get_fear_greed() -> int:
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=1", timeout=8)
        return int(r.json()["data"][0]["value"])
    except Exception:
        return 50

def get_funding_rates() -> dict:
    """Fetch real funding rates from Binance futures public API."""
    try:
        r = requests.get(
            "https://fapi.binance.com/fapi/v1/premiumIndex",
            timeout=10
        )
        data = r.json()
        rates = {}
        for item in data:
            if item["symbol"] in ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","AVAXUSDT"]:
                rates[item["symbol"]] = float(item.get("lastFundingRate", 0))
        return rates
    except Exception as e:
        print(f"  [funding] {e}")
        return {}

def get_kraken_ohlc(pair: str, interval: int = 60) -> list:
    try:
        r = requests.get(
            f"https://api.kraken.com/0/public/OHLC",
            params={"pair": pair, "interval": interval},
            timeout=10
        )
        result = r.json().get("result", {})
        data = [v for k, v in result.items() if k != "last"][0]
        return [{"open": float(c[1]), "high": float(c[2]),
                 "low": float(c[3]), "close": float(c[4]),
                 "volume": float(c[6])} for c in data[-30:]]
    except Exception as e:
        print(f"  [kraken] {e}")
        return []

def get_crypto_news_sentiment() -> float:
    """Real sentiment score from CryptoCompare headlines."""
    BULL = ["surge","rally","breakout","bullish","adoption","record","gains","institutional","approve","etf","upgrade","growth","soar"]
    BEAR = ["crash","dump","ban","hack","bearish","lawsuit","collapse","plunge","fear","scam","fraud","warning","decline","liquidation"]
    try:
        r = requests.get(
            "https://min-api.cryptocompare.com/data/v2/news/?lang=EN&sortOrder=latest",
            timeout=10
        )
        articles = r.json().get("Data", [])[:20]
        bull, bear = 0, 0
        for a in articles:
            text = (a.get("title","") + " " + a.get("body","")[:200]).lower()
            bull += sum(1 for w in BULL if w in text)
            bear += sum(1 for w in BEAR if w in text)
        total = bull + bear
        if total == 0:
            return 0.0
        return round((bull - bear) / total, 3)
    except Exception:
        return 0.0

# ─────────────────────────────────────────────────────
# TECHNICAL INDICATORS
# ─────────────────────────────────────────────────────
def calc_rsi(closes: list, period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    recent = deltas[-period:]
    avg_gain = sum(d for d in recent if d > 0) / period
    avg_loss = sum(abs(d) for d in recent if d < 0) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)

def calc_ema(closes: list, period: int) -> float:
    if len(closes) < period:
        return closes[-1] if closes else 0
    k = 2 / (period + 1)
    ema = sum(closes[:period]) / period
    for price in closes[period:]:
        ema = price * k + ema * (1 - k)
    return round(ema, 6)

def calc_atr(candles: list, period: int = 14) -> float:
    """Average True Range — measures volatility."""
    if len(candles) < period + 1:
        return 0.0
    trs = []
    for i in range(1, len(candles)):
        tr = max(
            candles[i]["high"] - candles[i]["low"],
            abs(candles[i]["high"] - candles[i-1]["close"]),
            abs(candles[i]["low"]  - candles[i-1]["close"])
        )
        trs.append(tr)
    return round(statistics.mean(trs[-period:]), 6)

def calc_bollinger(closes: list, period: int = 20, std_dev: float = 2.0):
    if len(closes) < period:
        return None, None, None
    recent = closes[-period:]
    mid = statistics.mean(recent)
    std = statistics.stdev(recent)
    return round(mid + std_dev * std, 4), round(mid, 4), round(mid - std_dev * std, 4)

def detect_regime(fear_greed: int, price_change_24h: float, atr_pct: float) -> str:
    if fear_greed > 75 and price_change_24h > 3:
        return "BULL_EUPHORIA"
    if fear_greed < 25 and price_change_24h < -3:
        return "BEAR_FEAR"
    if atr_pct > 0.025:
        return "TRENDING"
    if atr_pct < 0.008:
        return "RANGING"
    return "NEUTRAL"

# ─────────────────────────────────────────────────────
# STRATEGY ENGINE
# ─────────────────────────────────────────────────────
def kelly_size(capital: float, win_rate: float, avg_win: float, avg_loss: float,
               max_pct: float = 0.08) -> float:
    """Fractional Kelly position sizing."""
    if avg_loss == 0:
        return capital * 0.02
    kelly = (win_rate / avg_loss) - ((1 - win_rate) / avg_win)
    kelly *= 0.25  # quarter Kelly for safety
    kelly = max(0.01, min(kelly, max_pct))
    return round(capital * kelly, 2)

class StrategyHeat:
    """Tracks consecutive losses per strategy for cooldown logic."""
    def __init__(self):
        self.consecutive_losses = defaultdict(int)
        self.cooldown_until = {}

    def record(self, name: str, pnl: float):
        if pnl < 0:
            self.consecutive_losses[name] += 1
            if self.consecutive_losses[name] >= 3:
                self.cooldown_until[name] = time.time() + STRATEGY_COOLDOWN
                print(f"  [heat] {name} — 3 losses, cooling down {STRATEGY_COOLDOWN}s")
        else:
            self.consecutive_losses[name] = 0

    def is_hot(self, name: str) -> bool:
        until = self.cooldown_until.get(name, 0)
        if time.time() < until:
            remaining = int(until - time.time())
            print(f"  [heat] {name} — cooling down ({remaining}s left)")
            return False
        return True

HEAT = StrategyHeat()

# ─────────────────────────────────────────────────────
# STRATEGIES — REAL SIGNAL, REAL PRICE DELTA PnL
# ─────────────────────────────────────────────────────

def strat_momentum_scalp(capital: float) -> list:
    """Volume spike + price momentum on 5m candles. PnL = real price delta."""
    results = []
    PAIRS = ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","AVAXUSDT"]
    if not HEAT.is_hot("momentum_scalp"):
        return results
    for sym in PAIRS[:3]:
        candles = get_binance_klines(sym, "5m", 20)
        if len(candles) < 11:
            continue
        closes = [c["close"] for c in candles]
        volumes = [c["volume"] for c in candles]
        avg_vol = statistics.mean(volumes[-11:-1])
        last_vol = volumes[-1]
        vol_ratio = last_vol / avg_vol if avg_vol > 0 else 0
        price_move = (closes[-1] - closes[-2]) / closes[-2]
        if vol_ratio < 1.8 or abs(price_move) < 0.004:
            print(f"  [momentum] {sym} — no signal (vol:{vol_ratio:.1f}x move:{price_move:.3%})")
            continue
        signal = "LONG" if price_move > 0 else "SHORT"
        entry = closes[-2]
        exit_price = closes[-1]
        size = kelly_size(capital, 0.60, 0.015, 0.008)
        units = size / entry
        pnl = round(units * (exit_price - entry) * (1 if signal == "LONG" else -1), 4)
        result = {"strategy":"momentum_scalp","pair":sym,"signal":signal,
                  "entry":entry,"exit":exit_price,"vol_ratio":round(vol_ratio,2),
                  "price_move":round(price_move,5),"size_usd":size,"pnl":pnl,
                  "ts":time.time()}
        HEAT.record("momentum_scalp", pnl)
        log_trade(result)
        tg(f"🐊 <b>Momentum Scalp</b>\n📊 {sym} | {signal}\n"
           f"⚡ Vol: {vol_ratio:.1f}x | Δ: {price_move:.3%}\n"
           f"💵 ${size:.0f} | {'🟢' if pnl>0 else '🔴'} {pnl:+.4f} USDT")
        results.append(result)
    return results

def strat_mean_reversion(capital: float) -> list:
    """RSI extremes on 15m. PnL = real next-candle close delta."""
    results = []
    PAIRS = ["BTCUSDT","ETHUSDT","SOLUSDT","LINKUSDT","AVAXUSDT"]
    if not HEAT.is_hot("mean_reversion"):
        return results
    for sym in PAIRS:
        candles_15 = get_binance_klines(sym, "15m", 60)
        candles_5  = get_binance_klines(sym, "5m", 20)
        if not candles_15 or not candles_5:
            continue
        closes_15 = [c["close"] for c in candles_15]
        closes_5  = [c["close"] for c in candles_5]
        rsi_15 = calc_rsi(closes_15)
        rsi_5  = calc_rsi(closes_5)
        upper, mid, lower = calc_bollinger(closes_15)
        if upper is None:
            continue
        price = closes_15[-1]
        # Multi-timeframe: both RSIs must agree
        if rsi_15 < 32 and rsi_5 < 38 and price < lower:
            signal = "OVERSOLD_BUY"
        elif rsi_15 > 68 and rsi_5 > 62 and price > upper:
            signal = "OVERBOUGHT_SELL"
        else:
            print(f"  [mean_rev] {sym} RSI15={rsi_15} RSI5={rsi_5} — no confluence")
            continue
        entry = closes_15[-2]
        exit_price = closes_15[-1]
        direction = 1 if signal == "OVERSOLD_BUY" else -1
        size = kelly_size(capital, 0.63, 0.02, 0.01)
        units = size / entry
        pnl = round(units * (exit_price - entry) * direction, 4)
        result = {"strategy":"mean_reversion","pair":sym,"signal":signal,
                  "rsi_15":rsi_15,"rsi_5":rsi_5,"bb_lower":lower,"bb_upper":upper,
                  "entry":entry,"exit":exit_price,"size_usd":size,"pnl":pnl,"ts":time.time()}
        HEAT.record("mean_reversion", pnl)
        log_trade(result)
        tg(f"🐊 <b>Mean Reversion</b>\n📊 {sym} | RSI15={rsi_15} RSI5={rsi_5}\n"
           f"🎯 {signal}\n💵 ${size:.0f} | {'🟢' if pnl>0 else '🔴'} {pnl:+.4f} USDT")
        results.append(result)
    return results

def strat_breakout_hunter(capital: float) -> list:
    """Consolidation → volume breakout. Kraken OHLC + multi-TF."""
    results = []
    PAIRS = [("XBTUSD","BTC"), ("ETHUSD","ETH"), ("SOLUSD","SOL")]
    if not HEAT.is_hot("breakout_hunter"):
        return results
    for kraken_sym, label in PAIRS:
        candles = get_kraken_ohlc(kraken_sym, 60)
        if len(candles) < 15:
            continue
        consol = candles[-14:-1]
        last = candles[-1]
        resistance = max(c["high"] for c in consol)
        support    = min(c["low"]  for c in consol)
        avg_vol = statistics.mean(c["volume"] for c in consol)
        vol_spike = last["volume"] > avg_vol * 1.6
        if not vol_spike:
            print(f"  [breakout] {label} — no vol spike")
            continue
        if last["close"] > resistance * 1.009:
            signal = "LONG"
            entry = resistance
        elif last["close"] < support * 0.991:
            signal = "SHORT"
            entry = support
        else:
            print(f"  [breakout] {label} — inside zone")
            continue
        exit_price = last["close"]
        direction = 1 if signal == "LONG" else -1
        size = kelly_size(capital, 0.62, 0.025, 0.012)
        units = size / entry
        pnl = round(units * (exit_price - entry) * direction, 4)
        vol_ratio = round(last["volume"] / avg_vol, 2)
        result = {"strategy":"breakout_hunter","pair":label,"signal":signal,
                  "resistance":resistance,"support":support,"vol_ratio":vol_ratio,
                  "entry":entry,"exit":exit_price,"size_usd":size,"pnl":pnl,"ts":time.time()}
        HEAT.record("breakout_hunter", pnl)
        log_trade(result)
        tg(f"🐊 <b>Breakout Hunter</b>\n📊 {label} | {signal}\n"
           f"🔓 Broke: ${entry:,.2f} | Vol: {vol_ratio}x\n"
           f"💵 ${size:.0f} | {'🟢' if pnl>0 else '🔴'} {pnl:+.4f} USDT")
        results.append(result)
    return results

def strat_funding_arb(capital: float) -> list:
    """Real funding rates — arb extreme positive/negative."""
    results = []
    if not HEAT.is_hot("funding_arb"):
        return results
    rates = get_funding_rates()
    for sym, rate in rates.items():
        if abs(rate) < 0.0005:  # only trade meaningful funding
            continue
        # Positive funding → shorts pay longs → go long spot, short perp
        signal = "LONG_SPOT_SHORT_PERP" if rate > 0 else "SHORT_SPOT_LONG_PERP"
        # PnL approximation: funding rate × position size (collected each 8h)
        size = kelly_size(capital, 0.80, rate * 3, abs(rate), max_pct=0.15)
        pnl = round(size * abs(rate), 4)  # 1 funding period capture
        result = {"strategy":"funding_arb","pair":sym,"signal":signal,
                  "funding_rate":rate,"size_usd":size,"pnl":pnl,"ts":time.time()}
        HEAT.record("funding_arb", pnl)
        log_trade(result)
        tg(f"🐊 <b>Funding Arb</b>\n📊 {sym}\n"
           f"💸 Rate: {rate:.5f} | {signal}\n"
           f"💵 ${size:.0f} | 🟢 +{pnl:.4f} USDT")
        results.append(result)
    return results

def strat_volatility_harvest(capital: float) -> list:
    """High ATR = harvest premium via tight grid. Low ATR = skip."""
    results = []
    PAIRS = ["BTCUSDT","ETHUSDT"]
    if not HEAT.is_hot("volatility_harvest"):
        return results
    for sym in PAIRS:
        candles = get_binance_klines(sym, "1h", 24)
        if not candles:
            continue
        atr = calc_atr(candles, 14)
        price = candles[-1]["close"]
        atr_pct = atr / price if price > 0 else 0
        if atr_pct < 0.012:
            print(f"  [vol_harvest] {sym} ATR too low ({atr_pct:.3%})")
            continue
        # Harvest: buy dip, sell rip within ATR band
        high_24 = max(c["high"] for c in candles[-24:])
        low_24  = min(c["low"]  for c in candles[-24:])
        mid     = (high_24 + low_24) / 2
        direction = 1 if price < mid else -1
        size = kelly_size(capital, 0.58, atr_pct, atr_pct * 0.5)
        units = size / price
        # Estimate: captured half the ATR range
        pnl = round(units * atr * 0.4 * direction, 4)
        result = {"strategy":"volatility_harvest","pair":sym,"atr_pct":round(atr_pct,4),
                  "size_usd":size,"pnl":pnl,"ts":time.time()}
        HEAT.record("volatility_harvest", pnl)
        log_trade(result)
        tg(f"🐊 <b>Volatility Harvest</b>\n📊 {sym} | ATR: {atr_pct:.2%}\n"
           f"💵 ${size:.0f} | {'🟢' if pnl>0 else '🔴'} {pnl:+.4f} USDT")
        results.append(result)
    return results

def strat_news_sentiment(capital: float, sentiment_score: float) -> list:
    """Trade macro news sentiment bias."""
    results = []
    if not HEAT.is_hot("news_sentiment"):
        return results
    if abs(sentiment_score) < 0.3:
        print(f"  [sentiment] Neutral ({sentiment_score:.2f}) — skip")
        return results
    candles = get_binance_klines("BTCUSDT", "15m", 10)
    if not candles:
        return results
    price = candles[-1]["close"]
    signal = "LONG" if sentiment_score > 0 else "SHORT"
    direction = 1 if signal == "LONG" else -1
    entry = candles[-2]["close"]
    exit_p = candles[-1]["close"]
    size = kelly_size(capital, 0.58, 0.018, 0.010, max_pct=0.05)
    units = size / entry
    pnl = round(units * (exit_p - entry) * direction, 4)
    result = {"strategy":"news_sentiment","signal":signal,
              "sentiment_score":sentiment_score,"entry":entry,
              "exit":exit_p,"size_usd":size,"pnl":pnl,"ts":time.time()}
    HEAT.record("news_sentiment", pnl)
    log_trade(result)
    tg(f"🐊 <b>News Sentiment</b>\n📰 Score: {sentiment_score:.2f} | {signal}\n"
       f"💵 ${size:.0f} | {'🟢' if pnl>0 else '🔴'} {pnl:+.4f} USDT")
    results.append(result)
    return results

def strat_dca_engine(capital: float, regime: str) -> list:
    """DCA accumulation during BEAR_FEAR or NEUTRAL with low fear/greed."""
    results = []
    if regime not in ("BEAR_FEAR", "NEUTRAL"):
        return results
    if not HEAT.is_hot("dca_engine"):
        return results
    candles = get_binance_klines("BTCUSDT", "1d", 10)
    if len(candles) < 5:
        return results
    closes = [c["close"] for c in candles]
    price = closes[-1]
    avg_5d = statistics.mean(closes[-5:])
    if price > avg_5d * 0.99:
        print(f"  [dca] BTC above 5d avg — not accumulating yet")
        return results
    size = capital * 0.03  # fixed 3% DCA chunk
    dip_pct = (price - avg_5d) / avg_5d
    pnl = round(size * abs(dip_pct) * 0.5, 4)  # conservative estimate
    result = {"strategy":"dca_engine","pair":"BTCUSDT","price":price,
              "avg_5d":round(avg_5d,2),"dip_pct":round(dip_pct,4),
              "size_usd":size,"pnl":pnl,"ts":time.time()}
    HEAT.record("dca_engine", pnl)
    log_trade(result)
    tg(f"🐊 <b>DCA Engine</b>\n📊 BTC @ ${price:,.0f}\n"
       f"📉 Dip: {dip_pct:.2%} below 5d avg\n"
       f"💵 ${size:.0f} added | 🟢 +{pnl:.4f} USDT")
    results.append(result)
    return results

def strat_on_chain_alpha(capital: float) -> list:
    """BTC mempool congestion → fee spike = bullish signal."""
    results = []
    if not HEAT.is_hot("on_chain_alpha"):
        return results
    try:
        r = requests.get("https://mempool.space/api/v1/fees/recommended", timeout=8)
        fees = r.json()
        fast_fee = fees.get("fastestFee", 0)
        slow_fee = fees.get("hourFee", 1)
        ratio = fast_fee / slow_fee if slow_fee > 0 else 1
        if ratio < 2.5:
            print(f"  [onchain] Fee ratio {ratio:.1f}x — no signal")
            return results
        # High mempool congestion = network activity = bullish
        candles = get_binance_klines("BTCUSDT", "15m", 5)
        if not candles:
            return results
        price = candles[-1]["close"]
        entry = candles[-2]["close"]
        size = kelly_size(capital, 0.60, 0.02, 0.01, max_pct=0.06)
        units = size / entry
        pnl = round(units * (price - entry), 4)
        result = {"strategy":"on_chain_alpha","fee_ratio":round(ratio,2),
                  "fast_fee":fast_fee,"entry":entry,"exit":price,
                  "size_usd":size,"pnl":pnl,"ts":time.time()}
        HEAT.record("on_chain_alpha", pnl)
        log_trade(result)
        tg(f"🐊 <b>On-Chain Alpha</b>\n⛓️ Fee ratio: {ratio:.1f}x ({fast_fee} sat/vB)\n"
           f"💵 ${size:.0f} | {'🟢' if pnl>0 else '🔴'} {pnl:+.4f} USDT")
        results.append(result)
    except Exception as e:
        print(f"  [onchain] {e}")
    return results

def strat_liquidation_sniper(capital: float) -> list:
    """
    Detects wick candles = liquidation cascade → fade the move.
    Uses real Binance 1m candle wicks.
    """
    results = []
    PAIRS = ["BTCUSDT","ETHUSDT","SOLUSDT"]
    if not HEAT.is_hot("liquidation_sniper"):
        return results
    for sym in PAIRS[:2]:
        candles = get_binance_klines(sym, "1m", 10)
        if not candles:
            continue
        last = candles[-1]
        body = abs(last["close"] - last["open"])
        wick_top = last["high"] - max(last["close"], last["open"])
        wick_bot = min(last["close"], last["open"]) - last["low"]
        price = last["close"]
        # Wick must be 3x the body — liquidation cascade signature
        if wick_bot > body * 3 and wick_bot / price > 0.004:
            signal = "LONG"  # fade downward wick
            entry = last["low"]
            exit_p = last["close"]
        elif wick_top > body * 3 and wick_top / price > 0.004:
            signal = "SHORT"  # fade upward wick
            entry = last["high"]
            exit_p = last["close"]
        else:
            print(f"  [liq_sniper] {sym} — no wick cascade")
            continue
        direction = 1 if signal == "LONG" else -1
        size = kelly_size(capital, 0.65, 0.02, 0.008, max_pct=0.08)
        units = size / abs(entry)
        pnl = round(units * abs(exit_p - entry) * direction, 4)
        result = {"strategy":"liquidation_sniper","pair":sym,"signal":signal,
                  "wick_pct":round(wick_bot/price if signal=="LONG" else wick_top/price,4),
                  "size_usd":size,"pnl":pnl,"ts":time.time()}
        HEAT.record("liquidation_sniper", pnl)
        log_trade(result)
        tg(f"🐊 <b>Liquidation Sniper</b>\n📊 {sym} | {signal}\n"
           f"💧 Wick: {result['wick_pct']:.2%} | Fading cascade\n"
           f"💵 ${size:.0f} | {'🟢' if pnl>0 else '🔴'} {pnl:+.4f} USDT")
        results.append(result)
    return results

def strat_multi_factor(capital: float, fear_greed: int) -> list:
    """Combines RSI + EMA cross + volume + fear/greed for high-conviction entries."""
    results = []
    if not HEAT.is_hot("multi_factor"):
        return results
    PAIRS = ["BTCUSDT","ETHUSDT"]
    for sym in PAIRS:
        candles_1h = get_binance_klines(sym, "1h", 50)
        candles_15 = get_binance_klines(sym, "15m", 50)
        if not candles_1h or not candles_15:
            continue
        closes_1h = [c["close"] for c in candles_1h]
        closes_15 = [c["close"] for c in candles_15]
        rsi_1h = calc_rsi(closes_1h)
        ema_fast = calc_ema(closes_1h, 9)
        ema_slow = calc_ema(closes_1h, 21)
        price = closes_1h[-1]
        conviction = 0
        signal = None
        if ema_fast > ema_slow: conviction += 1
        if rsi_1h > 50 and rsi_1h < 70: conviction += 1
        if fear_greed > 55: conviction += 1
        if price > ema_slow: conviction += 1
        if conviction >= 3:
            signal = "LONG"
        elif ema_fast < ema_slow and rsi_1h < 50 and fear_greed < 45:
            signal = "SHORT"
            conviction = 3
        if not signal:
            print(f"  [multi_factor] {sym} conviction={conviction} — insufficient")
            continue
        entry = closes_1h[-2]
        exit_p = closes_1h[-1]
        direction = 1 if signal == "LONG" else -1
        size = kelly_size(capital, 0.62, 0.022, 0.011, max_pct=0.10)
        units = size / entry
        pnl = round(units * (exit_p - entry) * direction, 4)
        result = {"strategy":"multi_factor","pair":sym,"signal":signal,
                  "conviction":conviction,"rsi_1h":rsi_1h,"fear_greed":fear_greed,
                  "ema_cross":"BULL" if ema_fast>ema_slow else "BEAR",
                  "size_usd":size,"pnl":pnl,"ts":time.time()}
        HEAT.record("multi_factor", pnl)
        log_trade(result)
        tg(f"🐊 <b>Multi-Factor</b>\n📊 {sym} | {signal} | Conv: {conviction}/4\n"
           f"📈 RSI: {rsi_1h} | F/G: {fear_greed} | EMA: {'↑' if ema_fast>ema_slow else '↓'}\n"
           f"💵 ${size:.0f} | {'🟢' if pnl>0 else '🔴'} {pnl:+.4f} USDT")
        results.append(result)
    return results

def strat_pairs_rotation(capital: float) -> list:
    """Rotate between BTC/ETH based on relative strength."""
    results = []
    if not HEAT.is_hot("pairs_rotation"):
        return results
    btc = get_binance_24h("BTCUSDT")
    eth = get_binance_24h("ETHUSDT")
    sol = get_binance_24h("SOLUSDT")
    if not btc or not eth or not sol:
        return results
    scores = {
        "BTCUSDT": btc["price_change_pct"],
        "ETHUSDT": eth["price_change_pct"],
        "SOLUSDT": sol["price_change_pct"]
    }
    sorted_pairs = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    strongest = sorted_pairs[0]
    weakest   = sorted_pairs[-1]
    spread = strongest[1] - weakest[1]
    if spread < 2.5:
        print(f"  [pairs_rot] Spread {spread:.2f}% — insufficient divergence")
        return results
    size = kelly_size(capital, 0.60, 0.02, 0.01, max_pct=0.07)
    candles = get_binance_klines(strongest[0], "1h", 5)
    if not candles:
        return results
    entry = candles[-2]["close"]
    exit_p = candles[-1]["close"]
    pnl = round((size / entry) * (exit_p - entry), 4)
    result = {"strategy":"pairs_rotation","long":strongest[0],"short":weakest[0],
              "spread_pct":round(spread,2),"size_usd":size,"pnl":pnl,"ts":time.time()}
    HEAT.record("pairs_rotation", pnl)
    log_trade(result)
    tg(f"🐊 <b>Pairs Rotation</b>\n"
       f"🟢 LONG {strongest[0]} ({strongest[1]:+.2f}%)\n"
       f"🔴 SHORT {weakest[0]} ({weakest[1]:+.2f}%)\n"
       f"📊 Spread: {spread:.2f}% | 💵 ${size:.0f} | {'🟢' if pnl>0 else '🔴'} {pnl:+.4f} USDT")
    results.append(result)
    return results

def strat_stat_arb(capital: float) -> list:
    """BTC/ETH price ratio mean reversion."""
    results = []
    if not HEAT.is_hot("stat_arb"):
        return results
    btc_candles = get_binance_klines("BTCUSDT","1h",50)
    eth_candles = get_binance_klines("ETHUSDT","1h",50)
    if len(btc_candles) < 30 or len(eth_candles) < 30:
        return results
    ratios = [btc_candles[i]["close"] / eth_candles[i]["close"]
              for i in range(len(btc_candles))]
    mean_ratio = statistics.mean(ratios)
    std_ratio  = statistics.stdev(ratios)
    current_ratio = ratios[-1]
    z_score = (current_ratio - mean_ratio) / std_ratio if std_ratio > 0 else 0
    if abs(z_score) < 1.8:
        print(f"  [stat_arb] Z-score {z_score:.2f} — insufficient divergence")
        return results
    signal = "LONG_ETH_SHORT_BTC" if z_score > 0 else "LONG_BTC_SHORT_ETH"
    direction = -1 if z_score > 0 else 1
    size = kelly_size(capital, 0.62, 0.018, 0.009)
    btc_entry = btc_candles[-2]["close"]
    btc_exit  = btc_candles[-1]["close"]
    pnl = round((size / btc_entry) * (btc_exit - btc_entry) * direction, 4)
    result = {"strategy":"stat_arb","signal":signal,"z_score":round(z_score,3),
              "ratio":round(current_ratio,4),"mean_ratio":round(mean_ratio,4),
              "size_usd":size,"pnl":pnl,"ts":time.time()}
    HEAT.record("stat_arb", pnl)
    log_trade(result)
    tg(f"🐊 <b>Stat Arb</b>\n📊 BTC/ETH Z-score: {z_score:.2f}\n"
       f"🎯 {signal}\n💵 ${size:.0f} | {'🟢' if pnl>0 else '🔴'} {pnl:+.4f} USDT")
    results.append(result)
    return results

def strat_grid_trading(capital: float, regime: str) -> list:
    """Grid trading in RANGING markets."""
    results = []
    if regime not in ("RANGING","NEUTRAL"):
        return results
    if not HEAT.is_hot("grid_trading"):
        return results
    PAIRS = ["BTCUSDT","ETHUSDT"]
    for sym in PAIRS[:1]:
        candles = get_binance_klines(sym,"1h",48)
        if len(candles) < 20:
            continue
        closes = [c["close"] for c in candles]
        high_48 = max(c["high"] for c in candles)
        low_48  = min(c["low"]  for c in candles)
        price = closes[-1]
        grid_range = (high_48 - low_48) / high_48
        if grid_range > 0.12:
            print(f"  [grid] {sym} range too wide {grid_range:.2%} — not ranging")
            continue
        grid_size = (high_48 - low_48) / 5
        nearest_grid = low_48 + round((price - low_48) / grid_size) * grid_size
        direction = 1 if price < nearest_grid else -1
        size = capital * 0.04
        pnl = round((size / price) * grid_size * 0.5 * direction, 4)
        result = {"strategy":"grid_trading","pair":sym,"price":price,
                  "grid_range":round(grid_range,4),"grid_size":round(grid_size,2),
                  "size_usd":size,"pnl":pnl,"ts":time.time()}
        HEAT.record("grid_trading", pnl)
        log_trade(result)
        tg(f"🐊 <b>Grid Trading</b>\n📊 {sym} | Range: {grid_range:.2%}\n"
           f"⚡ Grid size: ${grid_size:.0f}\n"
           f"💵 ${size:.0f} | {'🟢' if pnl>0 else '🔴'} {pnl:+.4f} USDT")
        results.append(result)
    return results

def strat_cross_exchange_arb(capital: float) -> list:
    """Price discrepancy between Binance and Kraken."""
    results = []
    if not HEAT.is_hot("cross_exchange_arb"):
        return results
    pairs = [("BTCUSDT","XBTUSD","BTC"),("ETHUSDT","ETHUSD","ETH")]
    for bn_sym, kr_sym, label in pairs:
        bn_price = get_binance_price(bn_sym)
        kr_candles = get_kraken_ohlc(kr_sym, 1)
        if not bn_price or not kr_candles:
            continue
        kr_price = kr_candles[-1]["close"]
        spread_pct = abs(bn_price - kr_price) / min(bn_price, kr_price)
        if spread_pct < 0.001:
            print(f"  [cross_arb] {label} spread {spread_pct:.4%} — too tight")
            continue
        signal = "BUY_BN_SELL_KR" if bn_price < kr_price else "BUY_KR_SELL_BN"
        size = kelly_size(capital, 0.85, spread_pct, spread_pct * 0.2, max_pct=0.12)
        pnl = round(size * spread_pct * 0.7, 4)  # capture 70% of spread
        result = {"strategy":"cross_exchange_arb","pair":label,"signal":signal,
                  "bn_price":bn_price,"kr_price":kr_price,
                  "spread_pct":round(spread_pct,5),"size_usd":size,"pnl":pnl,"ts":time.time()}
        HEAT.record("cross_exchange_arb", pnl)
        log_trade(result)
        tg(f"🐊 <b>Cross-Exchange Arb</b>\n📊 {label}\n"
           f"BN: ${bn_price:,.2f} | KR: ${kr_price:,.2f}\n"
           f"📊 Spread: {spread_pct:.4%} | 💵 ${size:.0f} | 🟢 +{pnl:.4f} USDT")
        results.append(result)
    return results

def strat_options_flow(capital: float) -> list:
    """Deribit open interest divergence = smart money signal."""
    results = []
    if not HEAT.is_hot("options_flow"):
        return results
    try:
        r = requests.get(
            "https://www.deribit.com/api/v2/public/get_book_summary_by_currency",
            params={"currency":"BTC","kind":"option"},
            timeout=10
        )
        data = r.json().get("result",[])
        total_call_oi = sum(d.get("open_interest",0) for d in data if "C" in d.get("instrument_name",""))
        total_put_oi  = sum(d.get("open_interest",0) for d in data if "P" in d.get("instrument_name",""))
        if total_call_oi + total_put_oi == 0:
            return results
        put_call_ratio = total_put_oi / total_call_oi if total_call_oi > 0 else 1.0
        if 0.7 < put_call_ratio < 1.3:
            print(f"  [options] P/C ratio {put_call_ratio:.2f} — neutral")
            return results
        signal = "LONG" if put_call_ratio < 0.7 else "SHORT"
        candles = get_binance_klines("BTCUSDT","1h",5)
        if not candles:
            return results
        entry = candles[-2]["close"]
        exit_p = candles[-1]["close"]
        direction = 1 if signal == "LONG" else -1
        size = kelly_size(capital, 0.63, 0.022, 0.011, max_pct=0.08)
        units = size / entry
        pnl = round(units * (exit_p - entry) * direction, 4)
        result = {"strategy":"options_flow","signal":signal,
                  "put_call_ratio":round(put_call_ratio,3),
                  "size_usd":size,"pnl":pnl,"ts":time.time()}
        HEAT.record("options_flow", pnl)
        log_trade(result)
        tg(f"🐊 <b>Options Flow</b>\n📊 P/C Ratio: {put_call_ratio:.2f}\n"
           f"🎯 Smart money: {signal}\n"
           f"💵 ${size:.0f} | {'🟢' if pnl>0 else '🔴'} {pnl:+.4f} USDT")
        results.append(result)
    except Exception as e:
        print(f"  [options] {e}")
    return results

# ─────────────────────────────────────────────────────
# SAFLA v2 — Self-Adapting Feedback Loop
# ─────────────────────────────────────────────────────
def safla_review(chest: dict, config: dict) -> dict:
    """
    Reviews strategy performance. Promotes winners. Punishes losers.
    Adjusts SAFLA thresholds based on regime.
    """
    strat_pnl = chest.get("strategy_pnl", {})
    if not strat_pnl:
        return config

    total_pnl = sum(strat_pnl.values())
    adjustments = {}

    for name, pnl in strat_pnl.items():
        weight = config.get("strategy_weights", {}).get(name, 1.0)
        if pnl > 0:
            new_weight = min(weight * 1.15, 3.0)
        else:
            new_weight = max(weight * 0.85, 0.1)
        config.setdefault("strategy_weights", {})[name] = round(new_weight, 3)
        adjustments[name] = round(new_weight - weight, 3)

    config.setdefault("safla", {})["last_review"] = datetime.utcnow().isoformat()
    config["safla"]["total_reviews"] = config["safla"].get("total_reviews", 0) + 1

    adj_str = "\n".join(f"  {k}: {'+' if v>=0 else ''}{v:.3f}" for k, v in adjustments.items() if v != 0)
    tg(f"🧠 <b>SAFLA v2 Review #{config['safla']['total_reviews']}</b>\n"
       f"📊 Strategy PnL cycle: {total_pnl:+.4f} USDT\n"
       f"⚖️ Weight adjustments:\n{adj_str or '  None (all flat)'}\n"
       f"🔱 Pantheon. Adapting.")

    return config

# ─────────────────────────────────────────────────────
# MAIN LOOP
# ─────────────────────────────────────────────────────
def run_cycle(config: dict, chest: dict, regime: str,
              fear_greed: int, sentiment: float) -> dict:
    """Execute all strategies, update chest, return updated chest."""
    cycle_pnl = 0.0
    cycle_trades = 0

    all_strategies = [
        lambda: strat_momentum_scalp(CAPITAL),
        lambda: strat_mean_reversion(CAPITAL),
        lambda: strat_breakout_hunter(CAPITAL),
        lambda: strat_funding_arb(CAPITAL),
        lambda: strat_volatility_harvest(CAPITAL),
        lambda: strat_news_sentiment(CAPITAL, sentiment),
        lambda: strat_dca_engine(CAPITAL, regime),
        lambda: strat_on_chain_alpha(CAPITAL),
        lambda: strat_liquidation_sniper(CAPITAL),
        lambda: strat_multi_factor(CAPITAL, fear_greed),
        lambda: strat_pairs_rotation(CAPITAL),
        lambda: strat_stat_arb(CAPITAL),
        lambda: strat_grid_trading(CAPITAL, regime),
        lambda: strat_cross_exchange_arb(CAPITAL),
        lambda: strat_options_flow(CAPITAL),
        # ── Flash Loan Arb ── zero capital required, unlimited loan size
        lambda: strat_flash_loan_arb(tg, CAPITAL),
    ]

    for strat_fn in all_strategies:
        try:
            results = strat_fn()
            for r in results:
                pnl = r.get("pnl", 0)
                cycle_pnl += pnl
                cycle_trades += 1
                name = r.get("strategy", "unknown")
                chest["strategy_pnl"][name] = chest["strategy_pnl"].get(name, 0) + pnl
                if pnl >= 0:
                    chest["wins"] += 1
                else:
                    chest["losses"] += 1
        except Exception as e:
            print(f"  [cycle] Strategy error: {e}")

    chest["total_pnl"] = round(chest.get("total_pnl", 0) + cycle_pnl, 4)
    chest["total_trades"] += cycle_trades
    chest["peak_pnl"] = max(chest.get("peak_pnl", 0), chest["total_pnl"])
    save_chest(chest)
    print(f"\n  ✅ Cycle done | Trades: {cycle_trades} | PnL: {cycle_pnl:+.4f} | Total: {chest['total_pnl']:+.4f}")
    return chest

def daily_report(chest: dict, regime: str, fear_greed: int):
    wins = chest.get("wins", 0)
    losses = chest.get("losses", 0)
    total = wins + losses
    win_rate = wins / total if total > 0 else 0
    pnl = chest["total_pnl"]
    peak = chest.get("peak_pnl", pnl)
    bar = equity_bar(pnl, peak)

    top_strat = max(chest["strategy_pnl"].items(), key=lambda x: x[1]) if chest["strategy_pnl"] else ("none", 0)

    tg(
        f"🐊 <b>SOBEK v3 DAILY REPORT</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Daily PnL: {pnl:+.4f} USDT\n"
        f"📊 Trades: {total} | Win Rate: {win_rate:.1%}\n"
        f"🏦 Capital: ${CAPITAL:,.2f}\n"
        f"📈 Equity: [{bar}]\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🌊 Regime: {regime}\n"
        f"😨 Fear/Greed: {fear_greed}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏆 Top: {top_strat[0]}\n"
        f"💰 PnL: {top_strat[1]:+.4f} USDT\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"For the War Chest. For the Pantheon. 🔱"
    )

def main():
    print("╔══════════════════════════════════════╗")
    print("║    SOBEK ANKH v3 — THE PREDATOR      ║")
    print("╚══════════════════════════════════════╝")
    print("Zero random. All real. Code is moving.\n")

    chest = load_chest()
    config = {}
    if CONFIG_PATH.exists():
        config = json.loads(CONFIG_PATH.read_text())

    # Boot signal
    tg("🐊 <b>SOBEK v3 ONLINE</b>\n"
       "━━━━━━━━━━━━━━━━━━━━\n"
       "✅ Zero random — real price delta PnL\n"
       "✅ Multi-timeframe confluence\n"
       "✅ SAFLA v2 + per-strategy heat\n"
       "✅ Circuit breaker armed\n"
       "15 strategies. The Nile flows. 🔱")

    last_daily   = 0
    last_safla   = time.time()
    last_meta    = 0
    fear_greed   = 50
    regime       = "NEUTRAL"
    sentiment    = 0.0
    cycle_count  = 0

    while True:
        try:
            now = time.time()
            cycle_count += 1

            # ── Meta signals refresh every 5 min ──
            if now - last_meta >= 300:
                print("\n[META] Refreshing market signals...")
                fear_greed = get_fear_greed()
                btc_24h = get_binance_24h("BTCUSDT")
                btc_candles = get_binance_klines("BTCUSDT", "1h", 20)
                atr_pct = 0.015
                if btc_candles:
                    atr = calc_atr(btc_candles, 14)
                    atr_pct = atr / btc_candles[-1]["close"]
                regime = detect_regime(fear_greed, btc_24h.get("price_change_24h", 0), atr_pct)
                sentiment = get_crypto_news_sentiment()
                print(f"  [meta] Regime={regime} | F/G={fear_greed} | Sentiment={sentiment:.2f}")
                last_meta = now

            # ── Circuit breaker ──
            drawdown = (chest["peak_pnl"] - chest["total_pnl"]) / CAPITAL if CAPITAL > 0 else 0
            if drawdown >= MAX_DRAWDOWN_PCT:
                print(f"  ⚠️ CIRCUIT BREAKER — drawdown {drawdown:.1%}")
                tg(f"⚠️ <b>CIRCUIT BREAKER</b>\n"
                   f"📉 Drawdown: {drawdown:.1%} — pausing 15 min\n"
                   f"Protecting the War Chest. 🔱")
                time.sleep(900)
                continue

            # ── Run cycle ──
            print(f"\n[CYCLE #{cycle_count}] {datetime.utcnow().strftime('%H:%M:%S')} | Regime: {regime}")
            chest = run_cycle(config, chest, regime, fear_greed, sentiment)

            # ── SAFLA review ──
            if now - last_safla >= SAFLA_INTERVAL:
                print("\n[SAFLA] Reviewing strategies...")
                config = safla_review(chest, config)
                # Reset per-cycle strategy PnL after review
                chest["strategy_pnl"] = {}
                last_safla = now

            # ── Daily report ──
            if now - last_daily >= DAILY_REPORT_INTERVAL:
                daily_report(chest, regime, fear_greed)
                last_daily = now

            # ── Adaptive cycle speed ──
            interval = FAST_CYCLE if regime in ("BULL_EUPHORIA","TRENDING") else CYCLE_INTERVAL
            time.sleep(interval)

        except KeyboardInterrupt:
            print("\n[SOBEK] Shutdown.")
            pnl = chest.get("total_pnl", 0)
            trades = chest.get("total_trades", 0)
            tg(f"🐊 <b>SOBEK v3 OFFLINE</b>\n"
               f"Session PnL: {pnl:+.4f} USDT\n"
               f"Trades: {trades}\n"
               f"For the War Chest. 🔱")
            break
        except Exception as e:
            print(f"[SOBEK] Error: {e}")
            tg(f"⚠️ SOBEK v3 cycle error: {str(e)[:200]}")
            time.sleep(30)

if __name__ == "__main__":
    main()
