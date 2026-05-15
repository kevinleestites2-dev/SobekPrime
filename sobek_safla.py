"""
sobek_safla.py — The Feedback Loop
Sobek Ankh v2 | SAFLA Layer

Generator-Reflector-Curator pattern (ace-playbook inspired).
Every N trades: reads performance, rewrites config, reloads.
The loop improves the loop. The learning learns how to learn.

"The crocodile does not fight the current. He learns it." — Pantheon
"""

import json
import time
from datetime import datetime
from pathlib import Path
from collections import defaultdict

CONFIG_PATH = Path("sobek_config.json")
MEMORY_DIR  = Path("memory")
MEMORY_DIR.mkdir(exist_ok=True)

TRADE_LOG   = MEMORY_DIR / "trade_log.json"
PERF_FILE   = MEMORY_DIR / "strategy_performance.json"
SAFLA_LOG   = MEMORY_DIR / "safla_interventions.json"


# ─────────────────────────────────────────
# MEMORY — load / save trade log
# ─────────────────────────────────────────

def load_trade_log() -> list:
    if TRADE_LOG.exists():
        try:
            return json.loads(TRADE_LOG.read_text())
        except Exception:
            return []
    return []


def append_trade(trade: dict):
    """Called by sobek_ankh.py after every trade."""
    log = load_trade_log()
    trade["logged_at"] = datetime.utcnow().isoformat()
    log.append(trade)
    TRADE_LOG.write_text(json.dumps(log, indent=2))


# ─────────────────────────────────────────
# GENERATOR — what is the current state?
# ─────────────────────────────────────────

def generate_state(trades: list, n: int = 50) -> dict:
    """
    Analyzes last N trades per strategy.
    Returns raw performance data.
    """
    recent = trades[-n:] if len(trades) >= n else trades
    by_strategy = defaultdict(list)

    for t in recent:
        name = t.get("strategy", "unknown")
        pnl  = float(t.get("pnl", 0))
        by_strategy[name].append(pnl)

    state = {}
    for strategy, pnls in by_strategy.items():
        wins   = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]
        total  = len(pnls)

        win_rate = len(wins) / total if total > 0 else 0
        avg_win  = sum(wins) / len(wins) if wins else 0
        avg_loss = abs(sum(losses) / len(losses)) if losses else 0
        expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)

        state[strategy] = {
            "trade_count": total,
            "win_rate":    round(win_rate, 4),
            "avg_win":     round(avg_win, 4),
            "avg_loss":    round(avg_loss, 4),
            "expectancy":  round(expectancy, 4),
            "total_pnl":   round(sum(pnls), 4)
        }

    return state


# ─────────────────────────────────────────
# REFLECTOR — why is it happening?
# ─────────────────────────────────────────

def reflect(state: dict, config: dict) -> dict:
    """
    Interprets the state. Identifies winners, losers, and opportunities.
    Returns a diagnosis dict.
    """
    shrink_thresh = config["safla"]["shrink_threshold"]
    grow_thresh   = config["safla"]["grow_threshold"]

    diagnosis = {
        "winners":     [],
        "losers":      [],
        "struggling":  [],
        "insufficient_data": [],
        "insights":    []
    }

    for strategy, perf in state.items():
        if perf["trade_count"] < 5:
            diagnosis["insufficient_data"].append(strategy)
            continue

        wr = perf["win_rate"]
        ex = perf["expectancy"]

        if wr >= grow_thresh and ex > 0:
            diagnosis["winners"].append(strategy)
        elif wr < shrink_thresh or ex < 0:
            diagnosis["losers"].append(strategy)
        else:
            diagnosis["struggling"].append(strategy)

    # Cross-strategy insight — do meta strategies agree with object strategies?
    meta_strategies = [s for s, t in config["strategy_type"].items() if t == "meta"]
    obj_strategies  = [s for s, t in config["strategy_type"].items() if t == "object"]

    meta_winners = [s for s in diagnosis["winners"] if s in meta_strategies]
    obj_winners  = [s for s in diagnosis["winners"] if s in obj_strategies]

    if len(meta_winners) > len(meta_strategies) * 0.6 and len(obj_winners) > len(obj_strategies) * 0.6:
        diagnosis["insights"].append("HIGH_CONVICTION: meta and object strategies both winning")
    elif len(meta_winners) > len(meta_strategies) * 0.6 and len(obj_winners) < len(obj_strategies) * 0.3:
        diagnosis["insights"].append("META_LEADING: meta strategies ahead — regime shift may be coming")
    elif len(diagnosis["losers"]) > len(state) * 0.5:
        diagnosis["insights"].append("BROAD_UNDERPERFORMANCE: majority of strategies losing — check regime")

    return diagnosis


# ─────────────────────────────────────────
# CURATOR — keep what works, shrink what doesn't
# ─────────────────────────────────────────

def curate(config: dict, state: dict, diagnosis: dict) -> dict:
    """
    Rewrites strategy weights based on performance.
    The heart of SAFLA — the config that comes out is better than the one that went in.
    """
    safla_cfg = config["safla"]
    shrink_f  = safla_cfg["shrink_factor"]
    grow_f    = safla_cfg["grow_factor"]
    max_w     = safla_cfg["max_weight"]
    min_w     = safla_cfg["min_weight"]

    changes = {}

    for strategy in config["strategy_weights"]:
        if strategy not in state:
            continue

        current_weight = config["strategy_weights"][strategy]
        new_weight = current_weight

        if strategy in diagnosis["winners"]:
            new_weight = min(current_weight * grow_f, max_w)
        elif strategy in diagnosis["losers"]:
            new_weight = max(current_weight * shrink_f, min_w)
        # struggling — leave it alone, let it run

        new_weight = round(new_weight, 3)
        if new_weight != current_weight:
            changes[strategy] = {"from": current_weight, "to": new_weight}
            config["strategy_weights"][strategy] = new_weight

    # Update SAFLA metadata
    config["safla"]["trade_count_since_review"] = 0
    config["safla"]["last_review_at"] = datetime.utcnow().isoformat()
    config["safla"]["total_reviews"] = config["safla"].get("total_reviews", 0) + 1

    return config, changes


# ─────────────────────────────────────────
# LOG THE INTERVENTION
# ─────────────────────────────────────────

def log_intervention(state: dict, diagnosis: dict, changes: dict):
    """Record what SAFLA did and why. This builds the meta-memory."""
    log = []
    if SAFLA_LOG.exists():
        try:
            log = json.loads(SAFLA_LOG.read_text())
        except Exception:
            log = []

    config = json.loads(CONFIG_PATH.read_text())

    entry = {
        "ts":        datetime.utcnow().isoformat(),
        "regime":    config.get("regime", "UNKNOWN"),
        "winners":   diagnosis["winners"],
        "losers":    diagnosis["losers"],
        "insights":  diagnosis["insights"],
        "changes":   changes,
        "review_n":  config["safla"].get("total_reviews", 0)
    }
    log.append(entry)
    log = log[-200:]  # Keep last 200 interventions
    SAFLA_LOG.write_text(json.dumps(log, indent=2))

    # Save strategy performance snapshot
    PERF_FILE.write_text(json.dumps({
        "updated_at": datetime.utcnow().isoformat(),
        "regime": config.get("regime", "UNKNOWN"),
        "performance": state
    }, indent=2))


# ─────────────────────────────────────────
# SAFLA MAIN LOOP
# ─────────────────────────────────────────

def run_safla_check(force: bool = False) -> bool:
    """
    Called after every trade. Returns True if SAFLA reviewed and updated config.
    """
    config = json.loads(CONFIG_PATH.read_text())

    if not config["safla"]["enabled"]:
        return False

    # Increment trade counter
    config["safla"]["trade_count_since_review"] += 1
    review_every = config["safla"]["review_every_n_trades"]
    count = config["safla"]["trade_count_since_review"]

    CONFIG_PATH.write_text(json.dumps(config, indent=2))

    if not force and count < review_every:
        return False

    # Time to review
    print(f"\n⚡ SAFLA REVIEW #{config['safla'].get('total_reviews', 0) + 1} — {count} trades since last review")

    trades = load_trade_log()
    if len(trades) < 10:
        print("  Not enough trades yet. Need at least 10.")
        return False

    # Generator
    state = generate_state(trades, n=review_every)
    print(f"  Strategies analyzed: {len(state)}")

    # Reflector
    diagnosis = reflect(state, config)
    print(f"  Winners:  {diagnosis['winners']}")
    print(f"  Losers:   {diagnosis['losers']}")
    if diagnosis["insights"]:
        for insight in diagnosis["insights"]:
            print(f"  ⚡ Insight: {insight}")

    # Curator
    config = json.loads(CONFIG_PATH.read_text())  # re-read fresh
    config, changes = curate(config, state, diagnosis)

    if changes:
        print("  Weight changes:")
        for s, c in changes.items():
            direction = "↑" if c["to"] > c["from"] else "↓"
            print(f"    {direction} {s}: {c['from']} → {c['to']}")
    else:
        print("  No weight changes needed.")

    # Save
    CONFIG_PATH.write_text(json.dumps(config, indent=2))
    log_intervention(state, diagnosis, changes)

    print("  ✓ SAFLA complete. Config updated. Sobek reloads on next cycle.\n")
    return True


# ─────────────────────────────────────────
# RECALL — what worked last time in this regime?
# ─────────────────────────────────────────

def recall_regime_memory(regime: str) -> dict | None:
    """
    Mnemosyne pattern — look back at past interventions in this regime.
    Returns the best performing config snapshot for this regime, if any.
    """
    if not SAFLA_LOG.exists():
        return None

    try:
        log = json.loads(SAFLA_LOG.read_text())
    except Exception:
        return None

    regime_entries = [e for e in log if e.get("regime") == regime]
    if not regime_entries:
        return None

    # Find the entry where the most winners were identified in this regime
    best = max(regime_entries, key=lambda e: len(e.get("winners", [])))
    return {
        "regime": regime,
        "last_seen": best["ts"],
        "winners_then": best["winners"],
        "changes_then": best["changes"],
        "insight": best.get("insights", [])
    }


if __name__ == "__main__":
    # Force a SAFLA review right now
    print("🔱 Running forced SAFLA review...")
    result = run_safla_check(force=True)
    if not result:
        print("No review triggered — not enough data or SAFLA disabled.")
