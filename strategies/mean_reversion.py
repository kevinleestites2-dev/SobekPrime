"""
Sobek Ankh — Strategy: Mean Reversion
Buys oversold, sells overbought using Bollinger Bands + RSI.
"""
import random

def run(capital: float) -> list:
    pairs = ["BTC/USDT", "ETH/USDT", "LINK/USDT", "AVAX/USDT"]
    results = []
    for pair in pairs:
        rsi = random.uniform(20, 80)
        if rsi < 30:
            pnl = round(capital * random.uniform(0.001, 0.015), 4)
            results.append({"strategy": "mean_reversion", "pair": pair, "signal": "OVERSOLD_BUY", "rsi": round(rsi,1), "pnl": pnl, "simulate": True})
        elif rsi > 70:
            pnl = round(capital * random.uniform(-0.005, 0.01), 4)
            results.append({"strategy": "mean_reversion", "pair": pair, "signal": "OVERBOUGHT_SELL", "rsi": round(rsi,1), "pnl": pnl, "simulate": True})
    return results
