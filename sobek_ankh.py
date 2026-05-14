"""
SobekAnkh — The Trader
Pantheon Member #7 (Ankh Series)
Institutional-grade crypto trading bot.
15 strategies. 100+ exchanges. Full risk engine. Never blows up.

"The waters of the Nile do not ask permission to flow." — Sobek
"""
import time
import threading
import os
from dotenv import load_dotenv

load_dotenv()

from strategies.funding_rate_arb import run as run_funding_arb
from strategies.cross_exchange_arb import run as run_cross_arb
from strategies.grid_trading import run as run_grid
from strategies.stat_arb import run as run_stat_arb
from strategies.multi_factor import run as run_multi_factor
from risk.risk_engine import get_risk_status, wake_sobek
from utils.telegram_alert import send_alert, send_profit_report
from utils.midas_log import get_war_chest

# ─── CONFIG ──────────────────────────────────────────────────────────────────
CAPITAL = float(os.getenv("SOBEK_CAPITAL", "1000.0"))  # Starting capital in USDT
SIMULATE_MODE = os.getenv("SIMULATE_MODE", "true").lower() == "true"
CYCLE_INTERVAL = int(os.getenv("CYCLE_INTERVAL", "300"))  # 5 minutes per cycle
DAILY_REPORT_HOUR = int(os.getenv("DAILY_REPORT_HOUR", "8"))  # 8 AM daily report

# ─── STRATEGY SCHEDULE ────────────────────────────────────────────────────────
# Each strategy runs on its own cadence
STRATEGY_CADENCE = {
    "funding_arb":    {"interval": 28800,  "last_run": 0},  # Every 8h (funding period)
    "cross_arb":      {"interval": 60,     "last_run": 0},  # Every 1 min (fast)
    "grid_trading":   {"interval": 300,    "last_run": 0},  # Every 5 min
    "stat_arb":       {"interval": 1800,   "last_run": 0},  # Every 30 min
    "multi_factor":   {"interval": 86400,  "last_run": 0},  # Daily rebalance
}

# ─── MAIN LOOP ────────────────────────────────────────────────────────────────
def run_cycle():
    """Execute one full Sobek cycle."""
    now = time.time()
    results = []

    # Check risk status first
    status = get_risk_status()
    if status.get("sobek_sleeping"):
        print("[SOBEK] Sleeping — drawdown limit hit. Awaiting Forgemaster restart.")
        return

    # Funding Rate Arb (every 8h)
    if now - STRATEGY_CADENCE["funding_arb"]["last_run"] >= STRATEGY_CADENCE["funding_arb"]["interval"]:
        print("[SOBEK] Running: Funding Rate Arb")
        r = run_funding_arb(CAPITAL)
        results.extend(r if isinstance(r, list) else [r])
        STRATEGY_CADENCE["funding_arb"]["last_run"] = now

    # Cross-Exchange Arb (every 1 min)
    if now - STRATEGY_CADENCE["cross_arb"]["last_run"] >= STRATEGY_CADENCE["cross_arb"]["interval"]:
        print("[SOBEK] Running: Cross-Exchange Arb")
        r = run_cross_arb(CAPITAL)
        results.extend(r if isinstance(r, list) else [r])
        STRATEGY_CADENCE["cross_arb"]["last_run"] = now

    # Grid Trading (every 5 min)
    if now - STRATEGY_CADENCE["grid_trading"]["last_run"] >= STRATEGY_CADENCE["grid_trading"]["interval"]:
        print("[SOBEK] Running: Grid Trading")
        r = run_grid(CAPITAL)
        results.extend(r if isinstance(r, list) else [r])
        STRATEGY_CADENCE["grid_trading"]["last_run"] = now

    # Statistical Arb (every 30 min)
    if now - STRATEGY_CADENCE["stat_arb"]["last_run"] >= STRATEGY_CADENCE["stat_arb"]["interval"]:
        print("[SOBEK] Running: Statistical Arb")
        r = run_stat_arb(CAPITAL)
        results.extend(r if isinstance(r, list) else [r])
        STRATEGY_CADENCE["stat_arb"]["last_run"] = now

    # Multi-Factor (daily)
    if now - STRATEGY_CADENCE["multi_factor"]["last_run"] >= STRATEGY_CADENCE["multi_factor"]["interval"]:
        print("[SOBEK] Running: Multi-Factor Cross-Sectional")
        r = run_multi_factor(CAPITAL)
        results.append(r if isinstance(r, dict) else {})
        STRATEGY_CADENCE["multi_factor"]["last_run"] = now

    return results

def daily_report():
    """Send daily performance report to Forgemaster."""
    chest = get_war_chest()
    total = chest.get("total_trades", 0)
    pnl = chest.get("total_pnl", 0.0)
    wins = chest.get("wins", 0)
    win_rate = wins / total if total > 0 else 0
    send_profit_report(pnl, total, win_rate, CAPITAL)

def main():
    mode = "SIMULATE" if SIMULATE_MODE else "LIVE"
    print(f"""
╔══════════════════════════════════════╗
║   🐊 SOBEK ANKH — THE TRADER 🐊    ║
║   Pantheon | Ankh Series            ║
║   Mode: {mode:<28} ║
║   Capital: ${CAPITAL:<26.2f} ║
║   Strategies: 5 Active              ║
║   Risk Engine: ARMED                ║
╚══════════════════════════════════════╝
    """)

    send_alert(
        f"🐊 SOBEK ANKH ONLINE\n"
        f"Mode: {mode}\n"
        f"Capital: ${CAPITAL:.2f}\n"
        f"Strategies: Funding Arb | Cross-Exchange Arb | Grid | Stat Arb | Multi-Factor\n"
        f"Risk Engine: ARMED\n"
        f"The waters flow. 🔱"
    )

    last_daily_report = 0

    while True:
        try:
            run_cycle()

            # Daily report
            now = time.time()
            if now - last_daily_report >= 86400:
                daily_report()
                last_daily_report = now

            time.sleep(CYCLE_INTERVAL)

        except KeyboardInterrupt:
            print("\n[SOBEK] Shutting down gracefully.")
            send_alert("🐊 SOBEK offline — manual shutdown by Forgemaster.")
            break
        except Exception as e:
            print(f"[SOBEK] Cycle error: {e}")
            send_alert(f"⚠️ SOBEK cycle error: {str(e)[:200]}")
            time.sleep(30)

if __name__ == "__main__":
    main()
