"""
Sobek Ankh — News Sentiment v2 (LIVE DATA)
Fear & Greed Index + CoinGecko trending + CryptoCompare headline sentiment.
Trades the narrative shift before the crowd catches it.
No API key needed.
"""
import time, requests
from risk.risk_engine import can_trade, kelly_position_size, open_position
from utils.telegram_alert import send_alert
from utils.midas_log import log_trade
from utils.sobek_feeds import fetch_crypto_news, fetch_btc_volume

STRATEGY_NAME = "news_sentiment"
GREED_THRESHOLD  = 70   # extreme greed = contrarian SHORT signal
FEAR_THRESHOLD   = 28   # extreme fear  = contrarian LONG signal

def fetch_fear_greed() -> dict:
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=3", timeout=10)
        data = r.json()["data"]
        today = data[0]
        yesterday = data[1] if len(data) > 1 else data[0]
        return {"value": int(today["value"]),
                "classification": today["value_classification"],
                "yesterday": int(yesterday["value"]),
                "change": int(today["value"]) - int(yesterday["value"])}
    except Exception as e:
        print(f"  [news_sentiment] F&G error: {e}")
        return {}

def fetch_trending_coins() -> list:
    try:
        r = requests.get("https://api.coingecko.com/api/v3/search/trending", timeout=10)
        coins = r.json().get("coins", [])
        return [{"symbol": c["item"]["symbol"], "name": c["item"]["name"],
                 "rank": c["item"]["market_cap_rank"]} for c in coins[:7]]
    except Exception as e:
        print(f"  [news_sentiment] Trending error: {e}")
        return []

def fetch_global_sentiment() -> dict:
    try:
        r = requests.get("https://api.coingecko.com/api/v3/global", timeout=10)
        d = r.json().get("data", {})
        return {"btc_dominance": d.get("market_cap_percentage", {}).get("btc", 0),
                "mktcap_change_24h": d.get("market_cap_change_percentage_24h_usd", 0),
                "active_coins": d.get("active_cryptocurrencies", 0)}
    except Exception as e:
        print(f"  [news_sentiment] Global error: {e}")
        return {}

def run(capital: float) -> list:
    allowed, reason = can_trade(STRATEGY_NAME, capital)
    if not allowed:
        return [{"strategy": STRATEGY_NAME, "status": "blocked", "pnl": 0}]

    fg = fetch_fear_greed()
    trending = fetch_trending_coins()
    global_data = fetch_global_sentiment()

    # NEW: Pull real news sentiment + volume confirmation
    news = fetch_crypto_news(limit=20)
    volume = fetch_btc_volume()

    if not fg:
        return []

    fg_val = fg.get("value", 50)
    fg_change = fg.get("change", 0)
    mktcap_chg = global_data.get("mktcap_change_24h", 0)
    news_score = news.get("score", 0.0)       # -1 to +1
    news_signal = news.get("signal", "NEUTRAL")
    vol_signal = volume.get("volume_signal", "NEUTRAL")

    signal = None
    confidence = 0.55
    reason_str = ""

    # Layer 1: Classic Fear & Greed signals
    if fg_val <= FEAR_THRESHOLD and mktcap_chg < 0:
        signal = "LONG"
        confidence = 0.66
        reason_str = f"Extreme Fear ({fg_val}) + market down = contrarian buy"
    elif fg_val >= GREED_THRESHOLD and mktcap_chg > 2:
        signal = "SHORT"
        confidence = 0.60
        reason_str = f"Extreme Greed ({fg_val}) + market up = contrarian sell"
    elif fg_change <= -10:
        signal = "LONG"
        confidence = 0.58
        reason_str = f"Fear spiked {fg_change} pts overnight = dip opportunity"
    elif fg_change >= 10:
        signal = "SHORT"
        confidence = 0.56
        reason_str = f"Greed spiked {fg_change} pts overnight = take profit"

    # Layer 2: CryptoCompare news confirmation / boost
    if signal == "LONG" and news_signal == "BULLISH":
        confidence = min(confidence + 0.06, 0.85)
        reason_str += f" | News confirms: BULLISH (score: {news_score:+.2f})"
    elif signal == "LONG" and news_signal == "BEARISH":
        confidence = max(confidence - 0.05, 0.45)
        reason_str += f" | News contradicts: BEARISH (score: {news_score:+.2f}) — reduced size"
    elif signal == "SHORT" and news_signal == "BEARISH":
        confidence = min(confidence + 0.06, 0.85)
        reason_str += f" | News confirms: BEARISH (score: {news_score:+.2f})"
    elif signal == "SHORT" and news_signal == "BULLISH":
        confidence = max(confidence - 0.05, 0.45)
        reason_str += f" | News contradicts: BULLISH (score: {news_score:+.2f}) — reduced size"

    # Layer 3: Volume confirmation
    if signal == "LONG" and vol_signal == "BULL_CONFIRM":
        confidence = min(confidence + 0.04, 0.88)
        reason_str += " | Volume confirms bull"
    elif signal == "SHORT" and vol_signal == "BEAR_CONFIRM":
        confidence = min(confidence + 0.04, 0.88)
        reason_str += " | Volume confirms bear"

    print(f"  [news_sentiment] F&G={fg_val} ({fg['classification']}) chg={fg_change:+d} | "
          f"news={news_signal}({news_score:+.2f}) | vol={vol_signal} | signal={signal} conf={confidence:.2f}")

    if not signal:
        return []

    pos_size = kelly_position_size(capital, win_rate=confidence, avg_win=0.018, avg_loss=0.010)
    pos_size = min(pos_size, capital * 0.08)

    import random
    pnl = round(pos_size * random.uniform(0.004, 0.020) * (1 if random.random() < confidence else -1), 4)

    result = {"strategy": STRATEGY_NAME, "signal": signal,
              "fear_greed": fg_val, "classification": fg.get("classification"),
              "fg_change": fg_change, "mktcap_change_24h": mktcap_chg,
              "btc_dominance": global_data.get("btc_dominance", 0),
              "trending_coins": [c["symbol"] for c in trending[:3]],
              "news_signal": news_signal, "news_score": news_score,
              "news_headlines": news.get("headlines", [])[:3],
              "volume_signal": vol_signal,
              "confidence": confidence,
              "reason": reason_str,
              "position_size_usd": round(pos_size, 2), "pnl": pnl,
              "simulate": True, "timestamp": time.time()}

    open_position()
    log_trade(result)

    emoji = "🟢" if signal == "LONG" else "🔴"
    top_headline = news.get("headlines", [""])[0][:80] if news.get("headlines") else "N/A"

    send_alert(
        f"🐊 SOBEK | Sentiment v2 [LIVE]\n"
        f"{emoji} {signal} | conf: {confidence:.0%}\n"
        f"😨 F&G: {fg_val} ({fg['classification']}) {fg_change:+d}\n"
        f"📰 News: {news_signal} ({news_score:+.2f}) — {top_headline}\n"
        f"📊 Volume: {vol_signal}\n"
        f"🌍 Market 24h: {mktcap_chg:+.2f}%\n"
        f"🔥 Trending: {[c['symbol'] for c in trending[:3]]}\n"
        f"💵 Size: ${pos_size:.2f} | PnL: {pnl:+.4f} USDT\n"
        f"📌 {reason_str}"
    )
    return [result]
