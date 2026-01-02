#!/usr/bin/env python3
"""
HYPE SHORT STRATEGY BACKTEST

Based on analysis of 15,733 momentum events:
- HYPE stocks with 200%+ momentum have 59% probability of decline at 12 months
- HYPE stocks with 400-500% momentum have 76% probability of decline, 53% down >50%
- Quality stocks with same momentum only 13% decline probability

STRATEGY RULES:
1. ENTRY: HYPE stock with 200%+ trailing 12-month return
2. STOP LOSS: 25% above entry (if stock rises 25%, exit with loss)
3. PROFIT TARGET: 30% below entry (take profit at 30% gain)
4. TIME EXIT: Exit after 6 months if neither target hit
5. POSITION SIZE: 5% of portfolio per trade
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# ============================================================================
# CONFIGURATION
# ============================================================================

# HYPE STOCKS - Must have characteristics: unprofitable, high P/S, recent IPO
HYPE_STOCKS = [
    # COVID bubble
    'ZM', 'PTON', 'DOCU', 'TDOC', 'ROKU',
    # EV bubble
    'RIVN', 'LCID', 'NKLA',
    # Fintech
    'COIN', 'AFRM', 'HOOD', 'UPST', 'SOFI',
    # Speculative tech
    'SNOW', 'PLTR', 'U', 'DASH',
    # Consumer hype
    'BYND', 'CVNA', 'W', 'CHWY',
    # Social
    'SNAP', 'PINS',
]

# Strategy parameters
MOMENTUM_THRESHOLD = 2.0      # 200% trailing 12-month return
STOP_LOSS = 0.25              # Exit if price rises 25% (loss on short)
PROFIT_TARGET = 0.30          # Exit if price drops 30% (profit on short)
MAX_HOLDING_DAYS = 126        # 6 months max holding period
POSITION_SIZE = 0.05          # 5% of portfolio per trade
MIN_DAYS_BETWEEN_ENTRIES = 30 # Don't re-enter same stock within 30 days

# ============================================================================
# LOAD DATA
# ============================================================================

print("="*100)
print("HYPE SHORT STRATEGY BACKTEST")
print("="*100)

events = pd.read_csv('individual_stocks_momentum_events.csv')
events['date'] = pd.to_datetime(events['date'].str[:10])

# Filter to HYPE stocks only
hype_events = events[events['ticker'].isin(HYPE_STOCKS)].copy()
hype_events = hype_events.sort_values('date').reset_index(drop=True)

print(f"\nTotal HYPE stock events: {len(hype_events):,}")
print(f"HYPE stocks in dataset: {hype_events['ticker'].nunique()}")
print(f"Date range: {hype_events['date'].min().strftime('%Y-%m-%d')} to {hype_events['date'].max().strftime('%Y-%m-%d')}")

# ============================================================================
# BACKTEST ENGINE
# ============================================================================

class ShortStrategyBacktest:
    def __init__(self, events_df, position_size=0.05):
        self.events = events_df
        self.position_size = position_size
        self.trades = []
        self.active_positions = {}  # ticker -> entry_info
        self.last_entry_date = {}   # ticker -> last entry date

    def can_enter(self, ticker, date, momentum):
        """Check if we can enter a new short position"""
        # Check momentum threshold
        if momentum < MOMENTUM_THRESHOLD:
            return False

        # Check if already in position
        if ticker in self.active_positions:
            return False

        # Check minimum days between entries
        if ticker in self.last_entry_date:
            days_since = (date - self.last_entry_date[ticker]).days
            if days_since < MIN_DAYS_BETWEEN_ENTRIES:
                return False

        return True

    def run_backtest(self):
        """Run the backtest simulation"""

        # Group events by date for simulation
        dates = self.events['date'].unique()
        dates = sorted(dates)

        portfolio_value = 100000  # Starting capital
        cash = portfolio_value

        daily_values = []

        for current_date in dates:
            # Check for exits on active positions
            tickers_to_close = []

            for ticker, pos in self.active_positions.items():
                # Get current price data for this ticker
                ticker_events = self.events[
                    (self.events['ticker'] == ticker) &
                    (self.events['date'] == current_date)
                ]

                if len(ticker_events) == 0:
                    continue

                current_price = ticker_events.iloc[0]['price']
                entry_price = pos['entry_price']
                days_held = (current_date - pos['entry_date']).days

                # Calculate return (negative = profit for short)
                price_change = (current_price - entry_price) / entry_price
                short_return = -price_change  # Invert for short

                exit_reason = None

                # Check stop loss (price went UP by 25%)
                if price_change >= STOP_LOSS:
                    exit_reason = 'STOP_LOSS'

                # Check profit target (price went DOWN by 30%)
                elif price_change <= -PROFIT_TARGET:
                    exit_reason = 'PROFIT_TARGET'

                # Check time exit
                elif days_held >= MAX_HOLDING_DAYS:
                    exit_reason = 'TIME_EXIT'

                if exit_reason:
                    # Calculate P&L
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

            # Close positions
            for ticker in tickers_to_close:
                del self.active_positions[ticker]

            # Check for new entries
            today_events = self.events[self.events['date'] == current_date]

            for _, row in today_events.iterrows():
                ticker = row['ticker']
                momentum = row['trailing_12m']
                price = row['price']

                # Check entry criteria
                if not self.can_enter(ticker, current_date, momentum):
                    continue

                # Additional filter: RSI > 70 or extension > 75%
                rsi = row.get('rsi', 50)
                extension = row.get('pct_above_200sma', 0)

                if rsi < 70 and extension < 0.75:
                    continue

                # Enter position (limit to available cash)
                position_value = min(cash * self.position_size, cash * 0.95)

                if position_value < 1000:  # Minimum position size
                    continue

                self.active_positions[ticker] = {
                    'entry_date': current_date,
                    'entry_price': price,
                    'entry_momentum': momentum,
                    'position_value': position_value,
                }

                cash -= position_value
                self.last_entry_date[ticker] = current_date

            # Calculate portfolio value
            positions_value = sum(pos['position_value'] for pos in self.active_positions.values())
            total_value = cash + positions_value

            daily_values.append({
                'date': current_date,
                'portfolio_value': total_value,
                'cash': cash,
                'positions': len(self.active_positions),
            })

        return pd.DataFrame(daily_values), pd.DataFrame(self.trades)


# ============================================================================
# RUN BACKTEST
# ============================================================================

backtest = ShortStrategyBacktest(hype_events, position_size=POSITION_SIZE)
portfolio_df, trades_df = backtest.run_backtest()

print("\n" + "="*100)
print("BACKTEST RESULTS")
print("="*100)

if len(trades_df) == 0:
    print("\nNo trades executed! Check the entry criteria.")
else:
    # Trade statistics
    print(f"\nTotal trades: {len(trades_df)}")
    print(f"Winning trades: {(trades_df['return_pct'] > 0).sum()} ({(trades_df['return_pct'] > 0).mean()*100:.1f}%)")
    print(f"Losing trades: {(trades_df['return_pct'] <= 0).sum()} ({(trades_df['return_pct'] <= 0).mean()*100:.1f}%)")

    print(f"\nAverage return per trade: {trades_df['return_pct'].mean():+.2f}%")
    print(f"Median return per trade: {trades_df['return_pct'].median():+.2f}%")
    print(f"Best trade: {trades_df['return_pct'].max():+.2f}%")
    print(f"Worst trade: {trades_df['return_pct'].min():+.2f}%")

    print(f"\nAverage holding period: {trades_df['days_held'].mean():.1f} days")

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

    print(f"\n{'Year':<8} {'Trades':<10} {'Win Rate':<12} {'Avg Return':<14} {'Total P&L':<14}")
    print("-"*60)

    for year in sorted(trades_df['year'].unique()):
        year_trades = trades_df[trades_df['year'] == year]
        n_trades = len(year_trades)
        win_rate = (year_trades['return_pct'] > 0).mean() * 100
        avg_return = year_trades['return_pct'].mean()
        total_pnl = year_trades['pnl'].sum()

        print(f"{year:<8} {n_trades:<10} {win_rate:>8.1f}% {avg_return:>+12.2f}% ${total_pnl:>12,.0f}")

    # Portfolio performance
    if len(portfolio_df) > 1:
        start_value = portfolio_df.iloc[0]['portfolio_value']
        end_value = portfolio_df.iloc[-1]['portfolio_value']
        total_return = (end_value / start_value - 1) * 100

        # Calculate CAGR
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

    # Sample trades
    print("\n" + "-"*100)
    print("SAMPLE TRADES (First 20)")
    print("-"*100)

    print(f"\n{'Ticker':<8} {'Entry Date':<12} {'Exit Date':<12} {'Days':<6} {'Return':<10} {'Reason':<15}")
    print("-"*80)

    for _, trade in trades_df.head(20).iterrows():
        print(f"{trade['ticker']:<8} {str(trade['entry_date'])[:10]:<12} {str(trade['exit_date'])[:10]:<12} "
              f"{trade['days_held']:<6} {trade['return_pct']:>+8.2f}% {trade['exit_reason']:<15}")

# Save results
trades_df.to_csv('hype_short_trades.csv', index=False)
portfolio_df.to_csv('hype_short_portfolio.csv', index=False)

print("\n" + "="*100)
print("STRATEGY SUMMARY")
print("="*100)
print(f"""
HYPE SHORT STRATEGY RULES:
- Entry: HYPE stock (unprofitable, high P/S) with 200%+ momentum, RSI>70 or Extension>75%
- Stop Loss: 25% (exit if price rises 25%)
- Profit Target: 30% (exit if price drops 30%)
- Time Exit: 6 months max holding
- Position Size: 5% per trade

Results saved to:
- hype_short_trades.csv
- hype_short_portfolio.csv
""")
