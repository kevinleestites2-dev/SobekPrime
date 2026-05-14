"""
Sobek Ankh — Strategy: Momentum Scalping
Fast momentum detection on 1m/5m candles. Rides breakouts, cuts fast.
"""
import random

def run(capital: float) -> list:
    pairs = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT"]
    results = []
    for pair in pairs:
        momentum = random.uniform(-0.03, 0.03)
        if abs(momentum) > 0.015:
            direction = "LONG" if momentum > 0 else "SHORT"
            pnl = round(capital * 0.01 * abs(momentum) * (1 if momentum > 0 else -1), 4)
            results.append({"strategy": "momentum_scalp", "pair": pair, "direction": direction, "pnl": pnl, "simulate": True})
    return results
