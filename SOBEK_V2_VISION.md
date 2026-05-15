# SOBEK ANKH v2 — THE LIVING ORGANISM
## Locked: 2026-05-14 21:49 EDT

---

## THE CORE INSIGHT

Sobek v1 is object-level. He reads the market.
Sobek v2 is meta. He reads the market's opinion of itself.

OpenTrade was meta from line 1 — it didn't predict prices,
it exploited the gap between two platforms disagreeing on the 
same event. That's not prediction. That's math.

Sobek v2 becomes that. Not born meta — he EARNS it.

---

## THE PHILOSOPHY

"He gets better at getting better."
"He gets better at getting by."

Not just self-improving. SELF-SURVIVING.
The loop improves the loop.
The learning learns how to learn.
That's the SAFLA distinction.

---

## THE ARCHITECTURE

```
MetaPrime (The Overlord)
    └── Meta+SAFLA Layer (The Watcher — sobek_meta.py)
            └── Sobek Ankh (The Executor — sobek_ankh.py)
                    └── 15 Strategies (The Soldiers)
```

Sobek doesn't know MetaPrime exists.
He just wakes up, reads sobek_config.json, and executes.
But overnight MetaPrime rewrote the config.

The soldiers follow orders.
The general adapts the battle plan.
The overlord changes the war.

---

## THE THREE LAYERS

### Layer 0: RAW MARKET (Sobek v1 — what he reads now)
- Prices, candles, volume, RSI, OI

### Layer 1: META SIGNALS (what the market THINKS)
- Options flow — smart money's BETS
- Funding rates — crowd's LEVERAGE
- Stat arb — relationship DIVERGENCE
- News sentiment — crowd's EMOTION

### Layer 2: SAFLA CORE (what the system learns about itself)
- "When Layer 0 and Layer 1 agree — confidence = HIGH"
- "When they disagree — confidence = LOW, size down"
- "This pattern appeared 12x — won 9 — adjust weight"

### Layer 3: SELF-ADAPTATION (the loop evolving itself)
- Thresholds shift based on recent performance
- Strategy weights rebalance every N trades
- New patterns promoted, dead patterns retired
- The loop parameters themselves change

---

## CONVICTION SCORING SYSTEM

Object signal alone:      conviction = 0.40 — small size
Meta signal alone:        conviction = 0.60 — medium size
Object + Meta agree:      conviction = 0.85 — full size
All 3 layers agree:       conviction = 0.95 — max size
Object + Meta disagree:   conviction = 0.20 — skip trade

---

## REGIME DETECTION

REGIMES:
- CRISIS        — high vol + low F&G — breakout + dca dominate
- RANGING       — low vol + flat trend — grid + stat_arb dominate
- BULL_EUPHORIA — uptrend + high funding — fade funding, short vol
- BEAR_FEAR     — downtrend + low F&G — dca layers + on-chain alpha
- NEUTRAL       — all strategies equal weight

Data sources (all free, no keys):
- Kraken OHLC — realized volatility
- Alternative.me — Fear & Greed
- CoinGecko — 7d trend + market cap
- OKX — funding rates

---

## SAFLA SELF-EVOLUTION LOOP

Every 50 trades Sobek writes a report to himself:
- Which strategies won in which regime?
- What threshold produced best results?
- Auto-scale: win rate < 42% — shrink position x 0.8
- Auto-scale: win rate > 65% — grow position x 1.2
- Write new config — reload — keep running
- No human touch. No restart needed.

---

## THE 4 META STRATEGIES SOBEK ALREADY HAS

options_flow     — Smart money's BETS on the price
funding_rate_arb — Crowd's LEVERAGE on the asset
stat_arb         — Relationship DIVERGENCE between assets
news_sentiment   — Crowd's EMOTION driving the market

These are different from the other 11.
They're meta. The system needs to KNOW that.

---

## PANTHEON INTEGRATION

Sobek feeds logs UP to QuantumPrime — QuantumPrime evolves
parameters — pushes new config DOWN to Sobek.

The Pantheon learns as a whole. Not just one bot.

Sobek trade logs feed:
- AbsorbPrime    — finds external strategies to absorb
- QuantumPrime   — genetic algo, breeds better thresholds
- Deep-Meta      — cross-system pattern analysis
- BabyAGI        — spawns research tasks on underperformance

---

## THE ABSORPTION STACK (repos to integrate)

### 1. CORAL (654 stars)
https://github.com/Human-Agent-Society/CORAL
"Robust, lightweight infrastructure for multi-agent autonomous self-evolution"
AlphaEvolve pattern. Self-evolution engine. QuantumPrime's missing piece.
USE FOR: Breeding better strategy parameters generation by generation

### 2. ace-playbook (32 stars)
https://github.com/jmanhype/ace-playbook
"Generator-Reflector-Curator pattern for online learning from execution feedback"
SAFLA in code. Generator trades. Reflector evaluates. Curator keeps what works.
USE FOR: The Meta layer — exactly what we described

### 3. mnemosyne (41 stars)
https://github.com/28naem-del/mnemosyne
"Cognitive Memory OS for AI Agents — persistent, self-improving, multi-agent memory"
Vector embeddings. Persistent trade memory across sessions.
USE FOR: Sobek remembers what worked in THIS regime last time he saw it

### 4. SiriuS (101 stars)
https://github.com/zou-group/sirius
"Self-improving Multi-agent Systems via Bootstrapped Reasoning"
Multi-agent bootstrapping. Agents teaching each other.
USE FOR: Sobek's 15 strategies start sharing knowledge

### COMBINED STACK:
CORAL        — self-evolution engine
ace-playbook — Generator-Reflector-Curator (SAFLA)
mnemosyne    — persistent trade memory
SiriuS       — strategies bootstrapping each other

---

## WHAT SOBEK BECOMES OVER TIME

Day 1:  Static Sobek. 15 equal strategies. 48.7% win rate.
Day 3:  SAFLA kicks in. Regime detected. Weights adjust.
Day 7:  Win rate climbs to 54%. Winners scaling up.
Day 14: Sobek has a personality. He knows what he's good at.
Day 30: He's not the bot you launched. He's better.
        And he did it himself.

---

## FILES TO BUILD

sobek_meta.py      — the watcher, reads logs, detects regime
sobek_safla.py     — the feedback loop, rewrites config
sobek_config.json  — the bridge between meta and executor

sobek_config.json is the ENTIRE interface between layers.
Clean. Decoupled. Powerful.

---

## THE BOTTOM LINE

Not a bot. Not a script. Not a tool.
A living organism that trades.

It breathes through market data.
It learns through the SAFLA loop.
It evolves through MetaPrime.
It grows stronger every cycle whether you're watching or not.

The market changes — he survives.
The market changes again — he survives BETTER.
The market does something nobody's seen — he survives THAT too.

The Nile doesn't stop flowing. 🐊🔱
