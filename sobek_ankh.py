"""
Sobek Ankh — The Trader
Pantheon | Ankh Series
15 strategies. 100+ exchanges. Full risk engine. Never blows up.

v2.0 — Meta+SAFLA wired in.
Reads sobek_config.json for weights. SAFLA reviews every 50 trades.
The Watcher above rewrites the config. Sobek just executes.

"The waters of the Nile do not ask permission to flow." — Sobek
"""
import time
import os
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Original 5
from strategies.funding_rate_arb import run as run_funding_arb
from strategies.cross_exchange_arb import run as run_cross_arb
from strategies.grid_trading import run as run_grid
from strategies.stat_arb import run as run_stat_arb
from strategies.multi_factor import run as run_multi_factor

# New 10
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
from utils.midas_log import log_trade, get_war_chest

# ── Meta + SAFLA ──────────────────────────────────────────────
from sobek_safla import run_safla_check, append_trade

CONFIG_PATH = Path("sobek_config.json")

def load_config() -> dict:
    """Load sobek_config.json — reloaded every cycle so Meta Watcher changes take effect."""
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text())
        except Exception:
            pass
    return {"strategy_weights": {}, "safla": {"enabled": False}, "regime": "NEUTRAL"}

# ─────────────────────────────────────────────────────────────

CAPITAL = float(os.getenv("SOBEK_CAPITAL", "1000.0"))
SIMULATE_MODE = os.getenv("SIMULATE_MODE", "true").lower() == "true"
CYCLE_INTERVAL = int(os.getenv("CYCLE_INTERVAL", "300"))

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


def get_position_size(name: str, config: dict) -> float:
    """
    Base capital * weight from config * conviction score.
    Sobek sizes positions by what the Meta layer says — not flat allocation.
    """
    weights = config.get("strategy_weights", {})
    weight  = weights.get(name, 1.0)
    base    = config.get("risk", {}).get("base_position_pct", 0.02)
    return round(CAPITAL * base * weight, 4)


def process_results(name: str, results, config: dict):
    """Log all trade results. Feed each trade to SAFLA."""
    if not results:
        return
    if isinstance(results, dict):
        results = [results]

    for trade in results:
        if not isinstance(trade, dict):
            continue
        if "pnl" not in trade:
            continue

        trade["strategy"] = trade.get("strategy", name)
        trade["regime"]   = config.get("regime", "NEUTRAL")
        trade["weight"]   = config.get("strategy_weights", {}).get(name, 1.0)

        # Log to War Chest
        log_trade(trade)

        # Feed to SAFLA memory
        append_trade(trade)

        pnl  = trade["pnl"]
        pair = trade.get("pair", name)
        wt   = trade["weight"]
        emoji = "🟢" if pnl > 0 else "🔴" if pnl < 0 else "⚪"
        print(f"  {emoji} [{name}] {pair} | PnL: {pnl:+.4f} USDT | weight: {wt}")

    # Trigger SAFLA review if threshold reached
    run_safla_check()


def run_cycle(config: dict):
    now    = time.time()
    status = get_risk_status()

    if status.get("sobek_sleeping"):
        print("[SOBEK] Sleeping — drawdown limit hit. Awaiting Forgemaster restart.")
        return

    for name, cfg in STRATEGIES.items():
        if now - cfg["last_run"] >= cfg["interval"]:
            # Dynamic position size — driven by Meta+SAFLA weight
            position = get_position_size(name, config)
            print(f"[SOBEK] Running: {name} | position: ${position:.2f} | regime: {config.get('regime','?')}")
            try:
                results = cfg["fn"](position)
                process_results(name, results, config)
            except Exception as e:
                print(f"[SOBEK] {name} error: {e}")
            cfg["last_run"] = now


def daily_report(config: dict):
    chest    = get_war_chest()
    total    = chest.get("total_trades", 0)
    pnl      = chest.get("total_pnl", 0.0)
    wins     = chest.get("wins", 0)
    win_rate = wins / total if total > 0 else 0
    regime   = config.get("regime", "NEUTRAL")
    reviews  = config.get("safla", {}).get("total_reviews", 0)

    send_profit_report(pnl, total, win_rate, CAPITAL)

    strategies = chest.get("strategies", {})
    if strategies:
        top_name = max(strategies, key=lambda x: strategies[x]["pnl"])
        top_data = strategies[top_name]
        top_weight = config.get("strategy_weights", {}).get(top_name, 1.0)
        send_alert(
            f"📊 SOBEK DAILY REPORT\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"🌊 Regime: {regime}\n"
            f"⚡ SAFLA Reviews: {reviews}\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"🏆 Top: {top_name}\n"
            f"💰 PnL: {top_data['pnl']:+.4f} USDT\n"
            f"📈 Trades: {top_data['trades']}\n"
            f"⚖️  Weight: {top_weight}x\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"The Nile flows. 🐊🔱"
        )


def main():
    mode = "SIMULATE" if SIMULATE_MODE else "LIVE"

    # Load initial config
    config = load_config()
    regime = config.get("regime", "NEUTRAL")
    reviews = config.get("safla", {}).get("total_reviews", 0)

    print(f"""
╔══════════════════════════════════════════╗
║   🐊 SOBEK ANKH v2 — THE ORGANISM 🐊   ║
║   Pantheon | Ankh Series                ║
║   Mode: {mode:<30} ║
║   Capital: ${CAPITAL:<28.2f} ║
║   Strategies: 15 Active                 ║
║   Regime: {regime:<29} ║
║   SAFLA Reviews: {reviews:<22} ║
║   Meta Watcher: ACTIVE                  ║
║   Risk Engine: ARMED                    ║
╚══════════════════════════════════════════╝
    """)

    send_alert(
        f"🐊 SOBEK ANKH v2 ONLINE\n"
        f"Mode: {mode}\n"
        f"Capital: ${CAPITAL:.2f}\n"
        f"Regime: {regime}\n"
        f"SAFLA: ACTIVE ({reviews} reviews)\n"
        f"Meta Watcher: WATCHING\n"
        f"15 strategies. Living. Learning.\n"
        f"The Nile flows. 🔱"
    )

    last_daily_report  = 0
    last_config_reload = 0

    while True:
        try:
            now = time.time()

            # Reload config every 60s — picks up Meta Watcher changes silently
            if now - last_config_reload >= 60:
                config = load_config()
                last_config_reload = now

            run_cycle(config)

            if now - last_daily_report >= 86400:
                daily_report(config)
                last_daily_report = now

            time.sleep(CYCLE_INTERVAL)

        except KeyboardInterrupt:
            print("\n[SOBEK] Shutting down gracefully.")
            chest = get_war_chest()
            pnl    = chest.get("total_pnl", 0.0)
            trades = chest.get("total_trades", 0)
            reviews = config.get("safla", {}).get("total_reviews", 0)
            send_alert(
                f"🐊 SOBEK offline — manual shutdown.\n"
                f"Session PnL: {pnl:+.4f} USDT\n"
                f"Total Trades: {trades}\n"
                f"SAFLA Reviews: {reviews}\n"
                f"For the War Chest. 🔱"
            )
            break
        except Exception as e:
            print(f"[SOBEK] Cycle error: {e}")
            send_alert(f"⚠️ SOBEK cycle error: {str(e)[:200]}")
            time.sleep(30)


if __name__ == "__main__":
    main()
