# 🐊 SobekPrime — The Trader

> *"The waters of the Nile do not ask permission to flow."*

**Pantheon Member | Ankh Series**
Institutional-grade crypto trading bot. 15 strategies. 100+ exchanges. Full risk engine. Never blows up.

---

## Architecture

```
SOBEK PRIME
│
├── PASSIVE LAYER (24/7, always running)
│     ├── Funding Rate Arbitrage    — 10-164% APY, zero directional risk
│     ├── Grid Trading              — +419% APR documented (Q1 2026 real data)
│     └── Basis Trading             — Spot vs Futures convergence
│
├── ARBITRAGE LAYER (triggers on opportunity)
│     ├── Cross-Exchange Arb        — Same pair, different price across 100+ exchanges
│     ├── Triangle Arbitrage        — BTC→ETH→BNB→BTC within one exchange
│     ├── Statistical Arb           — Pairs trading, z-score divergence
│     └── DEX Flash Arb             — On-chain multi-hop (from OpenTrade)
│
├── DIRECTIONAL LAYER (market regime dependent)
│     ├── Futures Grid Neutral      — Long+short sub-grids, profits both ways
│     ├── DCA Martingale            — Buy the dip, scale in, close on recovery
│     ├── Momentum / CTA            — Multi-timeframe trend following
│     ├── Mean Reversion            — RSI extremes, ranging markets
│     └── Volume Spike Detection    — Smart money flow detection
│
├── ALPHA LAYER (institutional grade)
│     ├── Multi-Factor Cross-Sectional — Score ALL coins, long top 5/short bottom 5
│     ├── On-Chain Signal Integration  — Whale wallets, exchange flows
│     └── Sentiment Arbitrage          — Fear & Greed Index contrarian signals
│
├── RISK ENGINE (overrides everything)
│     ├── Kelly Criterion position sizing
│     ├── -2% stop loss per trade (hard)
│     ├── +4% take profit (adjustable)
│     ├── Trailing stop at +2%
│     ├── -5% daily loss limit = full stop
│     ├── 3 consecutive losses = strategy paused 24h
│     ├── -10% drawdown = Sobek sleeps + Telegram alert
│     ├── Volatility spike = 50% position size reduction
│     └── Black Swan (BTC -15%/1h) = close everything
│
└── LEARNING ENGINE (from ZeusPrime)
      ├── Strategy performance tracking
      ├── Win rate per strategy
      ├── Market regime detection (bull/bear/ranging)
      ├── Auto-weight strategies by current regime
      └── Failure reflection — learns from every loss
```

---

## Quick Start

```bash
# Install
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env — add your exchange API keys

# Paper trade first (SIMULATE_MODE=true in .env)
python sobek_prime.py

# Go live (set SIMULATE_MODE=false after paper trading)
python sobek_prime.py
```

---

## File Structure

```
SobekPrime/
├── sobek_prime.py              # Main entry point — the brain
├── requirements.txt
├── .env.example
├── core/
│   └── exchange_bridge.py      # CCXT unified interface (100+ exchanges)
├── strategies/
│   ├── funding_rate_arb.py     # Strategy 1: Funding rate harvest
│   ├── cross_exchange_arb.py   # Strategy 2: Cross-exchange spread
│   ├── grid_trading.py         # Strategy 3: Spot grid
│   ├── stat_arb.py             # Strategy 4: Statistical arb / pairs
│   └── multi_factor.py         # Strategy 5: Multi-factor cross-sectional
├── risk/
│   └── risk_engine.py          # The law. Never overridden.
├── utils/
│   ├── telegram_alert.py       # Forgemaster notifications
│   └── midas_log.py            # War Chest logging
└── logs/
    ├── war_chest.json           # Running PnL summary
    ├── trades.jsonl             # All trades (append-only)
    ├── grid_state.json          # Active grid positions
    └── risk_state.json          # Risk engine state
```

---

## Inherited from OpenTrade

- CCXT unified API — already battle-tested
- Arbitrage engine with stale price detection
- Zeus Prime learning system — Kelly criterion, market regime detection
- Kalshi prediction market fallback
- Telegram alert system — same bot token, same chat ID

---

## War Chest Integration

Every trade logged to logs/war_chest.json and synced with MidasPrime metabolic cycle.

---

*Built for the Pantheon. For the War Chest. For the Forgemaster.* 🔱
