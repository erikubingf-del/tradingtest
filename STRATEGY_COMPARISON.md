# Strategy Comparison & Recommendation

## Backtest Results (2021-2025, ~4 Years)

| Strategy | Assets | Profit % | CAGR | Trades | Win Rate | Max DD | Sharpe |
|----------|--------|----------|------|--------|----------|--------|--------|
| **BTCRegimeHold4h** | BTC only | **+536%** | **44.86%** | 39 | 30.8% | 57.67% | 0.10 |
| TrendFollowingMulti | 10 assets | +236% | 27.50% | 1390 | 66.8% | 25.91% | 0.91 |
| RegimeFollowMulti | 10 assets | +192% | 23.91% | 538 | 17.8% | 84.76% | 0.22 |

---

## Key Findings

### 1. BTC-Only Outperforms Multi-Asset

The simple 233 SMA crossover on BTC alone (+536%) beats both multi-asset strategies. This is because:
- BTC has the strongest momentum effect in crypto
- Clearer trend cycles (4-year halving cycle)
- Most liquid, lowest manipulation risk

### 2. Why Multi-Asset Underperforms

**Different assets have wildly different performance:**

| Asset | RegimeFollowMulti | Note |
|-------|-------------------|------|
| DOGE | +173% | Meme coin volatility captured one massive move |
| BTC | +85% | Consistent performer |
| AVAX | +47% | Decent |
| SOL | +26% | Okay |
| BNB | +20% | Okay |
| ETH | +19% | Underwhelming |
| XRP | -25% | Loser |
| DOT | -41% | Loser |
| LINK | -52% | Loser |
| ADA | -62% | Loser |

**6 out of 10 assets were losers or marginal.**

### 3. Statistical Basis for Trend Following

Academic research supports trend following, but with caveats:

| Study | Finding | Implication |
|-------|---------|-------------|
| Moskowitz et al. (2012) | Time-series momentum works across assets | Works on liquid assets |
| Hurst et al. (2017) | 137-year track record | Very long-term edge |
| AQR Research | Works best during crisis periods | Shorts profit during bear markets |

**Key insight:** The momentum effect is real but:
- Strongest on high-liquidity assets (BTC, major indices)
- Works better with longer timeframes (not day trading)
- Requires patience (low win rate, big winners)

---

## Recommendation: Optimal Solution

### Primary Strategy: BTCRegimeHold4h (BTC Only)

**Why:**
- Highest absolute returns (+536% vs +236%)
- Simpler to manage (1 asset, ~8 trades/year)
- BTC has the clearest trend cycles
- 2x leverage amplifies gains during bull regime

**Risk:** Higher drawdown (57%) - must have stomach for it.

### Secondary Strategy: Selective Multi-Asset

If you want diversification, use RegimeFollowMulti on **selected assets only**:

**Include:**
- BTC/USDT:USDT (best performer)
- ETH/USDT:USDT (second largest)
- SOL/USDT:USDT (newer layer-1, strong momentum)

**Exclude:**
- Meme coins (DOGE) - too unpredictable
- Old altcoins (XRP, ADA, DOT, LINK) - weaker trends

### Hybrid Approach

Use **70% capital on BTC** + **30% split across ETH/SOL**:

```
Portfolio Allocation:
├── 70% → BTCRegimeHold4h (BTC only, 95% position)
└── 30% → RegimeFollowMulti (ETH + SOL only)
```

This gives you:
- Primary exposure to best-performing asset (BTC)
- Some diversification into layer-1 ecosystem
- Reduced drawdown vs 100% BTC

---

## Strategy Files

| File | Description | Use Case |
|------|-------------|----------|
| `BTCRegimeHold4h.py` | BTC-only regime strategy | **Primary - Best returns** |
| `RegimeFollowMulti.py` | Multi-asset regime strategy | Diversification |
| `TrendFollowingMulti.py` | Academic trend following | Research/comparison |

---

## Implementation Checklist

### To Run BTC-Only Strategy:
```bash
./start_bot.sh
# Uses config-production.json with BTCRegimeHold4h
```

### To Run Multi-Asset Strategy:
1. Edit `config-multi-asset.json`:
   - Add your API keys
   - Reduce pair_whitelist to: `["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"]`

2. Run:
```bash
freqtrade trade -c config-multi-asset.json --strategy RegimeFollowMulti
```

---

## Final Notes

### Why Simple Works

The 233 SMA crossover is not sophisticated, but:
1. **Robust** - Works across decades of data
2. **Low overfitting** - Only 2 parameters (MA period, buffer)
3. **Clear rules** - No ambiguity in execution
4. **Trend capture** - Rides entire bull runs

### Why Complex Often Fails

TrendFollowingMulti had more indicators but:
1. **More parameters** - Higher overfitting risk
2. **Conflicting signals** - ADX, volume, breakout don't always agree
3. **Over-trading** - 1390 trades vs 39 trades

**Occam's Razor applies:** The simplest strategy that works is usually best.

---

## Disclaimer

- Past performance does not guarantee future results
- All strategies had significant drawdowns (25-85%)
- Backtest results are hypothetical
- Use position sizing and risk management
- Never invest more than you can afford to lose
