"""
Sobek Ankh — The Trader
Pantheon | Ankh Series
15 strategies. 100+ exchanges. Full risk engine. Never blows up.

"The waters of the Nile do not ask permission to flow." — Sobek
"""
import time
import os
from dotenv import load_dotenv

load_dotenv()

# ── Original 5 ──────────────────────────────────────────────────────────────
from strategies.funding_rate_arb import run as run_funding_arb
from strategies.cross_exchange_arb import run as run_cross_arb
from strategies.grid_trading import run as run_grid
from strategies.stat_arb import run as run_stat_arb
from strategies.multi_factor import run as run_multi_factor

# ── New 10 ──────────────────────────────────────────────────────────────────
from strategies.momentum_scalp import run as run_momentum_scalp
from strategies.mean_reversion import run as run_mean_reversion
from strategies.breakout_hunter import run as run_breakout_hunter
from strategies.dca_engine import run as run_dca_engine
from strategies.liquidation_sniper import run as run_liquidation_sniper
from strategies.news_sentiment import run as run_news_sentiment
from strategies.on_chain_alpha import run as run_on_chain_alpha
from strategies.options_flow import run as run_options_flow
from strategies.pairs_rotation import run as run_pairs_rotation
from strategies.volatility_harvest import run as run_volatility_harvest

from risk.risk_engine import get_risk_status
from utils.telegram_alert import send_alert, send_profit_report
from utils.midas_log import get_war_chest

CAPITAL = float(os.getenv("SOBEK_CAPITAL", "1000.0"))
SIMULATE_MODE = os.getenv("SIMULATE_MODE", "true").lower() == "true"
CYCLE_INTERVAL = int(os.getenv("CYCLE_INTERVAL", "300"))

# Strategy cadence: name -> {interval in seconds, last_run}
STRATEGIES = {
    "momentum_scalp":     {"fn": run_momentum_scalp,    "interval": 60,    "last_run": 0},
    "cross_arb":          {"fn": run_cross_arb,          "interval": 60,    "last_run": 0},
    "liquidation_sniper": {"fn": run_liquidation_sniper, "interval": 120,   "last_run": 0},
    "mean_reversion":     {"fn": run_mean_reversion,     "interval": 300,   "last_run": 0},
    "grid_trading":       {"fn": run_grid,               "interval": 300,   "last_run": 0},
    "breakout_hunter":    {"fn": run_breakout_hunter,    "interval": 300,   "last_run": 0},
    "news_sentiment":     {"fn": run_news_sentiment,     "interval": 600,   "last_run": 0},
    "dca_engine":         {"fn": run_dca_engine,         "interval": 900,   "last_run": 0},
    "volatility_harvest": {"fn": run_volatility_harvest, "interval": 900,   "last_run": 0},
    "options_flow":       {"fn": run_options_flow,       "interval": 1800,  "last_run": 0},
    "stat_arb":           {"fn": run_stat_arb,           "interval": 1800,  "last_run": 0},
    "on_chain_alpha":     {"fn": run_on_chain_alpha,     "interval": 1800,  "last_run": 0},
    "pairs_rotation":     {"fn": run_pairs_rotation,     "interval": 3600,  "last_run": 0},
    "funding_arb":        {"fn": run_funding_arb,        "interval": 28800, "last_run": 0},
    "multi_factor":       {"fn": run_multi_factor,       "interval": 86400, "last_run": 0},
}

def run_cycle():
    now = time.time()
    status = get_risk_status()
    if status.get("sobek_sleeping"):
        print("[SOBEK] Sleeping — drawdown limit hit. Awaiting Forgemaster restart.")
        return

    for name, cfg in STRATEGIES.items():
        if now - cfg["last_run"] >= cfg["interval"]:
            print(f"[SOBEK] Running: {name}")
            try:
                cfg["fn"](CAPITAL)
            except Exception as e:
                print(f"[SOBEK] {name} error: {e}")
            cfg["last_run"] = now

def daily_report():
    chest = get_war_chest()
    total = chest.get("total_trades", 0)
    pnl = chest.get("total_pnl", 0.0)
    wins = chest.get("wins", 0)
    win_rate = wins / total if total > 0 else 0
    send_profit_report(pnl, total, win_rate, CAPITAL)

def main():
    mode = "SIMULATE" if SIMULATE_MODE else "LIVE"
    print(f"""
\u2554{"\u2550"*38}\u2557
\u2551   \U0001f40a SOBEK ANKH \u2014 THE TRADER \U0001f40a    \u2551
\u2551   Pantheon | Ankh Series            \u2551
\u2551   Mode: {mode:<28} \u2551
\u2551   Capital: ${CAPITAL:<26.2f} \u2551
\u2551   Strategies: 15 Active             \u2551
\u2551   Risk Engine: ARMED                \u2551
\u255a{"\u2550"*38}\u255d
    """)

    send_alert(
        f"\U0001f40a SOBEK ANKH ONLINE\n"
        f"Mode: {mode}\n"
        f"Capital: ${CAPITAL:.2f}\n"
        f"Strategies: ALL 15 ACTIVE\n"
        f"Risk Engine: ARMED\n"
        f"The Nile flows at full strength. \U0001f531"
    )

    last_daily_report = 0

    while True:
        try:
            run_cycle()
            now = time.time()
            if now - last_daily_report >= 86400:
                daily_report()
                last_daily_report = now
            time.sleep(CYCLE_INTERVAL)
        except KeyboardInterrupt:
            print("\n[SOBEK] Shutting down gracefully.")
            send_alert("\U0001f40a SOBEK offline \u2014 manual shutdown by Forgemaster.")
            break
        except Exception as e:
            print(f"[SOBEK] Cycle error: {e}")
            send_alert(f"\u26a0\ufe0f SOBEK cycle error: {str(e)[:200]}")
            time.sleep(30)

if __name__ == "__main__":
    main()
