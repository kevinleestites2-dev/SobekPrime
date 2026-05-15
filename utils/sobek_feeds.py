"""
sobek_feeds.py — Pantheon Data Layer
Free, no-key public APIs wired for Sobek Ankh.

Feeds:
  - CryptoCompare: latest crypto news headlines + sentiment scoring
  - Mempool.space: BTC fee rates (sat/vB), mempool size in MB, congestion level
  - CoinGecko OHLCV: BTC volume analysis for regime confirmation
"""

import requests
import time

# ─────────────────────────────────────────
# CRYPTOCOMPARE — News Headlines
# No API key needed for basic news endpoint
# ─────────────────────────────────────────

CRYPTO_NEWS_URL = "https://min-api.cryptocompare.com/data/v2/news/?lang=EN&sortOrder=latest"

BULLISH_WORDS = [
    "surge", "rally", "breakout", "bullish", "adoption", "record", "high",
    "gains", "pump", "institutional", "approve", "etf", "upgrade", "launch",
    "partnership", "integration", "growth", "soar", "moon", "ath"
]
BEARISH_WORDS = [
    "crash", "dump", "ban", "hack", "bearish", "lawsuit", "regulation",
    "collapse", "fall", "plunge", "fear", "scam", "fraud", "warning",
    "decline", "sell", "drop", "loss", "liquidation", "fud"
]

def fetch_crypto_news(limit: int = 20) -> dict:
    """
    Fetch latest crypto news from CryptoCompare.
    Returns sentiment score, top headlines, and signal direction.
    Score: +1.0 = fully bullish, -1.0 = fully bearish, 0 = neutral
    """
    try:
        r = requests.get(CRYPTO_NEWS_URL, timeout=10)
        articles = r.json().get("Data", [])[:limit]

        bull_count = 0
        bear_count = 0
        headlines = []

        for article in articles:
            title = article.get("title", "").lower()
            body = article.get("body", "").lower()[:300]
            combined = title + " " + body

            b = sum(1 for w in BULLISH_WORDS if w in combined)
            bear = sum(1 for w in BEARISH_WORDS if w in combined)
            bull_count += b
            bear_count += bear
            headlines.append(article.get("title", ""))

        total = bull_count + bear_count
        if total == 0:
            score = 0.0
        else:
            score = (bull_count - bear_count) / total  # -1 to +1

        if score > 0.2:
            signal = "BULLISH"
        elif score < -0.2:
            signal = "BEARISH"
        else:
            signal = "NEUTRAL"

        return {
            "score": round(score, 3),
            "signal": signal,
            "bull_hits": bull_count,
            "bear_hits": bear_count,
            "headlines": headlines[:5],
            "article_count": len(articles)
        }

    except Exception as e:
        print(f"  [feeds] CryptoCompare error: {e}")
        return {"score": 0.0, "signal": "NEUTRAL", "headlines": [], "bull_hits": 0, "bear_hits": 0}


# ─────────────────────────────────────────
# MEMPOOL.SPACE — BTC Fee Rates & Congestion
# No API key needed
# ─────────────────────────────────────────

MEMPOOL_FEES_URL = "https://mempool.space/api/v1/fees/recommended"
MEMPOOL_STATS_URL = "https://mempool.space/api/mempool"

def fetch_mempool_fees() -> dict:
    """
    Returns BTC fee rates in sat/vB and congestion level.
    Fee pressure rising = on-chain demand signal.
    """
    try:
        fees_r = requests.get(MEMPOOL_FEES_URL, timeout=8)
        fees = fees_r.json()

        stats_r = requests.get(MEMPOOL_STATS_URL, timeout=8)
        stats = stats_r.json()

        fastest = fees.get("fastestFee", 0)
        half_hour = fees.get("halfHourFee", 0)
        hour = fees.get("hourFee", 0)
        economy = fees.get("economyFee", 0)
        minimum = fees.get("minimumFee", 0)

        mempool_bytes = stats.get("vsize", 0)
        mempool_mb = round(mempool_bytes / 1_000_000, 2)
        tx_count = stats.get("count", 0)

        # Congestion levels
        if fastest > 100:
            congestion = "EXTREME"
        elif fastest > 50:
            congestion = "HIGH"
        elif fastest > 20:
            congestion = "MODERATE"
        elif fastest > 5:
            congestion = "LOW"
        else:
            congestion = "VERY_LOW"

        # Fee pressure signal
        if fastest > 50 and mempool_mb > 100:
            fee_signal = "DEMAND_SURGE"
        elif fastest > 20 and mempool_mb > 50:
            fee_signal = "RISING_DEMAND"
        elif fastest < 3 and mempool_mb < 5:
            fee_signal = "NETWORK_IDLE"
        else:
            fee_signal = "NORMAL"

        return {
            "fastest_fee": fastest,
            "half_hour_fee": half_hour,
            "hour_fee": hour,
            "economy_fee": economy,
            "minimum_fee": minimum,
            "mempool_mb": mempool_mb,
            "mempool_tx_count": tx_count,
            "congestion": congestion,
            "fee_signal": fee_signal
        }

    except Exception as e:
        print(f"  [feeds] Mempool.space error: {e}")
        return {
            "fastest_fee": 0, "mempool_mb": 0, "mempool_tx_count": 0,
            "congestion": "UNKNOWN", "fee_signal": "NORMAL"
        }


# ─────────────────────────────────────────
# COINGECKO — BTC Volume Analysis
# No API key needed (free tier)
# ─────────────────────────────────────────

COINGECKO_VOLUME_URL = (
    "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart"
    "?vs_currency=usd&days=7&interval=daily"
)

def fetch_btc_volume() -> dict:
    """
    Returns BTC 7-day volume trend and volume signal.
    Volume expanding on uptrend = bull confirmation.
    Volume expanding on downtrend = bear confirmation.
    """
    try:
        r = requests.get(COINGECKO_VOLUME_URL, timeout=10)
        data = r.json()

        prices = [p[1] for p in data.get("prices", [])]
        volumes = [v[1] for v in data.get("total_volumes", [])]

        if len(volumes) < 3:
            return {"volume_signal": "INSUFFICIENT_DATA"}

        avg_volume = sum(volumes) / len(volumes)
        latest_volume = volumes[-1]
        prev_volume = volumes[-2]

        price_trend = "UP" if prices[-1] > prices[-3] else "DOWN"
        volume_trend = "EXPANDING" if latest_volume > prev_volume else "CONTRACTING"

        volume_ratio = latest_volume / avg_volume if avg_volume > 0 else 1.0

        if price_trend == "UP" and volume_trend == "EXPANDING":
            volume_signal = "BULL_CONFIRM"
        elif price_trend == "DOWN" and volume_trend == "EXPANDING":
            volume_signal = "BEAR_CONFIRM"
        elif price_trend == "UP" and volume_trend == "CONTRACTING":
            volume_signal = "WEAK_RALLY"
        elif price_trend == "DOWN" and volume_trend == "CONTRACTING":
            volume_signal = "WEAK_SELLOFF"
        else:
            volume_signal = "NEUTRAL"

        return {
            "avg_volume_7d": round(avg_volume, 0),
            "latest_volume": round(latest_volume, 0),
            "volume_ratio": round(volume_ratio, 3),
            "price_trend": price_trend,
            "volume_trend": volume_trend,
            "volume_signal": volume_signal
        }

    except Exception as e:
        print(f"  [feeds] CoinGecko volume error: {e}")
        return {"volume_signal": "NEUTRAL"}


# ─────────────────────────────────────────
# COMBINED SIGNAL SNAPSHOT
# ─────────────────────────────────────────

def get_full_signal_snapshot() -> dict:
    """
    One call to rule them all.
    Returns unified dict with all three feeds.
    """
    print("  [feeds] Pulling CryptoCompare news...")
    news = fetch_crypto_news()

    print("  [feeds] Pulling Mempool.space fees...")
    mempool = fetch_mempool_fees()

    print("  [feeds] Pulling CoinGecko volume...")
    volume = fetch_btc_volume()

    return {
        "news": news,
        "mempool": mempool,
        "volume": volume,
        "timestamp": time.time()
    }


if __name__ == "__main__":
    print("🐊 Sobek Feeds — Test Run\n")
    snap = get_full_signal_snapshot()

    print(f"\n📰 News Sentiment: {snap['news']['signal']} (score: {snap['news']['score']:+.3f})")
    print(f"   Bull hits: {snap['news']['bull_hits']} | Bear hits: {snap['news']['bear_hits']}")
    print(f"   Top headline: {snap['news']['headlines'][0] if snap['news']['headlines'] else 'N/A'}")

    print(f"\n⛓️  Mempool: {snap['mempool']['congestion']} | Signal: {snap['mempool']['fee_signal']}")
    print(f"   Fastest fee: {snap['mempool']['fastest_fee']} sat/vB")
    print(f"   Mempool size: {snap['mempool']['mempool_mb']} MB ({snap['mempool']['mempool_tx_count']:,} txs)")

    print(f"\n📊 Volume: {snap['volume']['volume_signal']}")
    print(f"   Price trend: {snap['volume']['price_trend']} | Volume: {snap['volume']['volume_trend']}")
    print(f"   Volume ratio vs 7d avg: {snap['volume'].get('volume_ratio', 'N/A')}x")
