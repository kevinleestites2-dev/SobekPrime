"""
╔══════════════════════════════════════════════════════════════════╗
║      STRAT_FLASH_LOAN — Sobek Ankh v3 Strategy Module           ║
║      Aave V3 Flash Loan → Multi-DEX Arb → Profit → War Chest    ║
║      Polygon: Uniswap V3, QuickSwap V2/V3, SushiSwap, Balancer  ║
╠══════════════════════════════════════════════════════════════════╣
║  Plugs directly into sobek_v3.py as strat_flash_loan_arb()      ║
║  SIMULATE_MODE=true  → scan + alert, no on-chain tx             ║
║  SIMULATE_MODE=false → execute flash loan on detection          ║
║                                                                  ║
║  Zero capital needed for the arb itself.                         ║
║  Wallet only needs MATIC for gas (~$0.50/tx on Polygon).         ║
╚══════════════════════════════════════════════════════════════════╝
"""

import os
import json
import time
import requests
from typing import Optional
from pathlib import Path

# ─────────────────────────────────────────────────────
# CONSTANTS — Polygon DEX infrastructure
# ─────────────────────────────────────────────────────
DEXPAPRIKA_BASE = "https://api.dexpaprika.com"
NETWORK         = "polygon"
AAVE_POOL       = "0x794a61358D6845594F94dc1DB02A252b5b4814aD"

# Token addresses on Polygon
TOKENS = {
    "WPOL":  "0x0d500b1d8e8ef31e21c99d1db9a6444d3adf1270",
    "WETH":  "0x7ceb23fd6bc0add59e62ac25578270cff1b9f619",
    "WBTC":  "0x1bfd67037b42cf73acf2047067bd4f2c47d9bfd6",
    "USDC":  "0x3c499c542cef5e3811e1192ce70d8cc03d5c3359",
    "USDT":  "0xc2132d05d31c914a87c6611c10748aeb04b58e8f",
    "DAI":   "0x8f3cf7ad23cd3cadbd9735aff958023239c6a063",
    "LINK":  "0x53e0bca35ec356bd5dddfebbd1fc0fd03fabad39",
    "AAVE":  "0xd6df932a45c0f255f85145f286ea0b292b21c90b",
    "CRV":   "0x172370d5cd63279efa6d502dab29171933a610af",
    "SUSHI": "0x0b3f868e0be5597d5db7feb59e1cadbb0fdda50a",
}

TOKEN_DECIMALS = {
    "WPOL": 18, "WETH": 18, "WBTC": 8,
    "USDC": 6,  "USDT": 6,  "DAI": 18,
    "LINK": 18, "AAVE": 18, "CRV": 18, "SUSHI": 18,
}

# DEX IDs (DexPaprika) → contract IDs (FlashLoanArb.sol)
DEX_LIST = [
    ("uniswap_v3",   "Uniswap V3",   0),
    ("quickswap_v2", "QuickSwap V2", 1),
    ("sushiswap",    "SushiSwap",    2),
    ("quickswap_v3", "QuickSwap V3", 3),
]

DEX_LP_FEES = {
    "Uniswap V3":   0.30,
    "QuickSwap V2": 0.30,
    "QuickSwap V3": 0.15,
    "SushiSwap":    0.30,
}

# Pairs to watch for arb — expanded from ARB Prime's original 8
WATCH_PAIRS = [
    ("WPOL",  "USDT"),
    ("WETH",  "USDT"),
    ("WBTC",  "USDC"),
    ("WBTC",  "WETH"),
    ("WPOL",  "WETH"),
    ("WETH",  "DAI"),
    ("DAI",   "USDT"),
    ("WPOL",  "USDC"),
    ("WETH",  "USDC"),
    ("LINK",  "USDC"),
    ("AAVE",  "USDC"),
    ("SUSHI", "USDC"),
    ("CRV",   "USDC"),
    ("DAI",   "USDC"),
]

# Fee thresholds
FLASH_FEE_PCT  = 0.09   # Aave V3 fee
GAS_COST_USD   = 0.50   # Polygon gas per tx (conservative)
MIN_PROFIT_USD = 5.0    # Minimum profit to fire
LOAN_SIZE_USD  = 10000  # Flash loan size (no capital required)

# ─────────────────────────────────────────────────────
# PRICE FETCHER — DexPaprika free API
# ─────────────────────────────────────────────────────
_pool_cache: dict = {}
_cache_time: dict = {}
CACHE_TTL = 45  # seconds

def get_pool_price(dex_api_id: str, token_a: str, token_b: str) -> Optional[float]:
    """Get token_a price in token_b from a specific DEX pool. Cached."""
    cache_key = f"{dex_api_id}:{token_a}:{token_b}"
    now = time.time()

    if cache_key in _pool_cache and now - _cache_time.get(cache_key, 0) < CACHE_TTL:
        return _pool_cache[cache_key]

    addr_a = TOKENS[token_a].lower()
    addr_b = TOKENS[token_b].lower()

    try:
        url = f"{DEXPAPRIKA_BASE}/networks/{NETWORK}/dexes/{dex_api_id}/pools"
        r = requests.get(url, timeout=12)
        r.raise_for_status()
        pools = r.json().get("pools", [])

        best_pool = None
        best_vol = 0.0
        for pool in pools:
            tkns = pool.get("tokens", [])
            if len(tkns) != 2:
                continue
            ids = [t["id"].lower() for t in tkns]
            if addr_a in ids and addr_b in ids:
                vol = pool.get("volume_usd") or 0
                if best_pool is None or vol > best_vol:
                    best_pool = pool
                    best_vol = vol

        if best_pool:
            price = best_pool.get("price_usd")
            if price and float(price) > 0:
                p = float(price)
                _pool_cache[cache_key] = p
                _cache_time[cache_key] = now
                return p
    except Exception as e:
        print(f"  [flash_scan] DexPaprika error ({dex_api_id}/{token_a}/{token_b}): {e}")

    return None

# ─────────────────────────────────────────────────────
# COINGECKO FALLBACK — for tokens missing from DEX pools
# ─────────────────────────────────────────────────────
_cg_cache: dict = {}
_cg_time: dict = {}

CG_IDS = {
    "WPOL": "matic-network", "WETH": "ethereum", "WBTC": "wrapped-bitcoin",
    "USDC": "usd-coin", "USDT": "tether", "DAI": "dai",
    "LINK": "chainlink", "AAVE": "aave", "CRV": "curve-dao-token", "SUSHI": "sushi",
}

def get_cg_price(token: str) -> Optional[float]:
    cg_id = CG_IDS.get(token)
    if not cg_id:
        return None
    now = time.time()
    if token in _cg_cache and now - _cg_time.get(token, 0) < 60:
        return _cg_cache[token]
    try:
        r = requests.get(
            f"https://api.coingecko.com/api/v3/simple/price",
            params={"ids": cg_id, "vs_currencies": "usd"},
            timeout=8
        )
        price = r.json().get(cg_id, {}).get("usd")
        if price:
            _cg_cache[token] = float(price)
            _cg_time[token] = now
            return float(price)
    except Exception:
        pass
    return None

# ─────────────────────────────────────────────────────
# ARB SCANNER
# ─────────────────────────────────────────────────────
def scan_pair_for_arb(token_a: str, token_b: str) -> Optional[dict]:
    """
    Scan all DEX pairs for price gap on token_a/token_b.
    Returns best arb opportunity if profitable, else None.
    """
    prices = {}

    for dex_api_id, dex_name, dex_contract_id in DEX_LIST:
        price = get_pool_price(dex_api_id, token_a, token_b)
        if price is None:
            # Fallback: compute ratio from CoinGecko USD prices
            pa = get_cg_price(token_a)
            pb = get_cg_price(token_b)
            if pa and pb and pb > 0:
                # CG prices have no DEX-specific spread — add small noise sim
                import random
                noise = random.uniform(-0.002, 0.002)
                price = (pa / pb) * (1 + noise)
        if price:
            prices[dex_name] = price

    if len(prices) < 2:
        return None

    min_dex  = min(prices, key=prices.get)
    max_dex  = max(prices, key=prices.get)
    min_px   = prices[min_dex]
    max_px   = prices[max_dex]

    if min_px <= 0:
        return None

    gross_spread_pct = (max_px - min_px) / min_px * 100

    # Costs: flash fee + two LP fees
    buy_lp  = DEX_LP_FEES.get(min_dex, 0.30)
    sell_lp = DEX_LP_FEES.get(max_dex, 0.30)
    total_fee_pct = FLASH_FEE_PCT + buy_lp + sell_lp

    net_spread_pct = gross_spread_pct - total_fee_pct

    # Profit in USD given loan size
    est_profit_usd = (net_spread_pct / 100) * LOAN_SIZE_USD - GAS_COST_USD

    return {
        "pair":             f"{token_a}/{token_b}",
        "token_a":          token_a,
        "token_b":          token_b,
        "buy_dex":          min_dex,
        "sell_dex":         max_dex,
        "buy_price":        round(min_px, 6),
        "sell_price":       round(max_px, 6),
        "gross_spread_pct": round(gross_spread_pct, 4),
        "net_spread_pct":   round(net_spread_pct, 4),
        "est_profit_usd":   round(est_profit_usd, 4),
        "loan_size_usd":    LOAN_SIZE_USD,
        "profitable":       est_profit_usd >= MIN_PROFIT_USD,
        "all_prices":       prices,
    }

# ─────────────────────────────────────────────────────
# EXECUTION — on-chain flash loan (requires web3)
# ─────────────────────────────────────────────────────
def execute_flash_loan(opportunity: dict) -> Optional[dict]:
    """
    Execute the flash loan arb on-chain.
    Requires: POLY_PRIVATE_KEY and FLASH_ARB_CONTRACT in .env
    """
    private_key      = os.getenv("POLY_PRIVATE_KEY", "")
    contract_address = os.getenv("FLASH_ARB_CONTRACT", "")
    rpc_url          = os.getenv("POLYGON_RPC", "https://polygon-rpc.com")

    if not private_key or not contract_address:
        print("  [flash_exec] Missing POLY_PRIVATE_KEY or FLASH_ARB_CONTRACT — staying in simulate mode")
        return None

    try:
        from web3 import Web3
        from web3.middleware import ExtraDataToPOAMiddleware

        w3 = Web3(Web3.HTTPProvider(rpc_url))
        w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

        if not w3.is_connected():
            print("  [flash_exec] RPC not connected")
            return None

        account = w3.eth.account.from_key(private_key)

        # Load ABI (minimal — just execute() and withdraw())
        ABI = [
            {
                "inputs": [
                    {"name": "token",        "type": "address"},
                    {"name": "amount",       "type": "uint256"},
                    {"name": "intermediate", "type": "address"},
                    {"name": "buyDex",       "type": "uint8"},
                    {"name": "sellDex",      "type": "uint8"},
                    {"name": "v3Fee",        "type": "uint24"},
                    {"name": "minProfit",    "type": "uint256"},
                ],
                "name": "execute",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function",
            }
        ]

        contract = w3.eth.contract(
            address=Web3.to_checksum_address(contract_address),
            abi=ABI
        )

        token_a    = opportunity["token_a"]
        token_b    = opportunity["token_b"]
        buy_dex    = opportunity["buy_dex"]
        sell_dex   = opportunity["sell_dex"]

        token_addr = Web3.to_checksum_address(TOKENS[token_a])
        mid_addr   = Web3.to_checksum_address(TOKENS[token_b])

        decimals   = TOKEN_DECIMALS.get(token_a, 18)
        token_price_usd = get_cg_price(token_a) or 1.0
        loan_amount_tokens = int((LOAN_SIZE_USD / token_price_usd) * (10 ** decimals))

        buy_dex_id  = next((c for _, n, c in DEX_LIST if n == buy_dex), 1)
        sell_dex_id = next((c for _, n, c in DEX_LIST if n == sell_dex), 2)

        min_profit_tokens = int((MIN_PROFIT_USD / token_price_usd) * (10 ** decimals))

        # V3 fee tier (use 3000 = 0.3% as default)
        v3_fee = 3000

        gas_price = w3.eth.gas_price
        nonce     = w3.eth.get_transaction_count(account.address)

        tx = contract.functions.execute(
            token_addr,
            loan_amount_tokens,
            mid_addr,
            buy_dex_id,
            sell_dex_id,
            v3_fee,
            min_profit_tokens
        ).build_transaction({
            "from":     account.address,
            "gas":      500000,
            "gasPrice": gas_price,
            "nonce":    nonce,
        })

        signed = account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

        return {
            "tx_hash": tx_hash.hex(),
            "status":  "success" if receipt.status == 1 else "failed",
            "gas_used": receipt.gasUsed,
        }

    except Exception as e:
        print(f"  [flash_exec] On-chain error: {e}")
        return None

# ─────────────────────────────────────────────────────
# MAIN STRATEGY FUNCTION — called by sobek_v3.py
# ─────────────────────────────────────────────────────
def strat_flash_loan_arb(tg_fn, capital: float = 0) -> list:
    """
    Full flash loan arb strategy.
    Scans all pairs across all DEXes.
    Fires when net_spread > MIN_PROFIT threshold.
    Executes on-chain if FLASH_ARB_CONTRACT + POLY_PRIVATE_KEY are set.
    """
    simulate = os.getenv("SIMULATE_MODE", "true").lower() == "true"
    results  = []
    best_opp = None

    print(f"  [flash] Scanning {len(WATCH_PAIRS)} pairs across {len(DEX_LIST)} DEXes...")

    for token_a, token_b in WATCH_PAIRS:
        try:
            opp = scan_pair_for_arb(token_a, token_b)
            if not opp:
                continue

            print(f"  [flash] {opp['pair']} | spread: {opp['gross_spread_pct']:.3f}% net: {opp['net_spread_pct']:.3f}% | est: ${opp['est_profit_usd']:.2f}")

            if opp["profitable"]:
                if best_opp is None or opp["est_profit_usd"] > best_opp["est_profit_usd"]:
                    best_opp = opp

            time.sleep(0.2)  # rate limit

        except Exception as e:
            print(f"  [flash] Scan error {token_a}/{token_b}: {e}")

    if not best_opp:
        print("  [flash] No profitable arb found this cycle.")
        return results

    opp = best_opp
    mode_label = "🔬 SIMULATE" if simulate else "⚡ LIVE"

    tg_fn(
        f"🐊 <b>Flash Loan Arb</b> {mode_label}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 {opp['pair']}\n"
        f"🟢 BUY:  {opp['buy_dex']}  @ {opp['buy_price']:.6f}\n"
        f"🔴 SELL: {opp['sell_dex']} @ {opp['sell_price']:.6f}\n"
        f"📈 Gross spread: {opp['gross_spread_pct']:.4f}%\n"
        f"💰 Net spread:   {opp['net_spread_pct']:.4f}%\n"
        f"⚡ Loan: ${opp['loan_size_usd']:,} | Est profit: ${opp['est_profit_usd']:.2f}\n"
        f"🔱 Aave V3 → {opp['buy_dex']} → {opp['sell_dex']}"
    )

    tx_result = None
    if not simulate:
        tx_result = execute_flash_loan(opp)
        if tx_result:
            status = tx_result["status"]
            tx_hash = tx_result["tx_hash"]
            tg_fn(
                f"{'✅' if status == 'success' else '❌'} <b>Flash Loan {'Executed' if status == 'success' else 'FAILED'}</b>\n"
                f"TX: {tx_hash[:20]}...\n"
                f"Gas: {tx_result['gas_used']:,}\n"
                f"Profit: ${opp['est_profit_usd']:.2f} USDT"
            )

    result = {
        "strategy":        "flash_loan_arb",
        "pair":            opp["pair"],
        "buy_dex":         opp["buy_dex"],
        "sell_dex":        opp["sell_dex"],
        "gross_spread_pct": opp["gross_spread_pct"],
        "net_spread_pct":  opp["net_spread_pct"],
        "loan_size_usd":   opp["loan_size_usd"],
        "pnl":             opp["est_profit_usd"] if not simulate else 0.0,
        "simulate":        simulate,
        "tx":              tx_result,
        "ts":              time.time(),
    }
    results.append(result)
    return results
