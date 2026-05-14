"""
SobekAnkh — Telegram Alert System
Inherits ZeusPrime's Telegram config. Sobek speaks through the same channel.
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8679655550:AAGUB1m5fmqHc8OHqqM24Vixz8FfwX-gqD4")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "7135054241")
BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

def send_alert(message: str, silent: bool = False) -> bool:
    """Send alert to Forgemaster via Telegram."""
    try:
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
            "disable_notification": silent
        }
        r = requests.post(f"{BASE_URL}/sendMessage", json=payload, timeout=10)
        return r.status_code == 200
    except Exception as e:
        print(f"[TELEGRAM] Alert failed: {e}")
        return False

def send_critical(message: str) -> bool:
    """High priority — always with sound."""
    return send_alert(f"🚨 CRITICAL\n{message}", silent=False)

def send_profit_report(daily_pnl: float, total_trades: int, win_rate: float, capital: float):
    msg = (
        f"🐊 SOBEK DAILY REPORT\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"💰 Daily PnL: {'+'if daily_pnl>=0 else ''}{daily_pnl:.2f} USDT\n"
        f"📊 Trades: {total_trades}\n"
        f"🎯 Win Rate: {win_rate:.1%}\n"
        f"🏦 Capital: ${capital:.2f}\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"For the War Chest. For the Pantheon. 🔱"
    )
    return send_alert(msg)
