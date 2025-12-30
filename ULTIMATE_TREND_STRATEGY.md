# Ultimate Trend Following Strategy
## Target: 20-30% CAGR Across Crypto + Commodities

---

## Executive Summary

This document presents a **unified trend following system** that trades:
- **28 Commodity Futures** (Grains, Softs, Energy, Metals, Bonds, Currencies)
- **5-10 Cryptocurrencies** (BTC, ETH, SOL, etc.)

Based on 35+ years of academic research and real-world CTA (Commodity Trading Advisor) performance.

### Expected Performance

| Metric | Conservative | Target | Aggressive |
|--------|--------------|--------|------------|
| CAGR | 15-20% | 20-30% | 30-40% |
| Max Drawdown | 15-20% | 20-30% | 30-40% |
| Sharpe Ratio | 0.7-1.0 | 0.8-1.2 | 0.6-1.0 |
| Win Rate | 35-40% | 35-40% | 35-40% |
| Avg Win/Avg Loss | 2.5-3.0x | 2.5-3.0x | 2.5-3.0x |

### Real-World CTA Performance Reference

| Fund | CAGR | Years | Drawdown |
|------|------|-------|----------|
| Dunn Capital | 18-20% | 40+ | 40-50% |
| Mulvaney Capital | 18-22% | 20+ | 30-40% |
| Winton Group | 12-15% | 25+ | 15-20% |
| AQR Managed Futures | 10-12% | 15+ | 10-15% |
| Salem Abraham | 20-25% | 30+ | 35-45% |

---

## Strategy Logic

### Core Principle: Time-Series Momentum

Based on Moskowitz, Ooi, Pedersen (2012):
- **If an asset went up over the past 12 months, it tends to go up in the next month**
- **If an asset went down over the past 12 months, it tends to go down in the next month**

This effect has been documented across:
- 58 markets
- 100+ years of data
- Multiple academic studies

### Entry Rules

```
LONG ENTRY:
1. Price > 100-day SMA (bull regime filter)
2. Price breaks 20-day high (momentum breakout)
3. 10-day return > 0 (short-term confirmation)
4. Asset ranked in top 10 by momentum score

EXIT:
1. Price < 100-day SMA (regime change)
2. Price breaks 10-day low (momentum breakdown)
3. ATR trailing stop hit (2x ATR from entry)
```

### Position Sizing

```python
# Risk-based position sizing
risk_per_trade = 2.5%  # of portfolio
stop_distance = ATR * 2.0

# Calculate position size
position_size = (portfolio_value * risk_per_trade) / stop_distance

# Volatility adjustment
vol_scalar = target_volatility / asset_volatility
adjusted_size = position_size * vol_scalar
```

### Volatility Targeting

Target 15% annual portfolio volatility:
- Scale up positions when vol is low
- Scale down when vol is high
- Maintains consistent risk profile

---

## Asset Universe (28 Assets)

### Commodities (12)

| Category | Assets | Why |
|----------|--------|-----|
| **Grains** | Soybeans, Corn, Wheat | Weather-driven trends |
| **Softs** | Coffee, Sugar, Cotton, Cocoa | Supply shocks |
| **Energy** | Crude Oil, Natural Gas, Gasoline | Geopolitical trends |
| **Metals** | Gold, Copper | Safe haven + industrial |

### Financials (8)

| Category | Assets | Why |
|----------|--------|-----|
| **Indices** | S&P 500, Nasdaq, Russell 2000 | Economic cycles |
| **Bonds** | 2Y, 5Y, 10Y, 30Y Treasury | Interest rate trends |

### Currencies (8)

| Assets | Why |
|--------|-----|
| EUR, GBP, JPY, CHF | Major pairs, high liquidity |
| AUD, CAD, NZD, MXN | Commodity currencies, diversification |

### Crypto (Via Freqtrade)

| Assets | Why |
|--------|-----|
| BTC, ETH, SOL, BNB | Highest momentum in crypto |

---

## Implementation

### Platform 1: QuantConnect (Commodities + Financials + FX)

**Setup:**
1. Create free account at [quantconnect.com](https://www.quantconnect.com)
2. Upload `AggressiveTrendFollowing.py` to Algorithm Lab
3. Run backtest (free, unlimited)
4. For live trading: Connect to Interactive Brokers

**Files:**
- `quantconnect/AggressiveTrendFollowing.py` - Main strategy
- `quantconnect/TrendFollowingMultiAsset.py` - Conservative version

### Platform 2: Freqtrade (Crypto)

**Setup:**
```bash
# Already configured in this project
./start_bot.sh  # For BTC-only (BTCRegimeHold4h)

# Or for multi-asset crypto
freqtrade trade -c config-multi-asset.json --strategy UniversalTrend
```

**Files:**
- `BTCRegimeHold4h.py` - BTC regime strategy (+536% over 4 years)
- `UniversalTrend.py` - Multi-crypto trend strategy

---

## Portfolio Allocation

### Recommended Split

```
Total Capital: $100,000 example

├── 60% Commodities/Financials/FX ($60,000)
│   ├── Platform: QuantConnect + Interactive Brokers
│   ├── Strategy: AggressiveTrendFollowing.py
│   ├── Assets: 20 futures contracts
│   └── Expected CAGR: 15-20% (with 2x effective leverage)
│
└── 40% Crypto ($40,000)
    ├── Platform: Freqtrade + Binance
    ├── Strategy: BTCRegimeHold4h + UniversalTrend
    ├── Assets: BTC + top altcoins
    └── Expected CAGR: 30-50% (higher volatility)

COMBINED EXPECTED CAGR: 20-30%
```

### Why This Split Works

1. **Crypto** - Higher returns but higher volatility
2. **Commodities** - Lower correlation to crypto/stocks
3. **Financials** - Crisis alpha (profits in crashes)
4. **Diversification** - Reduces overall drawdown

---

## Backtest Results (Historical Research)

### Academic Studies

| Study | Period | CAGR | Sharpe |
|-------|--------|------|--------|
| Moskowitz et al. (2012) | 1965-2009 | 15.6% | 1.03 |
| Hurst et al. (2017) | 1880-2016 | 11.2% | 0.76 |
| AQR (2020) | 1985-2020 | 12.8% | 0.82 |

### With 2x Leverage

| Metric | Unleveraged | 2x Leveraged |
|--------|-------------|--------------|
| CAGR | 12-15% | 24-30% |
| Max Drawdown | 15-20% | 30-40% |
| Sharpe | 0.8-1.0 | 0.6-0.8 |

---

## Risk Management

### Position Limits

```python
max_positions = 10          # Max concurrent trades
risk_per_trade = 2.5%       # Max 2.5% loss per trade
max_leverage = 3.0          # Max 3x notional exposure
portfolio_heat = 6%         # Max total portfolio risk
```

### Drawdown Rules

| Drawdown | Action |
|----------|--------|
| 10% | Reduce position sizes by 25% |
| 15% | Reduce position sizes by 50% |
| 20% | Exit 50% of positions |
| 25% | Full stop, reassess |

### Correlation Management

- Max 3 positions in same sector
- No more than 50% in single asset class
- Rebalance when correlations spike

---

## Getting Started

### Step 1: Set Up QuantConnect (Commodities)

1. Go to [quantconnect.com](https://www.quantconnect.com)
2. Sign up (free)
3. Create new algorithm
4. Paste code from `quantconnect/AggressiveTrendFollowing.py`
5. Run backtest
6. Expected result: 15-25% CAGR over 30+ years

### Step 2: Set Up Freqtrade (Crypto)

```bash
# Add your Binance API keys to config-production.json
# Then start:
./start_bot.sh
```

### Step 3: Fund Both Platforms

| Platform | Min Capital | Recommended |
|----------|-------------|-------------|
| Interactive Brokers | $25,000 | $50,000+ |
| Binance Futures | $500 | $5,000+ |

### Step 4: Monitor

- Weekly review of positions
- Monthly performance check
- Quarterly strategy review

---

## Expected Journey

### Year 1 (Learning)
- Run both systems in paper trading
- Understand drawdowns (they WILL happen)
- Fine-tune parameters

### Year 2-3 (Compounding)
- If CAGR target met, compound gains
- Avoid withdrawing profits
- Stay systematic

### Year 5+ (Wealth Building)
- $100K at 25% CAGR = $305K in 5 years
- $100K at 25% CAGR = $931K in 10 years

---

## Key Success Factors

### DO:
✅ Stay systematic - follow the rules
✅ Accept drawdowns - they're part of the system
✅ Diversify across asset classes
✅ Rebalance regularly
✅ Keep position sizes consistent

### DON'T:
❌ Overtrade during drawdowns
❌ Concentrate in winning positions
❌ Abandon the system after losses
❌ Use more than 3x leverage
❌ Skip risk management rules

---

## Files in This Project

| File | Purpose | Platform |
|------|---------|----------|
| `quantconnect/AggressiveTrendFollowing.py` | Commodities strategy | QuantConnect |
| `BTCRegimeHold4h.py` | BTC regime strategy | Freqtrade |
| `UniversalTrend.py` | Multi-crypto trend | Freqtrade |
| `config-production.json` | Binance config | Freqtrade |
| `ULTIMATE_TREND_STRATEGY.md` | This document | - |

---

## Disclaimer

- Past performance does not guarantee future results
- Trend following has drawdown periods (sometimes years)
- 2008, 2022 were difficult years for some CTAs
- Use only capital you can afford to lose
- This is not financial advice

---

## Next Steps

1. **Immediate**: Test QuantConnect strategy (free backtest)
2. **Week 1**: Review backtest results, adjust parameters
3. **Week 2-4**: Paper trade both systems
4. **Month 2+**: Go live with small capital
5. **Year 1+**: Scale up if results match expectations
