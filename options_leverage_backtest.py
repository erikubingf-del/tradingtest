#!/usr/bin/env python3
"""
Options-Enhanced Smart Leverage Strategy Backtest

Instead of using leveraged ETFs/futures for 2x-3x positions,
we use CALL OPTIONS which provide:
- LIMITED DOWNSIDE: Max loss = premium paid
- UNLIMITED UPSIDE: Full participation in gains
- NATURAL LEVERAGE: Delta provides effective leverage

This should theoretically REDUCE max drawdown while maintaining CAGR.
"""

import pandas as pd
import numpy as np
from datetime import datetime
import os
import zipfile
import math
from scipy.stats import norm

# ============================================================================
# BLACK-SCHOLES OPTION PRICING
# ============================================================================

def black_scholes_call(S, K, T, r, sigma):
    """
    Calculate call option price using Black-Scholes
    S: Current stock price
    K: Strike price
    T: Time to expiration (years)
    r: Risk-free rate
    sigma: Volatility (annualized)
    """
    if T <= 0:
        return max(0, S - K)

    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)

    call_price = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
    return call_price

def call_delta(S, K, T, r, sigma):
    """Calculate call option delta"""
    if T <= 0:
        return 1.0 if S > K else 0.0

    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    return norm.cdf(d1)

# ============================================================================
# STRATEGY PARAMETERS
# ============================================================================

PARAMS = {
    # Entry criteria (same as Smart Leverage)
    'mom_12m_min': 0.10,
    'mom_6m_min': 0.05,
    'mom_3m_min': 0.02,
    'mom_1m_min': 0.01,
    'min_signals': 3,

    # Options parameters
    'option_moneyness': 1.0,    # ATM calls (1.0 = at the money)
    'option_expiry_months': 6,  # 6-month options (roll every 6 months)
    'risk_free_rate': 0.03,     # 3% risk-free rate
    'iv_multiplier': 1.2,       # IV typically higher than HV

    # When to use options vs stock
    'use_options_above_leverage': 1.0,  # Use options for all leveraged positions

    # Exit criteria
    'stop_loss': -0.04,
    'trailing_atr_base': 2.0,
    'trailing_atr_leveraged': 1.5,

    # Portfolio
    'position_size': 0.05,
    'max_positions': 12,
    'initial_capital': 100000,
}

# Asset universe - mapped to filenames in the zip
ASSETS = [
    'SP500', 'NASDAQ', 'DOW', 'RUSSELL2000',
    'DAX', 'FTSE', 'NIKKEI', 'HANGSENG',
    'GOLD', 'SILVER', 'PLATINUM', 'COPPER',
    'CRUDE', 'NATGAS',
    'CORN', 'WHEAT', 'SOYBEANS', 'COFFEE', 'SUGAR', 'COTTON',
    'EURUSD', 'GBPUSD', 'USDJPY', 'DXY',
    'XLK', 'XLF', 'XLE', 'XLV',
    'TNOTE10', 'TBOND',
    'BTC', 'ETH',
]

def load_data():
    """Load historical data from zip file"""
    data = {}
    zip_path = 'historical_data.zip'

    with zipfile.ZipFile(zip_path, 'r') as z:
        for name in ASSETS:
            filename = f"historical_data/{name}.csv"

            if filename in z.namelist():
                with z.open(filename) as f:
                    # Skip rows 1 and 2 (ticker info), keep header row 0
                    df = pd.read_csv(f, header=0, index_col=0, parse_dates=True, skiprows=[1,2])

                    if 'Close' in df.columns and 'High' in df.columns and 'Low' in df.columns:
                        data[name] = df[['Close', 'High', 'Low']].copy()
                        data[name].columns = ['close', 'high', 'low']
                        data[name] = data[name].dropna()
                        data[name].index.name = 'date'

    return data

def calculate_signals(prices):
    """Calculate momentum and trend signals"""
    close = prices['close']

    # Momentum signals
    mom_12m = close.pct_change(252)
    mom_6m = close.pct_change(126)
    mom_3m = close.pct_change(63)
    mom_1m = close.pct_change(21)

    # Trend signals
    sma_50 = close.rolling(50).mean()
    sma_200 = close.rolling(200).mean()
    golden_cross = sma_50 > sma_200

    # Donchian breakout
    high_52w = prices['high'].rolling(252).max()
    breakout = close >= high_52w * 0.98

    # ATR for stops
    tr = pd.DataFrame({
        'hl': prices['high'] - prices['low'],
        'hc': abs(prices['high'] - close.shift(1)),
        'lc': abs(prices['low'] - close.shift(1))
    }).max(axis=1)
    atr = tr.rolling(14).mean()

    # Historical volatility for options pricing
    returns = close.pct_change()
    hist_vol = returns.rolling(63).std() * np.sqrt(252)  # Annualized

    return pd.DataFrame({
        'close': close,
        'mom_12m': mom_12m,
        'mom_6m': mom_6m,
        'mom_3m': mom_3m,
        'mom_1m': mom_1m,
        'golden_cross': golden_cross,
        'breakout': breakout,
        'atr': atr,
        'hist_vol': hist_vol,
    })

def count_signals(row):
    """Count entry signals"""
    signals = 0
    if row['mom_12m'] > PARAMS['mom_12m_min']:
        signals += 1
    if row['mom_6m'] > PARAMS['mom_6m_min']:
        signals += 1
    if row['mom_3m'] > PARAMS['mom_3m_min']:
        signals += 1
    if row['mom_1m'] > PARAMS['mom_1m_min']:
        signals += 1
    if row['golden_cross']:
        signals += 1
    if row['breakout']:
        signals += 1
    return signals

def get_target_leverage(signal_count):
    """Determine target leverage based on signal strength"""
    if signal_count >= 5:
        return 3.0
    elif signal_count >= 4:
        return 2.0
    elif signal_count >= 3:
        return 1.5
    else:
        return 1.0

class OptionsPosition:
    """Represents an options position"""
    def __init__(self, asset, entry_date, entry_price, investment, leverage, volatility):
        self.asset = asset
        self.entry_date = entry_date
        self.entry_price = entry_price
        self.investment = investment
        self.target_leverage = leverage
        self.volatility = max(0.15, volatility) if not pd.isna(volatility) else 0.25

        # Calculate option parameters
        self.strike = entry_price * PARAMS['option_moneyness']
        self.expiry_days = PARAMS['option_expiry_months'] * 30
        self.time_to_expiry = self.expiry_days / 365

        # Calculate option price and number of contracts
        iv = self.volatility * PARAMS['iv_multiplier']
        self.option_price = black_scholes_call(
            entry_price, self.strike, self.time_to_expiry,
            PARAMS['risk_free_rate'], iv
        )

        # Premium paid = our investment (max loss is capped here!)
        self.premium_paid = investment
        self.num_contracts = investment / (self.option_price * 100) if self.option_price > 0 else 0

        # Track for P&L
        self.current_value = investment
        self.high_value = investment
        self.days_held = 0

    def update_value(self, current_price, current_vol):
        """Update option value based on current price and time decay"""
        self.days_held += 1
        remaining_time = max(0, (self.expiry_days - self.days_held) / 365)

        iv = max(0.15, current_vol * PARAMS['iv_multiplier']) if not pd.isna(current_vol) else 0.25

        current_option_price = black_scholes_call(
            current_price, self.strike, remaining_time,
            PARAMS['risk_free_rate'], iv
        )

        self.current_value = self.num_contracts * current_option_price * 100
        self.high_value = max(self.high_value, self.current_value)

        return self.current_value

    def get_pnl(self):
        """Get profit/loss"""
        return self.current_value - self.premium_paid

    def get_pnl_pct(self):
        """Get profit/loss percentage"""
        return (self.current_value / self.premium_paid - 1) if self.premium_paid > 0 else 0

    def needs_roll(self):
        """Check if option needs to be rolled (near expiry)"""
        return self.days_held >= self.expiry_days - 10  # Roll 10 days before expiry

    def max_loss(self):
        """Maximum possible loss (the key benefit!)"""
        return self.premium_paid


class StockPosition:
    """Represents a regular stock position (no leverage)"""
    def __init__(self, asset, entry_date, entry_price, investment):
        self.asset = asset
        self.entry_date = entry_date
        self.entry_price = entry_price
        self.investment = investment
        self.shares = investment / entry_price
        self.current_value = investment
        self.high_value = investment
        self.high_price = entry_price

    def update_value(self, current_price, current_vol=None):
        self.current_value = self.shares * current_price
        self.high_value = max(self.high_value, self.current_value)
        self.high_price = max(self.high_price, current_price)
        return self.current_value

    def get_pnl(self):
        return self.current_value - self.investment

    def get_pnl_pct(self):
        return (self.current_value / self.investment - 1) if self.investment > 0 else 0


def run_backtest():
    """Run the options-enhanced backtest"""
    print("Loading data...")
    data = load_data()
    print(f"Loaded {len(data)} assets")

    # Calculate signals for all assets
    print("Calculating signals...")
    signals = {}
    for name, prices in data.items():
        signals[name] = calculate_signals(prices)

    # Get common date range
    all_dates = set()
    for name, sig in signals.items():
        all_dates.update(sig.dropna(subset=['mom_12m']).index)
    dates = sorted(all_dates)

    # Filter to valid backtest period
    dates = [d for d in dates if d >= pd.Timestamp('1981-01-01')]
    print(f"Backtesting from {dates[0].date()} to {dates[-1].date()}")

    # Portfolio tracking
    capital = PARAMS['initial_capital']
    positions = {}  # asset -> Position object (Options or Stock)

    equity_curve = []

    for date in dates:
        # Update all position values
        total_position_value = 0
        positions_to_close = []

        for asset, pos in positions.items():
            if asset not in signals or date not in signals[asset].index:
                continue

            row = signals[asset].loc[date]
            current_price = row['close']
            current_vol = row['hist_vol']

            if pd.isna(current_price):
                continue

            pos.update_value(current_price, current_vol)
            total_position_value += pos.current_value

            # Check exit conditions
            should_exit = False
            exit_reason = ""

            # Stop loss (for options, this is based on premium, not underlying)
            if isinstance(pos, OptionsPosition):
                # Options: exit if lost most of premium OR if underlying drops significantly
                if pos.get_pnl_pct() < -0.80:  # Lost 80% of premium
                    should_exit = True
                    exit_reason = "premium_decay"
                elif pos.needs_roll():
                    # Roll the option if still in trend
                    signal_count = count_signals(row)
                    if signal_count >= PARAMS['min_signals']:
                        # Roll: close current, open new
                        capital += pos.current_value
                        leverage = get_target_leverage(signal_count)
                        new_pos = OptionsPosition(
                            asset, date, current_price,
                            min(pos.premium_paid, capital * PARAMS['position_size']),
                            leverage, current_vol
                        )
                        capital -= new_pos.premium_paid
                        positions[asset] = new_pos
                        continue
                    else:
                        should_exit = True
                        exit_reason = "roll_no_signal"
            else:
                # Stock position: use ATR trailing stop
                atr = row['atr']
                if not pd.isna(atr) and atr > 0:
                    stop_price = pos.high_price - PARAMS['trailing_atr_base'] * atr
                    if current_price < stop_price:
                        should_exit = True
                        exit_reason = "trailing_stop"

            # Momentum exit (applies to both)
            signal_count = count_signals(row)
            if signal_count < 2:  # Lost too many signals
                should_exit = True
                exit_reason = "momentum_exit"

            if should_exit:
                positions_to_close.append((asset, exit_reason))

        # Close positions
        for asset, reason in positions_to_close:
            if asset in positions:
                pos = positions[asset]
                capital += pos.current_value
                del positions[asset]

        # Look for new entries
        if len(positions) < PARAMS['max_positions']:
            candidates = []

            for asset in signals:
                if asset in positions:
                    continue
                if date not in signals[asset].index:
                    continue

                row = signals[asset].loc[date]
                if pd.isna(row['close']) or pd.isna(row['mom_12m']):
                    continue

                signal_count = count_signals(row)
                if signal_count >= PARAMS['min_signals']:
                    candidates.append((asset, signal_count, row['mom_12m'], row))

            # Sort by momentum
            candidates.sort(key=lambda x: x[2], reverse=True)

            # Enter positions
            available_capital = capital
            for asset, signal_count, mom, row in candidates:
                if len(positions) >= PARAMS['max_positions']:
                    break

                investment = min(available_capital * PARAMS['position_size'],
                               available_capital * 0.5)  # Don't use more than 50% on one position

                if investment < 1000:
                    continue

                leverage = get_target_leverage(signal_count)
                current_price = row['close']
                current_vol = row['hist_vol']

                # Use OPTIONS for leveraged positions, STOCK for 1x
                if leverage > PARAMS['use_options_above_leverage']:
                    pos = OptionsPosition(asset, date, current_price, investment, leverage, current_vol)
                else:
                    pos = StockPosition(asset, date, current_price, investment)

                positions[asset] = pos
                capital -= investment
                available_capital -= investment

        # Calculate total equity
        total_equity = capital + sum(p.current_value for p in positions.values())
        equity_curve.append({'date': date, 'equity': total_equity})

    # Create equity DataFrame
    equity_df = pd.DataFrame(equity_curve).set_index('date')

    return equity_df

def run_comparison_backtest():
    """Run both strategies for comparison"""

    # First run: Options-enhanced strategy
    print("\n" + "="*70)
    print("RUNNING OPTIONS-ENHANCED STRATEGY")
    print("="*70)
    options_equity = run_backtest()

    # Now run original strategy (stock + leverage, no options)
    print("\n" + "="*70)
    print("RUNNING ORIGINAL SMART LEVERAGE STRATEGY (for comparison)")
    print("="*70)

    # Temporarily disable options
    original_threshold = PARAMS['use_options_above_leverage']
    PARAMS['use_options_above_leverage'] = 999  # Never use options

    original_equity = run_backtest()

    # Restore
    PARAMS['use_options_above_leverage'] = original_threshold

    return options_equity, original_equity

def calculate_metrics(equity_df, name):
    """Calculate performance metrics"""
    equity = equity_df['equity']

    # Returns
    total_return = (equity.iloc[-1] / equity.iloc[0]) - 1
    years = (equity.index[-1] - equity.index[0]).days / 365.25
    cagr = (equity.iloc[-1] / equity.iloc[0]) ** (1/years) - 1

    # Drawdown
    rolling_max = equity.cummax()
    drawdown = (equity - rolling_max) / rolling_max
    max_dd = drawdown.min()

    # Volatility
    daily_returns = equity.pct_change().dropna()
    volatility = daily_returns.std() * np.sqrt(252)

    # Ratios
    sharpe = (cagr - 0.03) / volatility if volatility > 0 else 0
    calmar = cagr / abs(max_dd) if max_dd != 0 else 0

    print(f"\n{name} Results:")
    print(f"  Total Return:   {total_return*100:,.1f}%")
    print(f"  CAGR:           {cagr*100:.2f}%")
    print(f"  Max Drawdown:   {max_dd*100:.2f}%")
    print(f"  Volatility:     {volatility*100:.2f}%")
    print(f"  Sharpe Ratio:   {sharpe:.2f}")
    print(f"  Calmar Ratio:   {calmar:.2f}")

    return {
        'cagr': cagr,
        'max_dd': max_dd,
        'volatility': volatility,
        'sharpe': sharpe,
        'calmar': calmar,
    }


if __name__ == '__main__':
    print("\n" + "="*70)
    print("OPTIONS-ENHANCED SMART LEVERAGE BACKTEST")
    print("="*70)
    print("\nConcept: Use CALL OPTIONS instead of leveraged positions")
    print("  - Limited downside: Max loss = premium paid")
    print("  - Unlimited upside: Full participation in gains")
    print("  - Natural leverage: Delta provides effective exposure")
    print("="*70)

    options_equity, original_equity = run_comparison_backtest()

    print("\n" + "="*70)
    print("COMPARISON RESULTS")
    print("="*70)

    options_metrics = calculate_metrics(options_equity, "OPTIONS-ENHANCED")
    original_metrics = calculate_metrics(original_equity, "ORIGINAL (Stock + Leverage)")

    print("\n" + "="*70)
    print("SUMMARY COMPARISON")
    print("="*70)
    print(f"\n{'Metric':<20} {'Options':<15} {'Original':<15} {'Difference':<15}")
    print("-"*60)
    print(f"{'CAGR':<20} {options_metrics['cagr']*100:>12.2f}% {original_metrics['cagr']*100:>12.2f}% {(options_metrics['cagr']-original_metrics['cagr'])*100:>+12.2f}%")
    print(f"{'Max Drawdown':<20} {options_metrics['max_dd']*100:>12.2f}% {original_metrics['max_dd']*100:>12.2f}% {(options_metrics['max_dd']-original_metrics['max_dd'])*100:>+12.2f}%")
    print(f"{'Calmar Ratio':<20} {options_metrics['calmar']:>12.2f}  {original_metrics['calmar']:>12.2f}  {options_metrics['calmar']-original_metrics['calmar']:>+12.2f}")
    print(f"{'Sharpe Ratio':<20} {options_metrics['sharpe']:>12.2f}  {original_metrics['sharpe']:>12.2f}  {options_metrics['sharpe']-original_metrics['sharpe']:>+12.2f}")

    # Save results
    options_equity.to_csv('options_equity_curve.csv')
    original_equity.to_csv('original_equity_curve.csv')

    print("\n" + "="*70)
    print("KEY INSIGHT:")
    print("="*70)
    print("""
Options provide ASYMMETRIC payoffs:
  - Your MAX LOSS is capped at the premium paid
  - Your UPSIDE is unlimited (minus theta decay)

In leveraged positions:
  - Original: 2x leverage means 2x losses too
  - Options: Premium is your max loss, regardless of how far it drops

TRADE-OFFS:
  - Options have theta decay (time value erodes)
  - Options require higher IV premiums during crashes
  - Rolling costs add up over time
  - But: Catastrophic loss protection in crashes!
""")
