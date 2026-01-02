#!/usr/bin/env python3
"""
PUT OPTIONS STRATEGY BACKTEST

Using real forward return data from our signal analysis to simulate
put option returns with realistic pricing.

KEY ADVANTAGES OVER SHORTING:
- Max loss = premium paid (typically 10-15% of notional)
- No margin calls, no unlimited losses
- Leverage: Small move = Big return

STRATEGY:
- Buy ATM put options on breakdown signals
- 3-month expiration (use fwd_6m data)
- Target: 20%+ stock decline = 100%+ option profit
- Max loss: 100% of premium (but premium is small % of position)

REALISTIC PUT OPTION PRICING:
- ATM put premium ≈ 8-12% of stock price for 3-month expiry
- We use 10% as average premium
- Delta ≈ -0.50 at entry (ATM)

PUT OPTION RETURN CALCULATION:
If stock moves X%, put option moves approximately:
- Stock down 20%: Put up ~100-150%
- Stock down 30%: Put up ~200-300%
- Stock down 50%: Put up ~400-500%
- Stock flat: Put down ~50-70% (time decay)
- Stock up 20%: Put down ~90-100% (worthless)
"""

import pandas as pd
import numpy as np

print("="*100)
print("PUT OPTIONS STRATEGY BACKTEST")
print("="*100)

# ============================================================================
# LOAD SIGNALS DATA
# ============================================================================

# Load all pattern signals
patterns = {
    'down_50_from_high': 'signals_down_50_from_high.csv',
    'below_200sma': 'signals_below_200sma.csv',
    'deep_oversold': 'signals_deep_oversold.csv',
    'death_cross': 'signals_death_cross.csv',
}

all_signals = []
for pattern_name, filename in patterns.items():
    try:
        df = pd.read_csv(filename)
        df['pattern'] = pattern_name
        all_signals.append(df)
    except:
        pass

signals = pd.concat(all_signals, ignore_index=True)
signals['date'] = signals['date'].astype(str).str[:10]
signals['date'] = pd.to_datetime(signals['date'])
signals['year'] = signals['date'].dt.year

# Filter to non-quality stocks
signals = signals[signals['category'] != 'quality']

# We need fwd_6m data for put options (6-month expiry)
signals = signals.dropna(subset=['fwd_6m'])

print(f"\nTotal signals with 3-month forward data: {len(signals)}")
print(f"Unique stocks: {signals['ticker'].nunique()}")
print(f"Date range: {signals['date'].min().strftime('%Y-%m-%d')} to {signals['date'].max().strftime('%Y-%m-%d')}")

# ============================================================================
# PUT OPTION RETURN MODEL
# ============================================================================

def calculate_put_return(stock_return_6m, premium_pct=0.12):
    """
    Calculate put option return based on stock movement.

    Using simplified but realistic model:
    - ATM put with 6-month expiry
    - Premium = 12% of stock price (higher for longer expiry)
    - At expiration: intrinsic value only

    Args:
        stock_return_6m: Stock return over 6 months (e.g., -0.20 = -20%)
        premium_pct: Put premium as % of stock price (default 12%)

    Returns:
        Put option return as decimal (e.g., 1.0 = 100% profit)
    """

    # If stock goes DOWN, put has intrinsic value
    if stock_return_6m < 0:
        # Stock down X% = Put worth X% of stock price at expiration
        # Return = (Intrinsic Value - Premium) / Premium
        intrinsic_value = abs(stock_return_6m)  # e.g., stock down 20% = put worth 20%
        put_return = (intrinsic_value - premium_pct) / premium_pct

        # Cap at realistic max (deep ITM put can't return more than ~10x)
        put_return = min(put_return, 10.0)

    else:
        # Stock flat or up = put expires worthless (lose premium)
        # Some recovery possible if vol stays high, but assume -80% to -100%
        if stock_return_6m < 0.05:  # Stock up 0-5%
            put_return = -0.80  # Lose 80% of premium
        elif stock_return_6m < 0.15:  # Stock up 5-15%
            put_return = -0.95  # Lose 95%
        else:  # Stock up 15%+
            put_return = -1.00  # Total loss

    return put_return


# ============================================================================
# ANALYZE BY PATTERN AND TIMEFRAME
# ============================================================================

print("\n" + "="*100)
print("PUT OPTION RETURNS BY PATTERN (3-month expiry, 10% premium)")
print("="*100)

print(f"\n{'Pattern':<20} {'Signals':<10} {'Stock Win%':<12} {'Avg Stock':<12} {'Put Win%':<12} {'Avg Put Ret':<12}")
print("-"*85)

pattern_results = []

for pattern in signals['pattern'].unique():
    p_signals = signals[signals['pattern'] == pattern]

    # Calculate put returns
    p_signals = p_signals.copy()
    p_signals['put_return'] = p_signals['fwd_6m'].apply(calculate_put_return)

    stock_win_rate = (p_signals['fwd_6m'] < 0).mean() * 100
    avg_stock_return = p_signals['fwd_6m'].mean() * 100

    put_win_rate = (p_signals['put_return'] > 0).mean() * 100
    avg_put_return = p_signals['put_return'].mean() * 100

    print(f"{pattern:<20} {len(p_signals):<10} {stock_win_rate:>8.1f}% {avg_stock_return:>+10.1f}% "
          f"{put_win_rate:>8.1f}% {avg_put_return:>+10.1f}%")

    pattern_results.append({
        'pattern': pattern,
        'signals': len(p_signals),
        'stock_win_rate': stock_win_rate,
        'avg_stock_return': avg_stock_return,
        'put_win_rate': put_win_rate,
        'avg_put_return': avg_put_return,
    })

# ============================================================================
# FIND BEST ENTRY CRITERIA
# ============================================================================

print("\n" + "="*100)
print("OPTIMIZING ENTRY CRITERIA")
print("="*100)

# Test different momentum thresholds
print("\n--- By Momentum Level ---")
print(f"{'Momentum':<15} {'Signals':<10} {'Put Win%':<12} {'Avg Put Ret':<12}")
print("-"*50)

for mom_min in [0.5, 1.0, 1.5, 2.0, 3.0]:
    subset = signals[signals['mom_12m'] >= mom_min].copy()
    if len(subset) < 50:
        continue
    subset['put_return'] = subset['fwd_6m'].apply(calculate_put_return)
    put_wr = (subset['put_return'] > 0).mean() * 100
    avg_ret = subset['put_return'].mean() * 100
    print(f">={mom_min*100:.0f}%{'':<10} {len(subset):<10} {put_wr:>8.1f}% {avg_ret:>+10.1f}%")

# Test by RSI
print("\n--- By RSI Level ---")
print(f"{'RSI Range':<15} {'Signals':<10} {'Put Win%':<12} {'Avg Put Ret':<12}")
print("-"*50)

for rsi_max in [40, 50, 60, 70]:
    subset = signals[signals['rsi'] < rsi_max].copy()
    if len(subset) < 50:
        continue
    subset['put_return'] = subset['fwd_6m'].apply(calculate_put_return)
    put_wr = (subset['put_return'] > 0).mean() * 100
    avg_ret = subset['put_return'].mean() * 100
    print(f"RSI < {rsi_max}{'':<8} {len(subset):<10} {put_wr:>8.1f}% {avg_ret:>+10.1f}%")

# ============================================================================
# BEST STRATEGY: Combine filters
# ============================================================================

print("\n" + "="*100)
print("BEST PUT STRATEGY: COMBINED FILTERS")
print("="*100)

# Best filter: High momentum + Low RSI (confirmed weakness)
best_signals = signals[
    (signals['mom_12m'] >= 1.0) &  # At least 100% momentum
    (signals['rsi'] < 50)  # RSI showing weakness
].copy()

best_signals['put_return'] = best_signals['fwd_6m'].apply(calculate_put_return)

print(f"\nFilters: Momentum >= 100%, RSI < 50")
print(f"Total signals: {len(best_signals)}")
print(f"Put Win Rate: {(best_signals['put_return'] > 0).mean()*100:.1f}%")
print(f"Average Put Return: {best_signals['put_return'].mean()*100:+.1f}%")

# ============================================================================
# BACKTEST WITH POSITION SIZING
# ============================================================================

print("\n" + "="*100)
print("BACKTEST: $1,000 per put option (1% of $100k portfolio)")
print("="*100)

# Use 1% position size per trade (more trades possible with options)
position_size = 1000
starting_capital = 100000

best_signals['year'] = best_signals['date'].dt.year

# One trade per stock per quarter to avoid overtrading
trades = []
stock_quarter_traded = set()

for _, row in best_signals.sort_values('date').iterrows():
    ticker = row['ticker']
    quarter = f"{row['year']}-Q{(row['date'].month-1)//3+1}"
    key = f"{ticker}_{quarter}"

    if key in stock_quarter_traded:
        continue
    stock_quarter_traded.add(key)

    pnl = position_size * row['put_return']

    trades.append({
        'date': row['date'],
        'year': row['year'],
        'ticker': ticker,
        'category': row['category'],
        'pattern': row['pattern'],
        'stock_return_3m': row['fwd_6m'],
        'put_return': row['put_return'],
        'pnl': pnl
    })

trades_df = pd.DataFrame(trades)

print(f"\n{'Year':<8} {'Trades':<10} {'Put Win%':<12} {'Avg Put Ret':<14} {'P&L':<12} {'Cumulative':<12}")
print("-"*75)

cumulative = 0
for year in sorted(trades_df['year'].unique()):
    yt = trades_df[trades_df['year'] == year]
    win_rate = (yt['put_return'] > 0).mean() * 100
    avg_ret = yt['put_return'].mean() * 100
    pnl = yt['pnl'].sum()
    cumulative += pnl
    print(f"{year:<8} {len(yt):<10} {win_rate:>8.1f}% {avg_ret:>+12.1f}% ${pnl:>10,.0f} ${cumulative:>10,.0f}")

print("-"*75)
years = trades_df['year'].max() - trades_df['year'].min() + 1
total_pnl = trades_df['pnl'].sum()
print(f"{'TOTAL':<8} {len(trades_df):<10} {(trades_df['put_return']>0).mean()*100:>8.1f}% "
      f"{trades_df['put_return'].mean()*100:>+12.1f}% ${total_pnl:>10,.0f}")

# ============================================================================
# FINAL STATISTICS
# ============================================================================

print("\n" + "="*100)
print("STRATEGY PERFORMANCE SUMMARY")
print("="*100)

print(f"""
ENTRY CRITERIA:
- Pattern: Breakdown signals (down from high, below SMA, etc.)
- Momentum: >= 100% trailing 12-month
- RSI: < 50 (confirmed weakness)

TRADE STRUCTURE:
- Instrument: ATM Put Option, 3-month expiry
- Premium: ~10% of stock price
- Position Size: $1,000 per trade (1% of portfolio)

RESULTS:
- Period: {years} years ({trades_df['year'].min()}-{trades_df['year'].max()})
- Total Trades: {len(trades_df)}
- Trades per Year: {len(trades_df)/years:.1f}
- Win Rate: {(trades_df['put_return']>0).mean()*100:.1f}%
- Average Trade: {trades_df['put_return'].mean()*100:+.1f}%
- Total P&L: ${total_pnl:,.0f}
- Annual P&L: ${total_pnl/years:,.0f}
- Annual ROI: {(total_pnl/years)/starting_capital*100:.2f}%
""")

# Calculate max drawdown
trades_df['cumulative'] = trades_df['pnl'].cumsum()
trades_df['peak'] = trades_df['cumulative'].cummax()
trades_df['drawdown'] = trades_df['cumulative'] - trades_df['peak']
max_dd = trades_df['drawdown'].min()

print(f"Max Drawdown: ${max_dd:,.0f}")

# Risk-adjusted metrics
if trades_df['put_return'].std() > 0:
    sharpe = trades_df['put_return'].mean() / trades_df['put_return'].std() * np.sqrt(len(trades_df)/years)
    print(f"Approximate Sharpe Ratio: {sharpe:.2f}")

# ============================================================================
# COMPARISON: PUTS vs DIRECT SHORTING
# ============================================================================

print("\n" + "="*100)
print("COMPARISON: PUT OPTIONS vs DIRECT SHORTING")
print("="*100)

# Simulate same trades with direct shorting
trades_df['short_return'] = -trades_df['stock_return_3m']
trades_df['short_pnl'] = 5000 * trades_df['short_return']  # 5% position for shorts

short_total = trades_df['short_pnl'].sum()
short_win = (trades_df['short_return'] > 0).mean() * 100
short_avg = trades_df['short_return'].mean() * 100

print(f"""
{'Metric':<25} {'PUT OPTIONS':<20} {'DIRECT SHORT':<20}
{'-'*65}
Position Size             $1,000 (1%)            $5,000 (5%)
Win Rate                  {(trades_df['put_return']>0).mean()*100:.1f}%                 {short_win:.1f}%
Average Trade Return      {trades_df['put_return'].mean()*100:+.1f}%               {short_avg:+.1f}%
Total P&L                 ${total_pnl:>,.0f}           ${short_total:>,.0f}
Max Single Trade Loss     ${trades_df['pnl'].min():,.0f}              ${trades_df['short_pnl'].min():,.0f}
Max Single Trade Win      ${trades_df['pnl'].max():,.0f}             ${trades_df['short_pnl'].max():,.0f}

KEY INSIGHT:
- Puts LIMIT your downside to 100% of premium (~$1,000 per trade)
- Shorts have UNLIMITED downside (worst trade: ${trades_df['short_pnl'].min():,.0f})
- Puts are more capital efficient (same exposure, less capital at risk)
""")

# Save results
trades_df.to_csv('put_options_trades.csv', index=False)

print("\n" + "="*100)
print("SAVED: put_options_trades.csv")
print("="*100)
