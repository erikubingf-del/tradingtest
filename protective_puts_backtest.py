#!/usr/bin/env python3
"""
PROTECTIVE PUTS Strategy for Smart Leverage

Instead of naked leveraged positions, we:
1. Hold the underlying asset (with leverage if desired)
2. BUY PUT OPTIONS as insurance for leveraged positions

This gives us:
- UPSIDE: Full participation in gains (minus put premium)
- DOWNSIDE: Limited to strike price minus premium paid

Think of it as "insurance" - you pay a premium to protect against crashes.
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

def black_scholes_put(S, K, T, r, sigma):
    """
    Calculate put option price using Black-Scholes
    """
    if T <= 0:
        return max(0, K - S)

    if sigma <= 0:
        sigma = 0.01

    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)

    put_price = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
    return max(0, put_price)

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

    # Leverage tiers
    'leverage_tier_1': 1.0,
    'leverage_tier_2': 1.5,
    'leverage_tier_3': 2.0,
    'leverage_tier_4': 3.0,

    # Protective put parameters
    'put_protection_pct': 0.10,     # 10% OTM puts (strike = 90% of entry)
    'put_expiry_months': 3,         # 3-month puts (quarterly)
    'put_cost_budget': 0.02,        # Budget 2% of position for put insurance
    'risk_free_rate': 0.03,
    'iv_multiplier': 1.3,           # IV premium during stress

    # Use puts only for leveraged positions
    'use_puts_above_leverage': 1.0,

    # Exit criteria
    'deleverage_pullback': 0.02,
    'deleverage_mom_decay': 0.40,
    'trailing_atr_base': 2.0,
    'trailing_atr_leveraged': 1.5,

    # Portfolio
    'position_size': 0.05,
    'max_positions': 12,
    'initial_capital': 100000,
}

# Asset universe
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
    hist_vol = returns.rolling(63).std() * np.sqrt(252)

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
        return PARAMS['leverage_tier_4']
    elif signal_count >= 4:
        return PARAMS['leverage_tier_3']
    elif signal_count >= 3:
        return PARAMS['leverage_tier_2']
    else:
        return PARAMS['leverage_tier_1']


class ProtectedPosition:
    """
    Leveraged position with protective put option

    Structure:
    - Long underlying with leverage (e.g., 2x exposure)
    - Long put option as insurance (limits downside)

    Payoff:
    - If price goes UP: Full leveraged gain minus put premium
    - If price goes DOWN: Loss limited to (entry - strike) + premium
    """
    def __init__(self, asset, entry_date, entry_price, investment, leverage, volatility):
        self.asset = asset
        self.entry_date = entry_date
        self.entry_price = entry_price
        self.base_investment = investment
        self.leverage = leverage
        self.volatility = max(0.15, volatility) if not pd.isna(volatility) else 0.25

        # Effective exposure (leveraged)
        self.exposure = investment * leverage
        self.shares = self.exposure / entry_price

        # Protective put parameters
        self.strike = entry_price * (1 - PARAMS['put_protection_pct'])  # 10% OTM
        self.expiry_days = PARAMS['put_expiry_months'] * 30
        self.time_to_expiry = self.expiry_days / 365

        # Calculate put premium
        iv = self.volatility * PARAMS['iv_multiplier']
        put_price = black_scholes_put(entry_price, self.strike, self.time_to_expiry,
                                       PARAMS['risk_free_rate'], iv)

        # Number of puts to cover leveraged position
        # 1 put contract = 100 shares, so we need shares/100 contracts
        self.num_puts = self.shares / 100
        self.put_premium_paid = self.num_puts * put_price * 100

        # Cap put cost at budget percentage
        max_put_cost = investment * PARAMS['put_cost_budget'] * leverage
        if self.put_premium_paid > max_put_cost:
            self.put_premium_paid = max_put_cost

        # Total investment = base + put premium
        self.total_investment = investment + self.put_premium_paid

        # Track values
        self.current_stock_value = self.exposure
        self.current_put_value = self.put_premium_paid
        self.high_price = entry_price
        self.high_value = self.total_investment
        self.days_held = 0

    def update_value(self, current_price, current_vol):
        """Update position value including put protection"""
        self.days_held += 1
        remaining_time = max(0.001, (self.expiry_days - self.days_held) / 365)

        # Stock value (leveraged)
        self.current_stock_value = self.shares * current_price

        # Put value
        iv = max(0.15, current_vol * PARAMS['iv_multiplier']) if not pd.isna(current_vol) else 0.25
        put_price = black_scholes_put(current_price, self.strike, remaining_time,
                                       PARAMS['risk_free_rate'], iv)
        self.current_put_value = self.num_puts * put_price * 100

        # Track high
        self.high_price = max(self.high_price, current_price)

        # Calculate P&L
        stock_pnl = self.current_stock_value - self.exposure
        put_pnl = self.current_put_value - self.put_premium_paid

        # KEY INSIGHT: When stock drops, put gains value (insurance pays out!)
        total_value = self.base_investment + stock_pnl + put_pnl

        # But there's a floor - the put guarantees we can sell at strike
        min_value = self.base_investment - (self.entry_price - self.strike) * self.shares / self.leverage - self.put_premium_paid
        total_value = max(total_value, min_value)

        self.high_value = max(self.high_value, total_value)

        return total_value

    def get_current_value(self):
        stock_pnl = self.current_stock_value - self.exposure
        put_pnl = self.current_put_value - self.put_premium_paid
        total_value = self.base_investment + stock_pnl + put_pnl
        min_value = self.base_investment - (self.entry_price - self.strike) * self.shares / self.leverage - self.put_premium_paid
        return max(total_value, min_value)

    def get_pnl_pct(self):
        return (self.get_current_value() / self.total_investment - 1)

    def needs_roll(self):
        """Check if put needs rolling"""
        return self.days_held >= self.expiry_days - 5

    def max_loss_pct(self):
        """Maximum possible loss percentage (the key benefit!)"""
        # With puts, max loss = move to strike + premium paid
        # As percentage: protection_pct + put_cost_budget
        return PARAMS['put_protection_pct'] + PARAMS['put_cost_budget']


class UnprotectedPosition:
    """Regular leveraged position without put protection"""
    def __init__(self, asset, entry_date, entry_price, investment, leverage):
        self.asset = asset
        self.entry_date = entry_date
        self.entry_price = entry_price
        self.base_investment = investment
        self.leverage = leverage
        self.total_investment = investment

        self.exposure = investment * leverage
        self.shares = self.exposure / entry_price

        self.current_value = investment
        self.high_price = entry_price
        self.high_value = investment

    def update_value(self, current_price, current_vol=None):
        self.current_stock_value = self.shares * current_price
        stock_pnl = self.current_stock_value - self.exposure

        # Leveraged P&L
        self.current_value = self.base_investment + stock_pnl
        self.current_value = max(0, self.current_value)  # Can't go below 0

        self.high_price = max(self.high_price, current_price)
        self.high_value = max(self.high_value, self.current_value)

        return self.current_value

    def get_current_value(self):
        return self.current_value

    def get_pnl_pct(self):
        return (self.current_value / self.total_investment - 1) if self.total_investment > 0 else 0


def run_backtest(use_puts=True):
    """Run the backtest with or without protective puts"""
    print(f"\nLoading data...")
    data = load_data()
    print(f"Loaded {len(data)} assets")

    # Calculate signals
    print("Calculating signals...")
    signals = {}
    for name, prices in data.items():
        signals[name] = calculate_signals(prices)

    # Get common date range
    all_dates = set()
    for name, sig in signals.items():
        all_dates.update(sig.dropna(subset=['mom_12m']).index)
    dates = sorted(all_dates)
    dates = [d for d in dates if d >= pd.Timestamp('1981-01-01')]
    print(f"Backtesting from {dates[0].date()} to {dates[-1].date()}")

    # Portfolio tracking
    capital = PARAMS['initial_capital']
    positions = {}
    equity_curve = []

    for date in dates:
        # Update positions
        positions_to_close = []
        total_position_value = 0

        for asset, pos in positions.items():
            if asset not in signals or date not in signals[asset].index:
                continue

            row = signals[asset].loc[date]
            current_price = row['close']
            current_vol = row.get('hist_vol', 0.25)

            if pd.isna(current_price):
                continue

            pos.update_value(current_price, current_vol)
            current_value = pos.get_current_value()
            total_position_value += current_value

            # Check exit conditions
            should_exit = False
            exit_reason = ""

            # ATR trailing stop
            atr = row['atr']
            if not pd.isna(atr) and atr > 0:
                atr_mult = PARAMS['trailing_atr_leveraged'] if pos.leverage > 1 else PARAMS['trailing_atr_base']
                stop_price = pos.high_price - atr_mult * atr
                if current_price < stop_price:
                    should_exit = True
                    exit_reason = "trailing_stop"

            # Momentum exit
            signal_count = count_signals(row)
            if signal_count < 2:
                should_exit = True
                exit_reason = "momentum_exit"

            # Roll puts if needed (for protected positions)
            if use_puts and isinstance(pos, ProtectedPosition) and pos.needs_roll():
                if not should_exit and signal_count >= PARAMS['min_signals']:
                    # Roll: close and reopen
                    capital += current_value
                    leverage = get_target_leverage(signal_count)
                    new_investment = min(pos.base_investment, capital * PARAMS['position_size'])
                    new_pos = ProtectedPosition(asset, date, current_price, new_investment,
                                                leverage, current_vol)
                    capital -= new_pos.total_investment
                    positions[asset] = new_pos
                    continue

            if should_exit:
                positions_to_close.append((asset, exit_reason))

        # Close positions
        for asset, reason in positions_to_close:
            if asset in positions:
                pos = positions[asset]
                capital += pos.get_current_value()
                del positions[asset]

        # New entries
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

            candidates.sort(key=lambda x: x[2], reverse=True)

            for asset, signal_count, mom, row in candidates:
                if len(positions) >= PARAMS['max_positions']:
                    break

                investment = capital * PARAMS['position_size']
                if investment < 1000:
                    continue

                leverage = get_target_leverage(signal_count)
                current_price = row['close']
                current_vol = row.get('hist_vol', 0.25)

                # Use protective puts for leveraged positions
                if use_puts and leverage > PARAMS['use_puts_above_leverage']:
                    pos = ProtectedPosition(asset, date, current_price, investment,
                                           leverage, current_vol)
                    if pos.total_investment > capital:
                        continue
                    capital -= pos.total_investment
                else:
                    pos = UnprotectedPosition(asset, date, current_price, investment, leverage)
                    capital -= investment

                positions[asset] = pos

        # Total equity
        total_equity = capital + sum(p.get_current_value() for p in positions.values())
        equity_curve.append({'date': date, 'equity': total_equity})

    return pd.DataFrame(equity_curve).set_index('date')


def calculate_metrics(equity_df, name):
    """Calculate performance metrics"""
    equity = equity_df['equity']

    total_return = (equity.iloc[-1] / equity.iloc[0]) - 1
    years = (equity.index[-1] - equity.index[0]).days / 365.25
    cagr = (equity.iloc[-1] / equity.iloc[0]) ** (1/years) - 1

    rolling_max = equity.cummax()
    drawdown = (equity - rolling_max) / rolling_max
    max_dd = drawdown.min()

    daily_returns = equity.pct_change().dropna()
    volatility = daily_returns.std() * np.sqrt(252)

    sharpe = (cagr - 0.03) / volatility if volatility > 0 else 0
    calmar = cagr / abs(max_dd) if max_dd != 0 else 0

    print(f"\n{name}:")
    print(f"  CAGR:           {cagr*100:.2f}%")
    print(f"  Max Drawdown:   {max_dd*100:.2f}%")
    print(f"  Volatility:     {volatility*100:.2f}%")
    print(f"  Sharpe Ratio:   {sharpe:.2f}")
    print(f"  Calmar Ratio:   {calmar:.2f}")

    return {'cagr': cagr, 'max_dd': max_dd, 'volatility': volatility,
            'sharpe': sharpe, 'calmar': calmar}


if __name__ == '__main__':
    print("\n" + "="*70)
    print("PROTECTIVE PUTS STRATEGY BACKTEST")
    print("="*70)
    print("\nConcept: Buy PUT OPTIONS as insurance on leveraged positions")
    print("  - UPSIDE: Full participation in gains (minus small premium)")
    print("  - DOWNSIDE: Limited by put strike price (insurance kicks in)")
    print("="*70)

    # Run with protective puts
    print("\n>>> Running WITH Protective Puts...")
    protected_equity = run_backtest(use_puts=True)

    # Run without puts (original strategy)
    print("\n>>> Running WITHOUT Puts (Original Smart Leverage)...")
    unprotected_equity = run_backtest(use_puts=False)

    print("\n" + "="*70)
    print("COMPARISON RESULTS")
    print("="*70)

    protected_metrics = calculate_metrics(protected_equity, "WITH PROTECTIVE PUTS")
    unprotected_metrics = calculate_metrics(unprotected_equity, "WITHOUT PUTS (Original)")

    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"\n{'Metric':<20} {'With Puts':<15} {'Without Puts':<15} {'Difference':<15}")
    print("-"*65)
    print(f"{'CAGR':<20} {protected_metrics['cagr']*100:>12.2f}% {unprotected_metrics['cagr']*100:>12.2f}% {(protected_metrics['cagr']-unprotected_metrics['cagr'])*100:>+12.2f}%")
    print(f"{'Max Drawdown':<20} {protected_metrics['max_dd']*100:>12.2f}% {unprotected_metrics['max_dd']*100:>12.2f}% {(protected_metrics['max_dd']-unprotected_metrics['max_dd'])*100:>+12.2f}%")
    print(f"{'Calmar Ratio':<20} {protected_metrics['calmar']:>12.2f}  {unprotected_metrics['calmar']:>12.2f}  {protected_metrics['calmar']-unprotected_metrics['calmar']:>+12.2f}")

    # Save
    protected_equity.to_csv('protected_equity_curve.csv')
    unprotected_equity.to_csv('unprotected_equity_curve.csv')

    print("\n" + "="*70)
    print("HOW PROTECTIVE PUTS WORK:")
    print("="*70)
    print("""
EXAMPLE: $10,000 position with 2x leverage at $100/share

WITHOUT PUTS:
  - Exposure: $20,000 (200 shares)
  - If price drops 20% to $80: Loss = 200 × $20 = $4,000 (40% of capital!)
  - If price drops 50% to $50: Loss = 200 × $50 = $10,000 (100% wipeout!)

WITH 10% OTM PROTECTIVE PUTS (Strike = $90):
  - Same exposure: $20,000 (200 shares)
  - Put premium: ~$200 (2% of position)
  - If price drops 20% to $80:
    * Stock loss: $4,000
    * Put gain: 200 × ($90 - $80) = $2,000
    * Net loss: $2,200 (22% vs 40% without puts!)
  - If price drops 50% to $50:
    * Stock loss: $10,000
    * Put gain: 200 × ($90 - $50) = $8,000
    * Net loss: $2,200 (still only 22%! The puts save you!)

TRADE-OFF: You pay ~2% premium per quarter = ~8% per year
But in crashes, this insurance can save you 20-30% or more!
""")
