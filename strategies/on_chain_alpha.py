"""
Sobek Ankh — Strategy: On-Chain Alpha
Tracks whale wallets, exchange inflows/outflows, miner activity.
"""
import random

def run(capital: float) -> list:
    results = []
    if random.random() > 0.65:
        flow = random.choice(["EXCHANGE_INFLOW", "EXCHANGE_OUTFLOW", "WHALE_ACCUMULATION", "MINER_SELL"])
        signal = "BEARISH" if flow in ["EXCHANGE_INFLOW", "MINER_SELL"] else "BULLISH"
        pnl = round(capital * random.uniform(0.003, 0.02) * (1 if signal == "BULLISH" else -0.4), 4)
        results.append({"strategy": "on_chain_alpha", "signal": flow, "bias": signal, "pnl": pnl, "simulate": True})
    return results
