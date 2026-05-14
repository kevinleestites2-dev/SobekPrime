"""
SobekPrime — MidasPrime Integration
Every trade logged to the War Chest in real time.
"""
import os
import json
import time
from datetime import datetime

LOG_FILE = "logs/war_chest.json"
TRADE_LOG = "logs/trades.jsonl"

def log_trade(trade: dict):
    """Log trade to JSONL file and update war chest summary."""
    os.makedirs("logs", exist_ok=True)

    trade["logged_at"] = datetime.utcnow().isoformat()

    # Append to trade log
    with open(TRADE_LOG, "a") as f:
        f.write(json.dumps(trade) + "\n")

    # Update war chest summary
    _update_war_chest(trade)

def _update_war_chest(trade: dict):
    try:
        with open(LOG_FILE) as f:
            chest = json.load(f)
    except Exception:
        chest = {
            "total_trades": 0,
            "total_pnl": 0.0,
            "wins": 0,
            "losses": 0,
            "strategies": {},
            "last_updated": None
        }

    chest["total_trades"] += 1
    pnl = trade.get("pnl", 0.0)
    chest["total_pnl"] += pnl

    if pnl > 0:
        chest["wins"] += 1
    elif pnl < 0:
        chest["losses"] += 1

    strategy = trade.get("strategy", "unknown")
    if strategy not in chest["strategies"]:
        chest["strategies"][strategy] = {"trades": 0, "pnl": 0.0, "wins": 0}
    chest["strategies"][strategy]["trades"] += 1
    chest["strategies"][strategy]["pnl"] += pnl
    if pnl > 0:
        chest["strategies"][strategy]["wins"] += 1

    chest["last_updated"] = datetime.utcnow().isoformat()

    with open(LOG_FILE, "w") as f:
        json.dump(chest, f, indent=2)

def get_war_chest() -> dict:
    try:
        with open(LOG_FILE) as f:
            return json.load(f)
    except Exception:
        return {}
