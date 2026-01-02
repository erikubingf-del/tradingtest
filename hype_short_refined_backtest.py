#!/usr/bin/env python3
"""
HYPE SHORT STRATEGY - REFINED (Wait for Breakdown)

KEY INSIGHT FROM DATA ANALYSIS:
- Entry during run-up = losing strategy (stocks keep going up)
- Entry AFTER breakdown = winning strategy

ENTRY CRITERIA:
1. HYPE stock with 200%+ trailing 12-month momentum
2. Price BELOW 50-day SMA (breakdown signal)
3. RSI < 70 (no longer overbought)

Expected: 67% decline probability at 12M, 52% chance of 50%+ decline

RISK MANAGEMENT:
- Stop Loss: 20% (exit if price rises 20%)
- Profit Target: 50% (take profit at 50% gain)
- Time Exit: 12 months
- Position Size: 5% per trade
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# ============================================================================
# CONFIGURATION
# ============================================================================

HYPE_STOCKS = [
    'ZM', 'PTON', 'DOCU', 'TDOC', 'ROKU',
    'RIVN', 'LCID', 'NKLA',
    'COIN', 'AFRM', 'HOOD', 'UPST', 'SOFI',
    'SNOW', 'PLTR', 'U', 'DASH',
    'BYND', 'CVNA', 'W', 'CHWY',
    'SNAP', 'PINS',
]

# Entry criteria
MOMENTUM_THRESHOLD = 2.0      # 200% trailing 12-month return
MAX_RSI = 70                  # RSI must be below this
REQUIRE_BELOW_50SMA = True    # Must be below 50 SMA

# Risk management
STOP_LOSS = 0.20              # Exit if price rises 20%
PROFIT_TARGET = 0.50          # Exit if price drops 50%
MAX_HOLDING_DAYS = 252        # 12 months max

POSITION_SIZE = 0.05          # 5% of portfolio per trade
MIN_DAYS_BETWEEN_ENTRIES = 60 # Don't re-enter same stock within 60 days

# ============================================================================
# LOAD DATA
# ============================================================================

print("="*100)
print("HYPE SHORT STRATEGY - REFINED (WAIT FOR BREAKDOWN)")
print("="*100)

events = pd.read_csv('individual_stocks_momentum_events.csv')
events['date'] = pd.to_datetime(events['date'].str[:10])

hype_events = events[events['ticker'].isin(HYPE_STOCKS)].copy()
hype_events = hype_events.sort_values('date').reset_index(drop=True)

print(f"\nTotal HYPE stock events: {len(hype_events):,}")
print(f"Date range: {hype_events['date'].min().strftime('%Y-%m-%d')} to {hype_events['date'].max().strftime('%Y-%m-%d')}")

# Filter to breakdown signals only
breakdown_signals = hype_events[
    (hype_events['trailing_12m'] >= MOMENTUM_THRESHOLD) &
    (hype_events['above_50sma'] == False) &
    (hype_events['rsi'] < MAX_RSI)
].copy()

print(f"\nBreakdown signals (200%+ mom, below 50SMA, RSI<70): {len(breakdown_signals):,}")

# ============================================================================
# BACKTEST ENGINE
# ============================================================================

class RefinedShortBacktest:
    def __init__(self, all_events, signals_df, position_size=0.05):
        self.all_events = all_events
        self.signals = signals_df
        self.position_size = position_size
        self.trades = []
        self.active_positions = {}
        self.last_entry_date = {}

    def run_backtest(self):
        """Run backtest on breakdown signals"""

        portfolio_value = 100000
        cash = portfolio_value

        dates = sorted(self.all_events['date'].unique())
        daily_values = []

        for current_date in dates:
            # Check exits
            tickers_to_close = []

            for ticker, pos in self.active_positions.items():
                ticker_events = self.all_events[
                    (self.all_events['ticker'] == ticker) &
                    (self.all_events['date'] == current_date)
                ]

                if len(ticker_events) == 0:
                    continue

                current_price = ticker_events.iloc[0]['price']
                entry_price = pos['entry_price']
                days_held = (current_date - pos['entry_date']).days

                price_change = (current_price - entry_price) / entry_price
                short_return = -price_change

                exit_reason = None

                if price_change >= STOP_LOSS:
                    exit_reason = 'STOP_LOSS'
                elif price_change <= -PROFIT_TARGET:
                    exit_reason = 'PROFIT_TARGET'
                elif days_held >= MAX_HOLDING_DAYS:
                    exit_reason = 'TIME_EXIT'

                if exit_reason:
                    position_value = pos['position_value']
                    pnl = position_value * short_return

                    self.trades.append({
                        'ticker': ticker,
                        'entry_date': pos['entry_date'],
                        'exit_date': current_date,
                        'entry_price': entry_price,
                        'exit_price': current_price,
                        'entry_momentum': pos['entry_momentum'],
                        'days_held': days_held,
                        'return_pct': short_return * 100,
                        'pnl': pnl,
                        'exit_reason': exit_reason,
                    })

                    cash += position_value + pnl
                    tickers_to_close.append(ticker)

            for ticker in tickers_to_close:
                del self.active_positions[ticker]

            # Check for new entries (only on signals)
            today_signals = self.signals[self.signals['date'] == current_date]

            for _, row in today_signals.iterrows():
                ticker = row['ticker']

                # Check if already in position
                if ticker in self.active_positions:
                    continue

                # Check min days between entries
                if ticker in self.last_entry_date:
                    days_since = (current_date - self.last_entry_date[ticker]).days
                    if days_since < MIN_DAYS_BETWEEN_ENTRIES:
                        continue

                # Enter position
                position_value = min(cash * self.position_size, cash * 0.5)
                if position_value < 1000:
                    continue

                self.active_positions[ticker] = {
                    'entry_date': current_date,
                    'entry_price': row['price'],
                    'entry_momentum': row['trailing_12m'],
                    'position_value': position_value,
                }

                cash -= position_value
                self.last_entry_date[ticker] = current_date

            # Record daily value
            positions_value = sum(pos['position_value'] for pos in self.active_positions.values())
            daily_values.append({
                'date': current_date,
                'portfolio_value': cash + positions_value,
                'cash': cash,
                'positions': len(self.active_positions),
            })

        return pd.DataFrame(daily_values), pd.DataFrame(self.trades)


# ============================================================================
# RUN BACKTEST
# ============================================================================

backtest = RefinedShortBacktest(hype_events, breakdown_signals, POSITION_SIZE)
portfolio_df, trades_df = backtest.run_backtest()

print("\n" + "="*100)
print("BACKTEST RESULTS - REFINED STRATEGY")
print("="*100)

if len(trades_df) == 0:
    print("\nNo trades executed!")
else:
    wins = (trades_df['return_pct'] > 0).sum()
    losses = (trades_df['return_pct'] <= 0).sum()

    print(f"\nTotal trades: {len(trades_df)}")
    print(f"Winning trades: {wins} ({wins/len(trades_df)*100:.1f}%)")
    print(f"Losing trades: {losses} ({losses/len(trades_df)*100:.1f}%)")

    print(f"\nAverage return per trade: {trades_df['return_pct'].mean():+.2f}%")
    print(f"Median return per trade: {trades_df['return_pct'].median():+.2f}%")
    print(f"Best trade: {trades_df['return_pct'].max():+.2f}%")
    print(f"Worst trade: {trades_df['return_pct'].min():+.2f}%")

    print(f"\nTotal P&L: ${trades_df['pnl'].sum():,.0f}")
    print(f"Average holding period: {trades_df['days_held'].mean():.0f} days")

    # Exit reasons
    print("\nExit reasons:")
    for reason in trades_df['exit_reason'].unique():
        count = (trades_df['exit_reason'] == reason).sum()
        avg_ret = trades_df[trades_df['exit_reason'] == reason]['return_pct'].mean()
        print(f"  {reason}: {count} trades, avg return {avg_ret:+.2f}%")

    # Annual breakdown
    print("\n" + "-"*100)
    print("ANNUAL PERFORMANCE")
    print("-"*100)

    trades_df['year'] = pd.to_datetime(trades_df['entry_date']).dt.year

    print(f"\n{'Year':<8} {'Trades':<10} {'Win Rate':<12} {'Avg Return':<14} {'Total P&L':<14} {'P&L %':<10}")
    print("-"*70)

    cumulative_start = 100000
    for year in sorted(trades_df['year'].unique()):
        year_trades = trades_df[trades_df['year'] == year]
        n_trades = len(year_trades)
        win_rate = (year_trades['return_pct'] > 0).mean() * 100
        avg_return = year_trades['return_pct'].mean()
        total_pnl = year_trades['pnl'].sum()
        pnl_pct = (total_pnl / cumulative_start) * 100

        print(f"{year:<8} {n_trades:<10} {win_rate:>8.1f}% {avg_return:>+12.2f}% ${total_pnl:>12,.0f} {pnl_pct:>+8.1f}%")

    # Portfolio summary
    if len(portfolio_df) > 1:
        start_value = 100000
        end_value = portfolio_df.iloc[-1]['portfolio_value']
        total_return = (end_value / start_value - 1) * 100

        years = (portfolio_df['date'].max() - portfolio_df['date'].min()).days / 365
        if years > 0:
            cagr = ((end_value / start_value) ** (1/years) - 1) * 100
        else:
            cagr = 0

        print("\n" + "-"*100)
        print("PORTFOLIO SUMMARY")
        print("-"*100)
        print(f"\nStarting value: ${start_value:,.0f}")
        print(f"Ending value: ${end_value:,.0f}")
        print(f"Total return: {total_return:+.2f}%")
        print(f"CAGR: {cagr:+.2f}%")
        print(f"Period: {years:.1f} years")

        # Annual return on capital
        avg_trades_per_year = len(trades_df) / years
        avg_pnl_per_year = trades_df['pnl'].sum() / years
        annual_roi = (avg_pnl_per_year / start_value) * 100

        print(f"\nAverage trades per year: {avg_trades_per_year:.1f}")
        print(f"Average P&L per year: ${avg_pnl_per_year:,.0f}")
        print(f"Annual ROI (on $100k): {annual_roi:+.2f}%")

    # Trade details
    print("\n" + "-"*100)
    print("ALL TRADES")
    print("-"*100)

    print(f"\n{'Ticker':<8} {'Entry':<12} {'Exit':<12} {'Days':<6} {'Return':<12} {'P&L':<12} {'Reason':<15}")
    print("-"*90)

    for _, trade in trades_df.iterrows():
        print(f"{trade['ticker']:<8} {str(trade['entry_date'])[:10]:<12} {str(trade['exit_date'])[:10]:<12} "
              f"{trade['days_held']:<6} {trade['return_pct']:>+10.2f}% ${trade['pnl']:>10,.0f} {trade['exit_reason']:<15}")

# Save results
trades_df.to_csv('hype_short_refined_trades.csv', index=False)
portfolio_df.to_csv('hype_short_refined_portfolio.csv', index=False)

print("\n" + "="*100)
print("STRATEGY SUMMARY")
print("="*100)
print(f"""
HYPE SHORT STRATEGY - REFINED RULES:

ENTRY CRITERIA (Wait for Breakdown):
✓ HYPE stock (unprofitable, high P/S, recent IPO)
✓ 200%+ trailing 12-month momentum
✓ Price BELOW 50-day SMA (breakdown signal)
✓ RSI < 70 (no longer overbought)

RISK MANAGEMENT:
✓ Stop Loss: 20% (exit if price rises 20%)
✓ Profit Target: 50% (exit if price drops 50%)
✓ Time Exit: 12 months max
✓ Position Size: 5% per trade
✓ Min 60 days between re-entries on same stock

EXPECTED EDGE (from data analysis):
✓ 67% probability of decline at 12 months
✓ 52% probability of 50%+ decline
""")
