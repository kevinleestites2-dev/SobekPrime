"""
Sobek Ankh — Live Dashboard
Flask web server — hit it in your browser to see Sobek live.
Run: python dashboard.py
Then open: http://localhost:8080
"""
import json
import os
import time
from datetime import datetime
from pathlib import Path
from flask import Flask, jsonify, render_template_string

app = Flask(__name__)

LOG_FILE  = "logs/war_chest.json"
TRADE_LOG = "logs/trades.jsonl"
SOBEK_START = time.time()

HTML = """
<!DOCTYPE html>
<html>
<head>
  <title>🐊 Sobek Dashboard</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="30">
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0a0a0a; color: #e0e0e0; font-family: 'Courier New', monospace; padding: 16px; }
    h1 { color: #c9a84c; font-size: 1.4em; margin-bottom: 4px; }
    .sub { color: #888; font-size: 0.8em; margin-bottom: 20px; }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 20px; }
    .card { background: #141414; border: 1px solid #2a2a2a; border-radius: 8px; padding: 14px; }
    .card .label { color: #888; font-size: 0.75em; text-transform: uppercase; margin-bottom: 4px; }
    .card .value { font-size: 1.5em; font-weight: bold; }
    .green { color: #00e676; }
    .red   { color: #ff5252; }
    .gold  { color: #c9a84c; }
    .white { color: #fff; }
    table { width: 100%; border-collapse: collapse; font-size: 0.8em; }
    th { color: #888; text-align: left; padding: 6px 4px; border-bottom: 1px solid #2a2a2a; }
    td { padding: 6px 4px; border-bottom: 1px solid #1a1a1a; }
    .badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.75em; }
    .badge-green { background: #003300; color: #00e676; }
    .badge-red   { background: #330000; color: #ff5252; }
    .badge-grey  { background: #1a1a1a; color: #888; }
    .section-title { color: #c9a84c; font-size: 0.85em; text-transform: uppercase; margin: 16px 0 8px; letter-spacing: 1px; }
    .status-bar { display: flex; align-items: center; gap: 8px; margin-bottom: 20px; }
    .dot { width: 10px; height: 10px; border-radius: 50%; background: #00e676; animation: pulse 2s infinite; }
    @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.3} }
    .footer { color: #333; font-size: 0.7em; margin-top: 20px; text-align: center; }
  </style>
</head>
<body>
  <h1>🐊 SOBEK ANKH</h1>
  <p class="sub">The Trader — Pantheon Ankh Series</p>

  <div class="status-bar">
    <div class="dot"></div>
    <span style="color:#00e676; font-size:0.85em;">LIVE</span>
    <span style="color:#444; font-size:0.85em;">|</span>
    <span style="color:#888; font-size:0.8em;">{{ uptime }}</span>
    <span style="color:#444; font-size:0.85em;">|</span>
    <span style="color:#888; font-size:0.8em;">Auto-refresh 30s</span>
  </div>

  <div class="grid">
    <div class="card">
      <div class="label">Total PnL</div>
      <div class="value {{ 'green' if pnl >= 0 else 'red' }}">{{ '+' if pnl >= 0 else '' }}{{ "%.2f"|format(pnl) }} USDT</div>
    </div>
    <div class="card">
      <div class="label">Total Trades</div>
      <div class="value white">{{ total_trades }}</div>
    </div>
    <div class="card">
      <div class="label">Win Rate</div>
      <div class="value {{ 'green' if win_rate >= 50 else 'red' }}">{{ "%.1f"|format(win_rate) }}%</div>
    </div>
    <div class="card">
      <div class="label">W / L</div>
      <div class="value white"><span class="green">{{ wins }}</span> / <span class="red">{{ losses }}</span></div>
    </div>
  </div>

  <div class="section-title">📊 Strategy Breakdown</div>
  <table>
    <tr><th>Strategy</th><th>Trades</th><th>PnL</th><th>Status</th></tr>
    {% for s in strategies %}
    <tr>
      <td style="color:#c9a84c">{{ s.name }}</td>
      <td>{{ s.trades }}</td>
      <td class="{{ 'green' if s.pnl >= 0 else 'red' }}">{{ '+' if s.pnl >= 0 else '' }}{{ "%.4f"|format(s.pnl) }}</td>
      <td>
        {% if s.pnl > 0 %}<span class="badge badge-green">HOT</span>
        {% elif s.pnl < 0 %}<span class="badge badge-red">COLD</span>
        {% else %}<span class="badge badge-grey">FLAT</span>{% endif %}
      </td>
    </tr>
    {% endfor %}
  </table>

  <div class="section-title">🕐 Recent Trades</div>
  <table>
    <tr><th>Strategy</th><th>PnL</th><th>Time</th></tr>
    {% for t in recent %}
    <tr>
      <td style="color:#aaa">{{ t.strategy }}</td>
      <td class="{{ 'green' if t.pnl >= 0 else 'red' }}">{{ '+' if t.pnl >= 0 else '' }}{{ "%.4f"|format(t.pnl) }}</td>
      <td style="color:#555">{{ t.time }}</td>
    </tr>
    {% endfor %}
  </table>

  <div class="footer">🔱 For the War Chest. For the Pantheon. — Last updated: {{ now }}</div>
</body>
</html>
"""

def get_chest():
    try:
        with open(LOG_FILE) as f:
            return json.load(f)
    except:
        return {"total_trades":0,"total_pnl":0.0,"wins":0,"losses":0,"strategies":{}}

def get_recent(n=10):
    trades = []
    try:
        lines = Path(TRADE_LOG).read_text().strip().split("\n")
        for line in reversed(lines[-n:]):
            t = json.loads(line)
            ts = t.get("logged_at","")[:19].replace("T"," ")
            trades.append({"strategy": t.get("strategy","?"), "pnl": t.get("pnl",0.0), "time": ts})
    except:
        pass
    return trades

def fmt_uptime(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    return f"Up {h}h {m}m"

@app.route("/")
def index():
    chest = get_chest()
    total = chest.get("total_trades", 0)
    pnl   = chest.get("total_pnl", 0.0)
    wins  = chest.get("wins", 0)
    losses= chest.get("losses", 0)
    win_rate = (wins / total * 100) if total > 0 else 0.0

    strats = []
    for name, data in sorted(chest.get("strategies",{}).items(), key=lambda x: -x[1].get("pnl",0)):
        strats.append({"name": name, "trades": data["trades"], "pnl": data["pnl"]})

    return render_template_string(HTML,
        pnl=pnl, total_trades=total, wins=wins, losses=losses,
        win_rate=win_rate, strategies=strats,
        recent=get_recent(), uptime=fmt_uptime(time.time()-SOBEK_START),
        now=datetime.utcnow().strftime("%H:%M:%S UTC"))

@app.route("/api")
def api():
    chest = get_chest()
    return jsonify(chest)

if __name__ == "__main__":
    print("[SOBEK] Dashboard live → http://localhost:8080")
    app.run(host="0.0.0.0", port=8080, debug=False)
