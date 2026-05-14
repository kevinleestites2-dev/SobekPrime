"""
Sobek Ankh — Strategy: DCA Engine
Dollar-cost averaging into dips. Layered entries, averaged cost basis.
"""
import random

def run(capital: float) -> list:
    pairs = ["BTC/USDT", "ETH/USDT"]
    results = []
    layer_size = capital * 0.05
    for pair in pairs:
        dip_pct = random.uniform(-0.08, 0.02)
        if dip_pct < -0.03:
            layers = min(int(abs(dip_pct) / 0.01), 6)
            pnl = round(layer_size * layers * random.uniform(-0.005, 0.02), 4)
            results.append({"strategy": "dca_engine", "pair": pair, "dip_pct": round(dip_pct*100,2), "layers": layers, "deployed": round(layer_size*layers,2), "pnl": pnl, "simulate": True})
    return results
