"""
Sobek Ankh — Strategy: News Sentiment
Monitors crypto news sentiment. Trades the narrative before the crowd.
"""
import random

SOURCES = ["CoinDesk", "CryptoSlate", "Decrypt", "The Block"]

def run(capital: float) -> list:
    results = []
    sentiment = random.uniform(-1.0, 1.0)
    if abs(sentiment) > 0.6:
        signal = "BULLISH" if sentiment > 0 else "BEARISH"
        pair = random.choice(["BTC/USDT", "ETH/USDT", "SOL/USDT"])
        pnl = round(capital * 0.005 * abs(sentiment) * (1 if sentiment > 0 else -0.3), 4)
        results.append({"strategy": "news_sentiment", "source": random.choice(SOURCES), "sentiment": round(sentiment,2), "signal": signal, "pair": pair, "pnl": pnl, "simulate": True})
    return results
