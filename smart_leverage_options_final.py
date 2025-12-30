#!/usr/bin/env python3
"""
SMART LEVERAGE + DEEP ITM CALLS

Final implementation combining:
1. Original Smart Leverage entry/exit logic
2. Deep ITM calls for leveraged positions (caps max loss)

Goal: Keep ~20% CAGR while reducing max drawdown below 50%
"""

import pandas as pd
import numpy as np
import zipfile
from scipy.stats import norm

def black_scholes_call(S, K, T, r, sigma):
    if T <= 0:
        return max(0, S - K)
    if sigma <= 0:
        sigma = 0.01
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    return max(0, S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2))

# EXACT Smart Leverage parameters
PARAMS = {
    'mom_12m_min': 0.10,
    'mom_6m_min': 0.05,
    'mom_3m_min': 0.02,
    'mom_1m_min': 0.01,
    'min_signals': 3,

    'leverage_tier_1': 1.0,
    'leverage_tier_2': 1.5,
    'leverage_tier_3': 2.0,
    'leverage_tier_4': 3.0,

    'deleverage_pullback': 0.02,
    'deleverage_mom_decay': 0.40,
    'stop_loss': -0.04,
    'trailing_atr_base': 2.0,
    'trailing_atr_leveraged': 1.5,

    'position_size': 0.05,
    'max_positions': 12,
    'initial_capital': 100000,

    # Deep ITM call parameters
    'itm_depth': 0.25,           # 25% ITM for higher delta
    'call_expiry_months': 6,
    'risk_free_rate': 0.03,
    'use_calls_threshold': 1.5,  # Use calls when leverage >= 1.5
}

ASSETS = [
    'SP500', 'NASDAQ', 'DOW', 'RUSSELL2000',
    'DAX', 'FTSE', 'NIKKEI', 'HANGSENG',
    'GOLD', 'SILVER', 'PLATINUM', 'COPPER',
    'CRUDE', 'NATGAS',
    'CORN', 'WHEAT', 'SOYBEANS', 'COFFEE', 'SUGAR', 'COTTON',
    'EURUSD', 'GBPUSD', 'USDJPY', 'DXY',
    'XLK', 'XLF', 'XLE', 'XLV',
    'BTC', 'ETH',
]

def load_data():
    data = {}
    with zipfile.ZipFile('historical_data.zip', 'r') as z:
        for name in ASSETS:
            filename = f"historical_data/{name}.csv"
            if filename in z.namelist():
                with z.open(filename) as f:
                    df = pd.read_csv(f, header=0, index_col=0, parse_dates=True, skiprows=[1,2])
                    if all(c in df.columns for c in ['Close', 'High', 'Low']):
                        data[name] = df[['Close', 'High', 'Low']].copy()
                        data[name].columns = ['close', 'high', 'low']
                        data[name] = data[name].dropna()
    return data

def calculate_signals(prices):
    close = prices['close']

    mom_12m = close.pct_change(252)
    mom_6m = close.pct_change(126)
    mom_3m = close.pct_change(63)
    mom_1m = close.pct_change(21)

    sma_50 = close.rolling(50).mean()
    sma_200 = close.rolling(200).mean()
    golden_cross = sma_50 > sma_200

    high_52w = prices['high'].rolling(252).max()
    breakout = close >= high_52w * 0.98

    tr = pd.DataFrame({
        'hl': prices['high'] - prices['low'],
        'hc': abs(prices['high'] - close.shift(1)),
        'lc': abs(prices['low'] - close.shift(1))
    }).max(axis=1)
    atr = tr.rolling(14).mean()

    returns = close.pct_change()
    hist_vol = returns.rolling(63).std() * np.sqrt(252)

    return pd.DataFrame({
        'close': close, 'mom_12m': mom_12m, 'mom_6m': mom_6m,
        'mom_3m': mom_3m, 'mom_1m': mom_1m,
        'golden_cross': golden_cross, 'breakout': breakout,
        'atr': atr, 'hist_vol': hist_vol,
    })

def count_signals(row):
    signals = 0
    if row['mom_12m'] > PARAMS['mom_12m_min']: signals += 1
    if row['mom_6m'] > PARAMS['mom_6m_min']: signals += 1
    if row['mom_3m'] > PARAMS['mom_3m_min']: signals += 1
    if row['mom_1m'] > PARAMS['mom_1m_min']: signals += 1
    if row['golden_cross']: signals += 1
    if row['breakout']: signals += 1
    return signals

def get_leverage(sc):
    if sc >= 5: return PARAMS['leverage_tier_4']
    elif sc >= 4: return PARAMS['leverage_tier_3']
    elif sc >= 3: return PARAMS['leverage_tier_2']
    return PARAMS['leverage_tier_1']


class DeepITMCallPosition:
    """Deep ITM call position - caps downside"""

    def __init__(self, asset, date, price, investment, leverage, vol):
        self.asset = asset
        self.entry_date = date
        self.entry_price = price
        self.base_investment = investment
        self.target_leverage = leverage
        self.vol = max(0.15, vol) if not pd.isna(vol) else 0.20

        # Deep ITM strike
        self.strike = price * (1 - PARAMS['itm_depth'])
        self.expiry_days = PARAMS['call_expiry_months'] * 30
        self.time_to_expiry = self.expiry_days / 365

        # Call price
        iv = self.vol * 1.1
        self.call_price = black_scholes_call(price, self.strike, self.time_to_expiry,
                                             PARAMS['risk_free_rate'], iv)

        # Number of contracts to achieve target leverage
        # Each contract controls 100 shares
        target_exposure = investment * leverage
        shares_needed = target_exposure / price
        self.num_contracts = shares_needed / 100

        # Premium required
        self.premium = self.num_contracts * self.call_price * 100

        # Scale down if premium exceeds investment
        if self.premium > investment * 1.5:  # Allow some extra for leverage
            self.num_contracts = (investment * 1.5) / (self.call_price * 100)
            self.premium = self.num_contracts * self.call_price * 100

        self.total_cost = min(self.premium, investment)
        self.current_value = self.total_cost
        self.high_price = price
        self.high_value = self.total_cost
        self.peak_mom = 0
        self.days_held = 0

    def update(self, price, vol, mom_12m=0):
        self.days_held += 1
        remaining_time = max(0.01, (self.expiry_days - self.days_held) / 365)

        iv = max(0.15, vol * 1.1) if not pd.isna(vol) else 0.20
        call_price = black_scholes_call(price, self.strike, remaining_time,
                                        PARAMS['risk_free_rate'], iv)

        self.current_value = self.num_contracts * call_price * 100
        self.high_price = max(self.high_price, price)
        self.high_value = max(self.high_value, self.current_value)
        self.peak_mom = max(self.peak_mom, mom_12m) if mom_12m > 0 else self.peak_mom

        return self.current_value

    def needs_roll(self):
        return self.days_held >= self.expiry_days - 10

    def should_deleverage(self, price, mom_12m):
        # Pullback from high
        pullback = (self.high_price - price) / self.high_price
        if pullback > PARAMS['deleverage_pullback']:
            return True, 'pullback'

        # Momentum decay
        if self.peak_mom > 0.05 and mom_12m > 0:
            decay = (self.peak_mom - mom_12m) / self.peak_mom
            if decay > PARAMS['deleverage_mom_decay']:
                return True, 'mom_decay'

        return False, None


class StockPosition:
    """Regular stock position (for 1x leverage)"""

    def __init__(self, asset, date, price, investment):
        self.asset = asset
        self.entry_date = date
        self.entry_price = price
        self.base_investment = investment
        self.total_cost = investment
        self.target_leverage = 1.0

        self.shares = investment / price
        self.current_value = investment
        self.high_price = price
        self.high_value = investment
        self.peak_mom = 0

    def update(self, price, vol=None, mom_12m=0):
        self.current_value = self.shares * price
        self.high_price = max(self.high_price, price)
        self.high_value = max(self.high_value, self.current_value)
        self.peak_mom = max(self.peak_mom, mom_12m) if mom_12m > 0 else self.peak_mom
        return self.current_value

    def needs_roll(self):
        return False

    def should_deleverage(self, price, mom_12m):
        return False, None


def run_backtest(use_options=True):
    print(f"\nLoading data...")
    data = load_data()
    print(f"Loaded {len(data)} assets")

    signals = {n: calculate_signals(p) for n, p in data.items()}

    all_dates = set()
    for s in signals.values():
        all_dates.update(s.dropna(subset=['mom_12m']).index)
    dates = sorted([d for d in all_dates if d >= pd.Timestamp('1981-01-01')])

    print(f"Backtesting {dates[0].date()} to {dates[-1].date()}")
    mode = "Deep ITM Calls" if use_options else "Regular Leverage"
    print(f"Mode: {mode}")

    capital = PARAMS['initial_capital']
    positions = {}
    equity_curve = []

    for date in dates:
        to_close = []

        for asset, pos in positions.items():
            if asset not in signals or date not in signals[asset].index:
                continue

            row = signals[asset].loc[date]
            price = row['close']
            vol = row.get('hist_vol', 0.2)
            mom = row.get('mom_12m', 0)

            if pd.isna(price):
                continue

            pos.update(price, vol, mom)

            # Roll options if needed
            if use_options and isinstance(pos, DeepITMCallPosition) and pos.needs_roll():
                sc = count_signals(row)
                if sc >= PARAMS['min_signals']:
                    capital += pos.current_value
                    lev = get_leverage(sc)
                    inv = min(pos.base_investment, capital * PARAMS['position_size'])
                    positions[asset] = DeepITMCallPosition(asset, date, price, inv, lev, vol)
                    capital -= positions[asset].total_cost
                    continue
                else:
                    to_close.append(asset)
                    continue

            # Deleverage check (for call positions)
            if use_options and isinstance(pos, DeepITMCallPosition):
                should_del, reason = pos.should_deleverage(price, mom)
                if should_del:
                    # Convert to stock position (deleverage)
                    capital += pos.current_value
                    inv = min(pos.base_investment, pos.current_value)
                    positions[asset] = StockPosition(asset, date, price, inv)
                    capital -= inv
                    continue

            # Exit checks
            should_exit = False

            # ATR trailing stop
            atr = row['atr']
            if not pd.isna(atr) and atr > 0:
                mult = PARAMS['trailing_atr_leveraged'] if pos.target_leverage > 1 else PARAMS['trailing_atr_base']
                if price < pos.high_price - mult * atr:
                    should_exit = True

            # Momentum exit
            if count_signals(row) < 2:
                should_exit = True

            # Stop loss
            pnl = (pos.current_value - pos.total_cost) / pos.total_cost
            if pnl < PARAMS['stop_loss']:
                should_exit = True

            if should_exit:
                to_close.append(asset)

        for asset in to_close:
            if asset in positions:
                capital += positions[asset].current_value
                del positions[asset]

        # New entries
        if len(positions) < PARAMS['max_positions']:
            candidates = []
            for asset in signals:
                if asset in positions or date not in signals[asset].index:
                    continue
                row = signals[asset].loc[date]
                if pd.isna(row['close']) or pd.isna(row['mom_12m']):
                    continue
                sc = count_signals(row)
                if sc >= PARAMS['min_signals']:
                    candidates.append((asset, sc, row['mom_12m'], row))

            candidates.sort(key=lambda x: x[2], reverse=True)

            for asset, sc, mom, row in candidates:
                if len(positions) >= PARAMS['max_positions']:
                    break

                inv = capital * PARAMS['position_size']
                if inv < 1000:
                    continue

                lev = get_leverage(sc)
                price = row['close']
                vol = row.get('hist_vol', 0.2)

                if use_options and lev >= PARAMS['use_calls_threshold']:
                    pos = DeepITMCallPosition(asset, date, price, inv, lev, vol)
                    capital -= pos.total_cost
                else:
                    pos = StockPosition(asset, date, price, inv)
                    capital -= inv

                positions[asset] = pos

        total = capital + sum(p.current_value for p in positions.values())
        equity_curve.append({'date': date, 'equity': total})

    return pd.DataFrame(equity_curve).set_index('date')


def metrics(eq, name):
    e = eq['equity']
    years = (e.index[-1] - e.index[0]).days / 365.25
    cagr = (e.iloc[-1] / e.iloc[0]) ** (1/years) - 1

    dd = (e - e.cummax()) / e.cummax()
    max_dd = dd.min()

    vol = e.pct_change().std() * np.sqrt(252)
    sharpe = (cagr - 0.03) / vol if vol > 0 else 0
    calmar = cagr / abs(max_dd) if max_dd != 0 else 0

    print(f"\n{name}:")
    print(f"  CAGR:         {cagr*100:.2f}%")
    print(f"  Max DD:       {max_dd*100:.2f}%")
    print(f"  Volatility:   {vol*100:.2f}%")
    print(f"  Sharpe:       {sharpe:.2f}")
    print(f"  Calmar:       {calmar:.2f}")

    return {'cagr': cagr, 'max_dd': max_dd, 'calmar': calmar, 'sharpe': sharpe}


if __name__ == '__main__':
    print("\n" + "="*70)
    print("SMART LEVERAGE WITH DEEP ITM CALLS")
    print("="*70)
    print("""
Strategy: Use Deep ITM Calls for leveraged positions
  - Same entry/exit signals as Smart Leverage
  - For 1.5x-3x positions: Use 25% ITM calls instead of leveraged ETFs
  - Benefit: MAX LOSS is capped at premium paid
  - Even in a 50% crash, you can only lose your call premium
""")

    print("\n>>> SMART LEVERAGE + OPTIONS...")
    options_eq = run_backtest(use_options=True)

    print("\n>>> SMART LEVERAGE (ORIGINAL)...")
    regular_eq = run_backtest(use_options=False)

    print("\n" + "="*70)
    print("FINAL COMPARISON")
    print("="*70)

    opt_m = metrics(options_eq, "WITH DEEP ITM CALLS")
    reg_m = metrics(regular_eq, "ORIGINAL (no options)")

    print("\n" + "="*70)
    print(f"\n{'Metric':<15} {'Options':<14} {'Original':<14} {'Change':<14}")
    print("-"*57)
    print(f"{'CAGR':<15} {opt_m['cagr']*100:>11.2f}% {reg_m['cagr']*100:>11.2f}% {(opt_m['cagr']-reg_m['cagr'])*100:>+11.2f}%")
    print(f"{'Max DD':<15} {opt_m['max_dd']*100:>11.2f}% {reg_m['max_dd']*100:>11.2f}% {(opt_m['max_dd']-reg_m['max_dd'])*100:>+11.2f}%")
    print(f"{'Calmar':<15} {opt_m['calmar']:>11.2f}  {reg_m['calmar']:>11.2f}  {opt_m['calmar']-reg_m['calmar']:>+11.2f}")
    print(f"{'Sharpe':<15} {opt_m['sharpe']:>11.2f}  {reg_m['sharpe']:>11.2f}  {opt_m['sharpe']-reg_m['sharpe']:>+11.2f}")

    # Save
    options_eq.to_csv('smart_leverage_options_equity.csv')
    regular_eq.to_csv('smart_leverage_regular_equity.csv')

    print("\n" + "="*70)
    print("CONCLUSION")
    print("="*70)
    if opt_m['calmar'] > reg_m['calmar']:
        print("\nDeep ITM Calls IMPROVED risk-adjusted returns!")
        print(f"Calmar improved from {reg_m['calmar']:.2f} to {opt_m['calmar']:.2f}")
    elif opt_m['max_dd'] > reg_m['max_dd']:  # Less negative = better
        print("\nDeep ITM Calls REDUCED max drawdown!")
        print(f"Max DD improved from {reg_m['max_dd']*100:.1f}% to {opt_m['max_dd']*100:.1f}%")
    else:
        print("\nOptions did not improve performance in this backtest.")
        print("This could be due to rolling costs and timing of entries.")
