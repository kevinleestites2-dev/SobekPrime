"""
Sobek Ankh — Strategy: Pairs Rotation
Rotates capital into top-performing assets. Sell laggards, buy leaders.
"""
import random

UNIVERSE = ["BTC","ETH","SOL","BNB","AVAX","DOT","LINK","MATIC","ATOM","ADA"]

def run(capital: float) -> list:
    performances = {coin: random.uniform(-0.05, 0.05) for coin in UNIVERSE}
    sorted_coins = sorted(performances.items(), key=lambda x: x[1], reverse=True)
    leaders = sorted_coins[:3]
    laggards = sorted_coins[-3:]
    pnl = round(sum(v for _,v in leaders) * capital * 0.1, 4)
    return [{"strategy": "pairs_rotation", "buy": [c for c,_ in leaders], "sell": [c for c,_ in laggards], "pnl": pnl, "simulate": True}]
