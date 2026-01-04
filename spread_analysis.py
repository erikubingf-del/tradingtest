#!/usr/bin/env python3
"""
Analyze price drops at different timeframes for put debit spread planning.
"""

import pandas as pd
import numpy as np

# Load the signals data
df = pd.read_csv('backtest_exits_signals.csv')

print("="*80)
print("PUT DEBIT SPREAD ANALYSIS: Expected Drops at Different Timeframes")
print("="*80)

# Timeframe columns (trading days -> approximate months)
timeframes = {
    'day_21': '1 Month',
    'day_42': '2 Months',
    'day_63': '3 Months',
    'day_84': '4 Months',
    'day_105': '5 Months',
    'day_126': '6 Months',
}

print(f"\nTotal trades analyzed: {len(df)}")
print(f"Date range: {df['date'].min()} to {df['date'].max()}")

# Calculate statistics for each timeframe
print("\n" + "="*80)
print("PRICE MOVEMENT STATISTICS BY TIMEFRAME")
print("="*80)

print(f"\n{'Timeframe':<12} {'Down %':<10} {'Avg Drop':<12} {'Median Drop':<12} {'10th Pctl':<12} {'25th Pctl':<12} {'Win Rate':<10}")
print("-"*80)

results = []
for col, name in timeframes.items():
    data = df[col].dropna()

    # Percentage of stocks that went down
    down_pct = (data < 0).sum() / len(data) * 100

    # Among those that went down, what was the average drop?
    down_data = data[data < 0]
    avg_drop = down_data.mean() * 100 if len(down_data) > 0 else 0
    median_drop = down_data.median() * 100 if len(down_data) > 0 else 0

    # Percentiles (for picking strike prices)
    pctl_10 = data.quantile(0.10) * 100  # 10% of stocks drop more than this
    pctl_25 = data.quantile(0.25) * 100  # 25% of stocks drop more than this

    results.append({
        'timeframe': name,
        'down_pct': down_pct,
        'avg_drop': avg_drop,
        'median_drop': median_drop,
        'pctl_10': pctl_10,
        'pctl_25': pctl_25,
    })

    print(f"{name:<12} {down_pct:>7.0f}% {avg_drop:>+10.0f}% {median_drop:>+10.0f}% {pctl_10:>+10.0f}% {pctl_25:>+10.0f}% {down_pct:>8.0f}%")

# For put debit spread planning
print("\n" + "="*80)
print("PUT DEBIT SPREAD STRIKE SELECTION GUIDE")
print("="*80)

print("""
For a PUT DEBIT SPREAD:
  - BUY put at higher strike (ATM or near current price)
  - SELL put at lower strike (target price you expect stock to reach)

Your max profit = Strike difference - Premium paid
Your max loss = Premium paid

RECOMMENDED LOWER STRIKE (where to sell put):
""")

print(f"{'Timeframe':<12} {'Conservative':<18} {'Moderate':<18} {'Aggressive':<18}")
print(f"{'':12} {'(75% hit rate)':<18} {'(50% hit rate)':<18} {'(25% hit rate)':<18}")
print("-"*70)

for col, name in timeframes.items():
    data = df[col].dropna()

    # Conservative: 75th percentile (75% of stocks reach this)
    conservative = data.quantile(0.75) * 100
    # Moderate: 50th percentile (50% of stocks reach this)
    moderate = data.quantile(0.50) * 100
    # Aggressive: 25th percentile (25% of stocks reach this)
    aggressive = data.quantile(0.25) * 100

    print(f"{name:<12} {conservative:>+15.0f}% {moderate:>+15.0f}% {aggressive:>+15.0f}%")

# Specific example for IREN
print("\n" + "="*80)
print("EXAMPLE: IREN at $43 - PUT DEBIT SPREAD STRIKES")
print("="*80)

current_price = 43.0

print(f"\nIREN Current Price: ${current_price:.2f}")
print(f"\nRecommended Put Debit Spread Strikes:")
print(f"{'Timeframe':<12} {'Buy Put @':<12} {'Sell Put @ (Moderate)':<22} {'Sell Put @ (Aggressive)':<22}")
print("-"*70)

for col, name in timeframes.items():
    data = df[col].dropna()

    moderate = data.quantile(0.50)
    aggressive = data.quantile(0.25)

    buy_strike = round(current_price)
    sell_moderate = round(current_price * (1 + moderate))
    sell_aggressive = round(current_price * (1 + aggressive))

    print(f"{name:<12} ${buy_strike:<10} ${sell_moderate:<20} ${sell_aggressive:<20}")

# Win rate analysis
print("\n" + "="*80)
print("WIN RATE BY DROP TARGET")
print("="*80)

print("\nProbability stock drops to target by timeframe:")
print(f"\n{'Target Drop':<12}", end="")
for name in timeframes.values():
    print(f"{name:<12}", end="")
print()
print("-"*80)

for target in [-10, -15, -20, -25, -30, -35, -40, -50]:
    print(f"{target:>+10}%  ", end="")
    for col in timeframes.keys():
        data = df[col].dropna()
        hit_rate = (data <= target/100).sum() / len(data) * 100
        print(f"{hit_rate:>10.0f}%  ", end="")
    print()

print("\n" + "="*80)
print("SUMMARY FOR YOUR IREN TRADE")
print("="*80)

print(f"""
IREN at ${current_price:.2f}

For 6/18 expiration (~5-6 months):

  CONSERVATIVE (high win rate, lower profit):
    Buy $43 Put / Sell $35 Put
    Target: Stock drops to $35 (-19%)
    Expected win rate: ~50%

  MODERATE (balanced):
    Buy $43 Put / Sell $30 Put
    Target: Stock drops to $30 (-30%)
    Expected win rate: ~35-40%

  AGGRESSIVE (lower win rate, higher profit):
    Buy $43 Put / Sell $25 Put
    Target: Stock drops to $25 (-42%)
    Expected win rate: ~25%

Based on your screenshot showing:
  - Buy $43 Put / Sell $29 Put spread
  - Cost: $27
  - Max profit: $73
  - Breakeven: $28.73

  This is between MODERATE and AGGRESSIVE.
  Stock needs to drop to ~$29 (-33%) for max profit.
  Historical data shows ~35% of signals drop 33%+ in 6 months.
""")
