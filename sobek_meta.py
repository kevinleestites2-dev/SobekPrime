"""
sobek_meta.py — The Watcher Above The Nile
Sobek Ankh v2 | Meta Layer

Reads market regime. Scores conviction. Rewrites sobek_config.json.
Sobek never knows this exists. He just wakes up and the config is better.

"The hawk sees the whole river. The crocodile sees only what is in front of him.
 You need both." — Pantheon
"""

import json
import time
import requests
from datetime import datetime
from pathlib import Path

CONFIG_PATH = Path("sobek_config.json")
MEMORY_DIR = Path("memory")
MEMORY_DIR.mkdir(exist_ok=True)

# ─────────────────────────────────────────
# MARKET DATA (all free, no keys)
# ─────────────────────────────────────────

def get_fear_greed() -> dict:
    """Alternative.me Fear & Greed Index"""
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=7", timeout=8)
        data = r.json()["data"]
        current = int(data[0]["value"])
        week_avg = sum(int(d["value"]) for d in data) / len(data)
        return {"current": current, "week_avg": week_avg, "label": data[0]["value_classification"]}
    except Exception:
        return {"current": 50, "week_avg": 50, "label": "Neutral"}


def get_btc_data() -> dict:
    """CoinGecko — BTC price, 7d trend, market cap"""
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart"
            "?vs_currency=usd&days=7&interval=daily",
            timeout=8
        )
        prices = [p[1] for p in r.json()["prices"]]
        trend_7d = (prices[-1] - prices[0]) / prices[0]
        # Realized vol — std of daily returns
        returns = [(prices[i] - prices[i-1]) / prices[i-1] for i in range(1, len(prices))]
        import statistics
        vol = statistics.stdev(returns) if len(returns) > 1 else 0.02
        return {
            "price": prices[-1],
            "trend_7d": trend_7d,
            "realized_vol": vol,
            "prices": prices
        }
    except Exception:
        return {"price": 0, "trend_7d": 0, "realized_vol": 0.02, "prices": []}


def get_funding_rate() -> float:
    """OKX BTC-USDT-SWAP funding rate"""
    try:
        r = requests.get(
            "https://www.okx.com/api/v5/public/funding-rate?instId=BTC-USDT-SWAP",
            timeout=8
        )
        return float(r.json()["data"][0]["fundingRate"])
    except Exception:
        return 0.0


def get_btc_dominance() -> float:
    """CoinGecko global market dominance"""
    try:
        r = requests.get("https://api.coingecko.com/api/v3/global", timeout=8)
        return r.json()["data"]["market_cap_percentage"]["btc"]
    except Exception:
        return 50.0


# ─────────────────────────────────────────
# REGIME DETECTION
# ─────────────────────────────────────────

def detect_regime(fg: dict, btc: dict, funding: float) -> tuple[str, float]:
    """
    Returns (regime_name, confidence_0_to_1)
    """
    vol   = btc["realized_vol"]
    trend = btc["trend_7d"]
    fear  = fg["current"]
    fg_trend = fg["current"] - fg["week_avg"]  # positive = getting greedy

    scores = {}

    # CRISIS — high vol + extreme fear
    crisis_score = 0.0
    if vol > 0.06: crisis_score += 0.4
    if fear < 25:  crisis_score += 0.4
    if trend < -0.10: crisis_score += 0.2
    scores["CRISIS"] = crisis_score

    # RANGING — low vol + neutral sentiment + no clear trend
    ranging_score = 0.0
    if vol < 0.02: ranging_score += 0.4
    if 35 < fear < 65: ranging_score += 0.3
    if abs(trend) < 0.03: ranging_score += 0.3
    scores["RANGING"] = ranging_score

    # BULL_EUPHORIA — uptrend + high funding + greed
    bull_score = 0.0
    if trend > 0.05: bull_score += 0.35
    if funding > 0.0003: bull_score += 0.35
    if fear > 70: bull_score += 0.3
    scores["BULL_EUPHORIA"] = bull_score

    # BEAR_FEAR — downtrend + low funding + fear
    bear_score = 0.0
    if trend < -0.05: bear_score += 0.35
    if funding < 0.0: bear_score += 0.25
    if fear < 40: bear_score += 0.2
    if fg_trend < -5: bear_score += 0.2
    scores["BEAR_FEAR"] = bear_score

    # NEUTRAL — nothing dominant
    scores["NEUTRAL"] = 0.3

    best_regime = max(scores, key=scores.get)
    confidence  = scores[best_regime]

    # If nothing scores above 0.45 — it's genuinely neutral
    if confidence < 0.45:
        return "NEUTRAL", 0.5

    return best_regime, min(confidence, 1.0)


# ─────────────────────────────────────────
# CONVICTION SCORING
# ─────────────────────────────────────────

def score_conviction(strategy_name: str, config: dict, regime: str) -> float:
    """
    Cross-validates object vs meta signal type.
    Returns conviction multiplier for position sizing.
    """
    strategy_type = config["strategy_type"].get(strategy_name, "object")
    thresholds = config["conviction_thresholds"]

    # Count how many meta strategies are active/weighted in this regime
    regime_weights = config["regime_weights"].get(regime, {})
    meta_strategies = [k for k, v in config["strategy_type"].items() if v == "meta"]
    active_meta = sum(1 for s in meta_strategies if regime_weights.get(s, 1.0) >= 1.0)
    total_meta = len(meta_strategies)
    meta_agreement = active_meta / total_meta if total_meta > 0 else 0.5

    object_strategies = [k for k, v in config["strategy_type"].items() if v == "object"]
    active_object = sum(1 for s in object_strategies if regime_weights.get(s, 1.0) >= 1.0)
    total_object = len(object_strategies)
    object_agreement = active_object / total_object if total_object > 0 else 0.5

    both_agree = meta_agreement > 0.6 and object_agreement > 0.6
    all_agree  = meta_agreement > 0.75 and object_agreement > 0.75
    conflict   = (meta_agreement > 0.6) != (object_agreement > 0.6)

    if all_agree:
        return thresholds["all_layers_agree"]
    if both_agree:
        return thresholds["object_meta_agree"]
    if conflict:
        return thresholds["conflict"]
    if strategy_type == "meta":
        return thresholds["meta_only"]
    return thresholds["object_only"]


# ─────────────────────────────────────────
# CONFIG WRITER
# ─────────────────────────────────────────

def apply_regime_to_config(config: dict, regime: str, confidence: float) -> dict:
    """Blend regime weights with current weights based on confidence."""
    regime_overrides = config["regime_weights"].get(regime, {})

    for strategy in config["strategy_weights"]:
        if strategy in regime_overrides:
            target = regime_overrides[strategy]
            current = config["strategy_weights"][strategy]
            # Blend — don't slam full weight instantly
            blended = current + (target - current) * confidence * 0.5
            config["strategy_weights"][strategy] = round(
                max(config["safla"]["min_weight"],
                    min(config["safla"]["max_weight"], blended)), 3)

    config["regime"] = regime
    config["regime_confidence"] = round(confidence, 3)
    config["generated_at"] = datetime.utcnow().isoformat()
    return config


def save_regime_history(regime: str, confidence: float, fg: dict, btc: dict, funding: float):
    """Append to regime history — this becomes Sobek's memory."""
    history_file = MEMORY_DIR / "regime_history.json"
    history = []
    if history_file.exists():
        try:
            history = json.loads(history_file.read_text())
        except Exception:
            history = []

    entry = {
        "ts": datetime.utcnow().isoformat(),
        "regime": regime,
        "confidence": round(confidence, 3),
        "fear_greed": fg["current"],
        "btc_trend_7d": round(btc["trend_7d"], 4),
        "realized_vol": round(btc["realized_vol"], 4),
        "funding_rate": round(funding, 6)
    }
    history.append(entry)

    # Keep last 500 entries
    history = history[-500:]
    history_file.write_text(json.dumps(history, indent=2))


# ─────────────────────────────────────────
# MAIN WATCHER
# ─────────────────────────────────────────

def run_meta_watcher(once: bool = False):
    """
    Main loop. Runs every 10 minutes.
    Detects regime. Updates config. Sobek reads it automatically.
    """
    print("🔱 Sobek Meta Watcher — ONLINE")
    print("   Watching the river from above...\n")

    while True:
        try:
            print(f"[{datetime.utcnow().strftime('%H:%M:%S')}] Scanning market regime...")

            # Gather signals
            fg     = get_fear_greed()
            btc    = get_btc_data()
            funding = get_funding_rate()

            # Detect regime
            regime, confidence = detect_regime(fg, btc, funding)

            print(f"  Fear & Greed : {fg['current']} ({fg['label']})")
            print(f"  BTC 7d trend : {btc['trend_7d']:+.2%}")
            print(f"  Realized vol : {btc['realized_vol']:.4f}")
            print(f"  Funding rate : {funding:.6f}")
            print(f"  ► Regime     : {regime} (confidence: {confidence:.2f})")

            # Load config
            config = json.loads(CONFIG_PATH.read_text())

            # Apply regime weights
            old_regime = config.get("regime", "NEUTRAL")
            config = apply_regime_to_config(config, regime, confidence)

            # Save updated config
            CONFIG_PATH.write_text(json.dumps(config, indent=2))

            # Save to memory
            save_regime_history(regime, confidence, fg, btc, funding)

            if old_regime != regime:
                print(f"  ⚡ REGIME SHIFT: {old_regime} → {regime}")
            else:
                print(f"  ✓ Config updated. Sobek will pick it up on next cycle.")

        except Exception as e:
            print(f"  [META ERROR] {e}")

        if once:
            break

        print()
        time.sleep(600)  # Run every 10 minutes


if __name__ == "__main__":
    run_meta_watcher()
