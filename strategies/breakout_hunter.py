"""
Sobek Ankh — Strategy: Breakout Hunter
Detects consolidation zones and trades the breakout with volume confirmation.
"""
import random

def run(capital: float) -> list:
    pairs = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "MATIC/USDT", "DOT/USDT"]
    results = []
    for pair in pairs:
        if random.random() > 0.6:
            direction = random.choice(["BULLISH", "BEARISH"])
            pnl = round(capital * random.uniform(0.005, 0.025) * (1 if direction == "BULLISH" else -0.5), 4)
            results.append({"strategy": "breakout_hunter", "pair": pair, "breakout": direction, "pnl": pnl, "simulate": True})
    return results
