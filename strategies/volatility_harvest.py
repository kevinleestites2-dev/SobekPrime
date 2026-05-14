"""
Sobek Ankh — Strategy: Volatility Harvest
Sells volatility when IV is elevated. Collects theta decay, hedges delta.
"""
import random

def run(capital: float) -> list:
    iv = random.uniform(0.3, 1.2)
    results = []
    if iv > 0.7:
        premium = round(capital * 0.02 * (iv - 0.5), 4)
        pnl = round(premium * random.uniform(0.4, 0.9), 4)
        results.append({"strategy": "volatility_harvest", "iv": round(iv,2), "premium_collected": premium, "pnl": pnl, "simulate": True})
    return results
