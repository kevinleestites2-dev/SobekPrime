"""
SobekPrime — Risk Engine
The law. Overrides everything. Sobek never blows up.
"""
import os
import json
import time
from datetime import datetime, date

RISK_CONFIG = {
    "stop_loss_pct": float(os.getenv("STOP_LOSS_PCT", "0.02")),        # -2% per trade
    "take_profit_pct": float(os.getenv("TAKE_PROFIT_PCT", "0.04")),    # +4% per trade
    "trailing_stop_pct": float(os.getenv("TRAILING_STOP_PCT", "0.02")), # trails at +2%
    "max_open_positions": int(os.getenv("MAX_POSITIONS", "5")),
    "daily_loss_limit_pct": float(os.getenv("DAILY_LOSS_LIMIT", "0.05")), # -5% = full stop
    "max_drawdown_pct": float(os.getenv("MAX_DRAWDOWN", "0.10")),        # -10% = sleep
    "consecutive_loss_pause": int(os.getenv("CONSEC_LOSS_PAUSE", "3")),  # 3 losses = pause strat
    "black_swan_pct": float(os.getenv("BLACK_SWAN_PCT", "0.15")),        # BTC -15%/1h = close all
    "volatility_reduction_pct": float(os.getenv("VOL_REDUCTION", "0.50")), # spike = half size
    "max_dca_layers": int(os.getenv("MAX_DCA_LAYERS", "6")),
}

STATE_FILE = "logs/risk_state.json"

def _load_state() -> dict:
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except Exception:
        return {
            "daily_pnl": 0.0,
            "peak_capital": 0.0,
            "open_positions": 0,
            "strategy_losses": {},
            "paused_strategies": {},
            "sobek_sleeping": False,
            "last_reset": str(date.today()),
        }

def _save_state(state: dict):
    os.makedirs("logs", exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def _reset_daily_if_needed(state: dict) -> dict:
    today = str(date.today())
    if state.get("last_reset") != today:
        state["daily_pnl"] = 0.0
        state["last_reset"] = today
    return state

def kelly_position_size(capital: float, win_rate: float, avg_win: float, avg_loss: float) -> float:
    """Kelly Criterion — optimal position size."""
    if avg_loss == 0:
        return 0.0
    b = avg_win / avg_loss
    q = 1 - win_rate
    kelly = (b * win_rate - q) / b
    kelly = max(0.0, min(kelly, 0.25))  # cap at 25% of capital
    return capital * kelly

def can_trade(strategy_name: str, capital: float) -> tuple[bool, str]:
    """Check if trading is allowed. Returns (allowed, reason)."""
    state = _load_state()
    state = _reset_daily_if_needed(state)

    if state.get("sobek_sleeping"):
        return False, "SOBEK_SLEEPING: Drawdown limit hit. Awaiting manual restart."

    daily_loss_limit = capital * RISK_CONFIG["daily_loss_limit_pct"]
    if state["daily_pnl"] <= -daily_loss_limit:
        return False, f"DAILY_LIMIT_HIT: Lost {state['daily_pnl']:.2f} today. No more trades."

    if state["open_positions"] >= RISK_CONFIG["max_open_positions"]:
        return False, f"MAX_POSITIONS: {state['open_positions']} trades open."

    paused = state.get("paused_strategies", {})
    if strategy_name in paused:
        pause_until = paused[strategy_name]
        if time.time() < pause_until:
            remaining = int((pause_until - time.time()) / 3600)
            return False, f"STRATEGY_PAUSED: {strategy_name} paused for {remaining}h more."
        else:
            del paused[strategy_name]
            state["paused_strategies"] = paused

    _save_state(state)
    return True, "OK"

def record_trade_result(strategy_name: str, pnl: float, capital: float):
    """Record trade outcome and apply consequences."""
    state = _load_state()
    state = _reset_daily_if_needed(state)

    state["daily_pnl"] = state.get("daily_pnl", 0.0) + pnl
    state["open_positions"] = max(0, state.get("open_positions", 1) - 1)

    if pnl < 0:
        losses = state.get("strategy_losses", {})
        losses[strategy_name] = losses.get(strategy_name, 0) + 1
        state["strategy_losses"] = losses

        if losses[strategy_name] >= RISK_CONFIG["consecutive_loss_pause"]:
            pause_until = time.time() + 86400  # 24h
            state["paused_strategies"][strategy_name] = pause_until
            losses[strategy_name] = 0
            print(f"[RISK] {strategy_name} paused 24h after {RISK_CONFIG['consecutive_loss_pause']} consecutive losses.")
    else:
        losses = state.get("strategy_losses", {})
        losses[strategy_name] = 0
        state["strategy_losses"] = losses

    peak = state.get("peak_capital", capital)
    if capital > peak:
        state["peak_capital"] = capital
    drawdown = (state["peak_capital"] - capital) / state["peak_capital"] if state["peak_capital"] > 0 else 0
    if drawdown >= RISK_CONFIG["max_drawdown_pct"]:
        state["sobek_sleeping"] = True
        print(f"[RISK] DRAWDOWN {drawdown:.1%} — SOBEK SLEEPING. Manual restart required.")

    _save_state(state)

def open_position():
    state = _load_state()
    state["open_positions"] = state.get("open_positions", 0) + 1
    _save_state(state)

def get_stop_loss(entry_price: float, side: str) -> float:
    if side == "buy":
        return entry_price * (1 - RISK_CONFIG["stop_loss_pct"])
    return entry_price * (1 + RISK_CONFIG["stop_loss_pct"])

def get_take_profit(entry_price: float, side: str, pct: float = None) -> float:
    tp_pct = pct or RISK_CONFIG["take_profit_pct"]
    if side == "buy":
        return entry_price * (1 + tp_pct)
    return entry_price * (1 - tp_pct)

def wake_sobek():
    """Manually wake Sobek after drawdown event."""
    state = _load_state()
    state["sobek_sleeping"] = False
    state["daily_pnl"] = 0.0
    _save_state(state)
    print("[RISK] Sobek awakened. Trading resumed.")

def get_risk_status() -> dict:
    return _load_state()
