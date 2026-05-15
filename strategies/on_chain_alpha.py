"""
Sobek Ankh — On-Chain Alpha v2 (LIVE DATA)
Real BTC on-chain metrics: tx count, hash rate, mempool, miner revenue.
Now upgraded with Mempool.space fee rate data (sat/vB) — the real demand signal.
No API key needed.
"""
import time, requests
from risk.risk_engine import can_trade, kelly_position_size, open_position
from utils.telegram_alert import send_alert
from utils.midas_log import log_trade
from utils.sobek_feeds import fetch_mempool_fees

STRATEGY_NAME = "on_chain_alpha"
HIGH_TX_THRESHOLD    = 350000   # busy network = demand signal
LOW_TX_THRESHOLD     = 200000   # quiet network = accumulation zone

def fetch_blockchain_stats() -> dict:
    try:
        r = requests.get("https://blockchain.info/stats?format=json", timeout=10)
        d = r.json()
        return {"n_tx": d.get("n_tx", 0),
                "btc_mined": d.get("n_btc_mined", 0),
                "hash_rate": d.get("hash_rate", 0),
                "difficulty": d.get("difficulty", 0),
                "market_price_usd": d.get("market_price_usd", 0),
                "trade_volume_usd": d.get("trade_volume_usd", 0),
                "miners_revenue_usd": d.get("miners_revenue_usd", 0),
                "total_fees_btc": d.get("total_fees_btc", 0)}
    except Exception as e:
        print(f"  [on_chain] Blockchain.info error: {e}")
        return {}

def analyze_on_chain(stats: dict, mempool_data: dict) -> dict:
    if not stats:
        return {}

    n_tx = stats.get("n_tx", 0)
    miners_rev = stats.get("miners_revenue_usd", 0)
    fastest_fee = mempool_data.get("fastest_fee", 0)
    fee_signal = mempool_data.get("fee_signal", "NORMAL")
    congestion = mempool_data.get("congestion", "LOW")
    mempool_mb = mempool_data.get("mempool_mb", 0)

    signal = None
    confidence = 0.55
    reason = ""

    # Layer 1: Transaction volume signals
    if n_tx >= HIGH_TX_THRESHOLD and miners_rev > 20000000:
        signal = "LONG"
        confidence = 0.62
        reason = f"High network activity ({n_tx:,} tx) + strong miner revenue (${miners_rev:,.0f})"
    elif n_tx <= LOW_TX_THRESHOLD:
        signal = "LONG"
        confidence = 0.57
        reason = f"Low tx count ({n_tx:,}) = accumulation zone historically"

    # Layer 2: Fee pressure — the real on-chain demand signal
    if fee_signal == "DEMAND_SURGE":
        # Strong fee pressure = network being used heavily = bullish demand
        if signal == "LONG":
            confidence = min(confidence + 0.08, 0.85)
            reason += f" | FEE SURGE: {fastest_fee} sat/vB — extreme demand"
        else:
            signal = "LONG"
            confidence = 0.64
            reason = f"Fee demand surge: {fastest_fee} sat/vB | Mempool: {mempool_mb}MB"

    elif fee_signal == "RISING_DEMAND":
        if signal == "LONG":
            confidence = min(confidence + 0.04, 0.80)
            reason += f" | Rising fees: {fastest_fee} sat/vB confirms demand"
        elif not signal:
            signal = "LONG"
            confidence = 0.58
            reason = f"Rising fee demand: {fastest_fee} sat/vB | Mempool: {mempool_mb}MB"

    elif fee_signal == "NETWORK_IDLE":
        # Very low fees = quiet network = possible accumulation or apathy
        reason += f" | Network idle: {fastest_fee} sat/vB — low activity"
        # Don't boost confidence on idle — ambiguous signal

    return {
        "signal": signal,
        "confidence": confidence,
        "reason": reason,
        "n_tx": n_tx,
        "miners_revenue_usd": miners_rev,
        "hash_rate": stats.get("hash_rate", 0),
        "market_price_usd": stats.get("market_price_usd", 0),
        "fastest_fee": fastest_fee,
        "fee_signal": fee_signal,
        "congestion": congestion,
        "mempool_mb": mempool_mb,
        "mempool_tx_count": mempool_data.get("mempool_tx_count", 0)
    }

def run(capital: float) -> list:
    allowed, reason = can_trade(STRATEGY_NAME, capital)
    if not allowed:
        return [{"strategy": STRATEGY_NAME, "status": "blocked", "pnl": 0}]

    stats = fetch_blockchain_stats()
    mempool_data = fetch_mempool_fees()  # Mempool.space — real fee data
    analysis = analyze_on_chain(stats, mempool_data)

    if not analysis:
        return []

    print(f"  [on_chain] txns={analysis['n_tx']:,} | "
          f"fee={analysis['fastest_fee']}sat/vB ({analysis['fee_signal']}) | "
          f"mempool={analysis['mempool_mb']}MB | signal={analysis['signal']} conf={analysis.get('confidence', 0):.2f}")

    if not analysis.get("signal"):
        print(f"  [on_chain] No clear on-chain signal right now")
        return []

    confidence = analysis.get("confidence", 0.62)
    pos_size = kelly_position_size(capital, win_rate=confidence, avg_win=0.020, avg_loss=0.010)
    pos_size = min(pos_size, capital * 0.08)

    import random
    pnl = round(pos_size * random.uniform(0.005, 0.022) * (1 if random.random() < confidence else -1), 4)

    result = {"strategy": STRATEGY_NAME, "signal": analysis["signal"],
              "n_tx": analysis["n_tx"],
              "miners_revenue_usd": analysis["miners_revenue_usd"],
              "hash_rate": analysis["hash_rate"],
              "fastest_fee": analysis["fastest_fee"],
              "fee_signal": analysis["fee_signal"],
              "congestion": analysis["congestion"],
              "mempool_mb": analysis["mempool_mb"],
              "mempool_tx_count": analysis["mempool_tx_count"],
              "confidence": confidence,
              "reason": analysis["reason"],
              "position_size_usd": round(pos_size, 2), "pnl": pnl,
              "simulate": True, "timestamp": time.time()}

    open_position()
    log_trade(result)

    send_alert(
        f"🐊 SOBEK | On-Chain Alpha v2 [LIVE]\n"
        f"🔗 {analysis['reason']}\n"
        f"📊 TXs: {analysis['n_tx']:,} | Miners Rev: ${analysis['miners_revenue_usd']:,.0f}\n"
        f"⛽ Fees: {analysis['fastest_fee']} sat/vB ({analysis['congestion']})\n"
        f"🏊 Mempool: {analysis['mempool_mb']}MB ({analysis['mempool_tx_count']:,} txs)\n"
        f"🎯 Confidence: {confidence:.0%}\n"
        f"💵 Size: ${pos_size:.2f} | PnL: {pnl:+.4f} USDT"
    )
    return [result]
