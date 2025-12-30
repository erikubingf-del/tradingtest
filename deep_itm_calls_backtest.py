#!/usr/bin/env python3
"""
DEEP IN-THE-MONEY CALLS AS LEVERAGE

The problem with leveraged ETFs:
  - Daily rebalancing causes volatility decay
  - 3x ETF can go to zero in extreme moves
  - Losses compound faster than gains

The problem with ATM calls:
  - High theta decay (time value erodes quickly)
  - Premium is expensive

SOLUTION: Deep ITM Calls
  - Strike price well BELOW current price (e.g., 20% ITM)
  - Delta close to 1.0 (moves $1 for $1 with stock)
  - Mostly intrinsic value, minimal time value decay
  - Lower capital requirement = built-in leverage
  - MAX LOSS = premium paid (capped!)

Example:
  Stock at $100, buy $80 strike call for $22 (intrinsic $20 + $2 time)
  - If stock goes to $120: Call worth $40 = +82% return
  - If stock goes to $80: Call worth ~$2 = -91% return
  - If stock goes to $60: Call worth $0 = -100% but capped at $22!

Compare to 2x leveraged ETF:
  - Stock $100 -> $120 (+20%): 2x ETF +40%
  - Stock $100 -> $80 (-20%): 2x ETF -40%
  - Stock $100 -> $60 (-40%): 2x ETF -80%

The call gives BETTER upside and CAPPED downside!
"""

import pandas as pd
import numpy as np
import zipfile
from scipy.stats import norm

def black_scholes_call(S, K, T, r, sigma):
    """Calculate call option price"""
    if T <= 0:
        return max(0, S - K)
    if sigma <= 0:
        sigma = 0.01
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    return S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)

def call_delta(S, K, T, r, sigma):
    """Calculate call delta"""
    if T <= 0:
        return 1.0 if S > K else 0.0
    if sigma <= 0:
        sigma = 0.01
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    return norm.cdf(d1)

PARAMS = {
    # Entry criteria
    'mom_12m_min': 0.10,
    'mom_6m_min': 0.05,
    'mom_3m_min': 0.02,
    'mom_1m_min': 0.01,
    'min_signals': 3,

    # Deep ITM Call parameters
    'itm_depth': 0.20,           # 20% in-the-money
    'call_expiry_months': 6,     # 6-month LEAPS
    'risk_free_rate': 0.03,

    # When to use calls (for leveraged positions)
    'use_calls_for_leverage': 1.5,  # Use calls when target leverage >= 1.5x

    # Exits
    'trailing_atr_base': 2.0,
    'trailing_atr_leveraged': 1.5,

    # Portfolio
    'position_size': 0.05,
    'max_positions': 12,
    'initial_capital': 100000,
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
        'mom_3m': mom_3m, 'mom_1m': mom_1m, 'golden_cross': golden_cross,
        'breakout': breakout, 'atr': atr, 'hist_vol': hist_vol,
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
    if sc >= 5: return 3.0
    elif sc >= 4: return 2.0
    elif sc >= 3: return 1.5
    return 1.0


class DeepITMCallPosition:
    """Position using deep ITM calls for leverage"""

    def __init__(self, asset, date, price, investment, target_leverage, vol):
        self.asset = asset
        self.entry_date = date
        self.entry_price = price
        self.investment = investment
        self.target_leverage = target_leverage
        self.vol = max(0.15, vol) if not pd.isna(vol) else 0.20

        # Deep ITM: Strike = 80% of current price (20% ITM)
        self.strike = price * (1 - PARAMS['itm_depth'])
        self.expiry_days = PARAMS['call_expiry_months'] * 30
        self.time_to_expiry = self.expiry_days / 365

        # Calculate call price (mostly intrinsic value)
        self.call_price = black_scholes_call(
            price, self.strike, self.time_to_expiry,
            PARAMS['risk_free_rate'], self.vol * 1.1  # Slight IV premium
        )

        # With deep ITM, premium is ~20% of stock price
        # This gives natural leverage: $100 stock exposure for $22 premium = 4.5x
        self.num_contracts = (investment * target_leverage) / (self.call_price * 100)
        self.premium_paid = self.num_contracts * self.call_price * 100

        # Cap at available investment
        if self.premium_paid > investment:
            self.num_contracts = investment / (self.call_price * 100)
            self.premium_paid = investment

        # Effective exposure
        delta = call_delta(price, self.strike, self.time_to_expiry,
                          PARAMS['risk_free_rate'], self.vol * 1.1)
        self.effective_shares = self.num_contracts * 100 * delta
        self.effective_exposure = self.effective_shares * price
        self.actual_leverage = self.effective_exposure / investment

        self.current_value = investment
        self.high_price = price
        self.high_value = investment
        self.days_held = 0

    def update_value(self, current_price, vol):
        self.days_held += 1
        remaining_time = max(0.01, (self.expiry_days - self.days_held) / 365)

        iv = max(0.15, vol * 1.1) if not pd.isna(vol) else 0.20

        current_call_price = black_scholes_call(
            current_price, self.strike, remaining_time,
            PARAMS['risk_free_rate'], iv
        )

        self.current_value = self.num_contracts * current_call_price * 100
        self.high_price = max(self.high_price, current_price)
        self.high_value = max(self.high_value, self.current_value)

        return self.current_value

    def get_pnl_pct(self):
        return (self.current_value / self.premium_paid - 1) if self.premium_paid > 0 else 0

    def needs_roll(self):
        return self.days_held >= self.expiry_days - 10


class StockPosition:
    """Regular stock position (no options)"""

    def __init__(self, asset, date, price, investment, leverage=1.0):
        self.asset = asset
        self.entry_date = date
        self.entry_price = price
        self.investment = investment
        self.leverage = leverage

        self.exposure = investment * leverage
        self.shares = self.exposure / price

        self.current_value = investment
        self.high_price = price
        self.high_value = investment

    def update_value(self, current_price, vol=None):
        stock_value = self.shares * current_price
        pnl = stock_value - self.exposure
        self.current_value = max(0, self.investment + pnl)

        self.high_price = max(self.high_price, current_price)
        self.high_value = max(self.high_value, self.current_value)

        return self.current_value

    def get_pnl_pct(self):
        return (self.current_value / self.investment - 1) if self.investment > 0 else 0

    def needs_roll(self):
        return False


def run_backtest(use_calls=True):
    """Run backtest"""
    print(f"\nLoading data...")
    data = load_data()
    print(f"Loaded {len(data)} assets")

    signals = {name: calculate_signals(p) for name, p in data.items()}

    all_dates = set()
    for sig in signals.values():
        all_dates.update(sig.dropna(subset=['mom_12m']).index)
    dates = sorted([d for d in all_dates if d >= pd.Timestamp('1981-01-01')])

    print(f"Backtesting from {dates[0].date()} to {dates[-1].date()}")

    capital = PARAMS['initial_capital']
    positions = {}
    equity_curve = []
    calls_used = 0

    for date in dates:
        positions_to_close = []

        for asset, pos in positions.items():
            if asset not in signals or date not in signals[asset].index:
                continue

            row = signals[asset].loc[date]
            price = row['close']
            vol = row.get('hist_vol', 0.2)

            if pd.isna(price):
                continue

            pos.update_value(price, vol)

            # Roll calls if needed
            if use_calls and isinstance(pos, DeepITMCallPosition) and pos.needs_roll():
                sc = count_signals(row)
                if sc >= PARAMS['min_signals']:
                    # Roll: close and reopen
                    capital += pos.current_value
                    leverage = get_leverage(sc)
                    new_investment = min(pos.investment, capital * PARAMS['position_size'])
                    new_pos = DeepITMCallPosition(asset, date, price, new_investment, leverage, vol)
                    capital -= new_pos.premium_paid
                    positions[asset] = new_pos
                    continue
                else:
                    positions_to_close.append(asset)
                    continue

            # Exit checks
            should_exit = False
            atr = row['atr']
            if not pd.isna(atr) and atr > 0:
                lev = getattr(pos, 'leverage', 1) or getattr(pos, 'actual_leverage', 1)
                atr_mult = PARAMS['trailing_atr_leveraged'] if lev > 1 else PARAMS['trailing_atr_base']
                if price < pos.high_price - atr_mult * atr:
                    should_exit = True

            if count_signals(row) < 2:
                should_exit = True

            if should_exit:
                positions_to_close.append(asset)

        for asset in positions_to_close:
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

                investment = capital * PARAMS['position_size']
                if investment < 1000:
                    continue

                leverage = get_leverage(sc)
                price = row['close']
                vol = row.get('hist_vol', 0.2)

                if use_calls and leverage >= PARAMS['use_calls_for_leverage']:
                    pos = DeepITMCallPosition(asset, date, price, investment, leverage, vol)
                    capital -= pos.premium_paid
                    calls_used += 1
                else:
                    pos = StockPosition(asset, date, price, investment, leverage)
                    capital -= investment

                positions[asset] = pos

        total = capital + sum(p.current_value for p in positions.values())
        equity_curve.append({'date': date, 'equity': total})

    print(f"Deep ITM calls used: {calls_used}")
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

    return {'cagr': cagr, 'max_dd': max_dd, 'calmar': calmar}


if __name__ == '__main__':
    print("\n" + "="*70)
    print("DEEP ITM CALLS AS LEVERAGE")
    print("="*70)
    print("""
Using deep in-the-money calls instead of leveraged ETFs:

Advantages:
  - Delta ~0.9-1.0 (moves almost $1 for $1 with stock)
  - Low theta decay (mostly intrinsic value)
  - Built-in leverage (control $100 stock for ~$22)
  - MAX LOSS CAPPED at premium paid

Example: Instead of 2x leveraged ETF
  - Buy 20% ITM call for ~22% of stock price
  - Get ~4.5x leverage naturally
  - If crash: Max loss = 100% of premium (not 200%+ with 2x ETF)
""")

    print("\n>>> With DEEP ITM CALLS...")
    calls_eq = run_backtest(use_calls=True)

    print("\n>>> With REGULAR LEVERAGE...")
    stock_eq = run_backtest(use_calls=False)

    print("\n" + "="*70)
    print("RESULTS")
    print("="*70)

    calls_m = metrics(calls_eq, "DEEP ITM CALLS")
    stock_m = metrics(stock_eq, "REGULAR LEVERAGE")

    print("\n" + "="*70)
    print(f"\n{'Metric':<15} {'Calls':<14} {'Regular':<14} {'Diff':<14}")
    print("-"*55)
    print(f"{'CAGR':<15} {calls_m['cagr']*100:>11.2f}% {stock_m['cagr']*100:>11.2f}% {(calls_m['cagr']-stock_m['cagr'])*100:>+11.2f}%")
    print(f"{'Max DD':<15} {calls_m['max_dd']*100:>11.2f}% {stock_m['max_dd']*100:>11.2f}% {(calls_m['max_dd']-stock_m['max_dd'])*100:>+11.2f}%")
    print(f"{'Calmar':<15} {calls_m['calmar']:>11.2f}  {stock_m['calmar']:>11.2f}  {calls_m['calmar']-stock_m['calmar']:>+11.2f}")
