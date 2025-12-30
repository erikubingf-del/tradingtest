#!/usr/bin/env python3
"""
TACTICAL OPTIONS STRATEGY

The problem with constant put protection:
  - Premiums eat into returns (8%+ per year)
  - 90% of the time markets go up, so insurance is wasted

SOLUTION: Only buy puts when DANGER SIGNALS appear:
  1. Volatility spike (VIX > threshold)
  2. Momentum deteriorating (but not yet exit signal)
  3. Price approaching stop loss

This way we:
  - Save on premium during good times
  - Get protection when it matters most
  - Let trends run without drag
"""

import pandas as pd
import numpy as np
from datetime import datetime
import zipfile
from scipy.stats import norm

# Black-Scholes
def black_scholes_put(S, K, T, r, sigma):
    if T <= 0:
        return max(0, K - S)
    if sigma <= 0:
        sigma = 0.01
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    return max(0, K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1))

PARAMS = {
    # Entry criteria
    'mom_12m_min': 0.10,
    'mom_6m_min': 0.05,
    'mom_3m_min': 0.02,
    'mom_1m_min': 0.01,
    'min_signals': 3,

    # Leverage
    'leverage_tier_1': 1.0,
    'leverage_tier_2': 1.5,
    'leverage_tier_3': 2.0,
    'leverage_tier_4': 3.0,

    # TACTICAL PUT TRIGGERS
    'vol_spike_threshold': 0.35,    # Buy puts when vol > 35%
    'momentum_decay_threshold': 0.5, # Buy puts when momentum decays 50%
    'pullback_warning': 0.015,       # 1.5% pullback triggers protection

    # Put parameters
    'put_otm_pct': 0.05,            # 5% OTM puts
    'put_expiry_days': 21,          # 21-day puts (cheaper, more gamma)
    'risk_free_rate': 0.03,

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
    hist_vol = returns.rolling(21).std() * np.sqrt(252)  # 21-day vol

    # Momentum peak (for decay detection)
    mom_peak = mom_12m.rolling(63).max()

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
        'mom_peak': mom_peak,
    })

def count_signals(row):
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

def get_leverage(signal_count):
    if signal_count >= 5:
        return PARAMS['leverage_tier_4']
    elif signal_count >= 4:
        return PARAMS['leverage_tier_3']
    elif signal_count >= 3:
        return PARAMS['leverage_tier_2']
    return PARAMS['leverage_tier_1']

def should_buy_protection(row, position):
    """Determine if we should buy tactical puts NOW"""
    # Trigger 1: Volatility spike
    if row['hist_vol'] > PARAMS['vol_spike_threshold']:
        return True, "vol_spike"

    # Trigger 2: Momentum decay
    if row['mom_peak'] > 0 and row['mom_12m'] > 0:
        decay = 1 - (row['mom_12m'] / row['mom_peak'])
        if decay > PARAMS['momentum_decay_threshold']:
            return True, "mom_decay"

    # Trigger 3: Price pullback from high
    if position.high_price > 0:
        pullback = (position.high_price - row['close']) / position.high_price
        if pullback > PARAMS['pullback_warning']:
            return True, "pullback"

    return False, None


class TacticalPosition:
    """Position with tactical put buying"""

    def __init__(self, asset, entry_date, entry_price, investment, leverage):
        self.asset = asset
        self.entry_date = entry_date
        self.entry_price = entry_price
        self.investment = investment
        self.leverage = leverage

        self.exposure = investment * leverage
        self.shares = self.exposure / entry_price

        self.current_value = investment
        self.high_price = entry_price
        self.high_value = investment

        # Put protection (initially none)
        self.has_put = False
        self.put_strike = 0
        self.put_value = 0
        self.put_premium = 0
        self.put_expiry = 0
        self.days_held = 0

    def buy_protection(self, current_price, vol, days_remaining=21):
        """Buy a protective put"""
        if self.has_put:
            return 0  # Already protected

        self.put_strike = current_price * (1 - PARAMS['put_otm_pct'])
        self.put_expiry = days_remaining

        iv = max(0.2, vol * 1.2) if not pd.isna(vol) else 0.3
        put_price = black_scholes_put(
            current_price, self.put_strike, days_remaining/365,
            PARAMS['risk_free_rate'], iv
        )

        # Number of puts for our exposure
        num_puts = self.shares / 100
        self.put_premium = num_puts * put_price * 100
        self.put_value = self.put_premium
        self.has_put = True

        return self.put_premium

    def update_value(self, current_price, vol):
        self.days_held += 1

        # Stock value
        stock_value = self.shares * current_price
        stock_pnl = stock_value - self.exposure
        base_value = self.investment + stock_pnl

        # Update put if we have one
        put_pnl = 0
        if self.has_put:
            self.put_expiry -= 1
            if self.put_expiry <= 0:
                # Put expired - check if ITM
                if current_price < self.put_strike:
                    # Put pays out!
                    payout = (self.put_strike - current_price) * self.shares
                    put_pnl = payout - self.put_premium
                else:
                    # Put expired worthless
                    put_pnl = -self.put_premium
                self.has_put = False
                self.put_value = 0
            else:
                # Mark to market
                iv = max(0.2, vol * 1.2) if not pd.isna(vol) else 0.3
                put_price = black_scholes_put(
                    current_price, self.put_strike, self.put_expiry/365,
                    PARAMS['risk_free_rate'], iv
                )
                num_puts = self.shares / 100
                self.put_value = num_puts * put_price * 100
                put_pnl = self.put_value - self.put_premium

        self.current_value = max(0, base_value + put_pnl)
        self.high_price = max(self.high_price, current_price)
        self.high_value = max(self.high_value, self.current_value)

        return self.current_value

    def get_current_value(self):
        return self.current_value


def run_backtest(tactical=True):
    """Run backtest with or without tactical puts"""
    print(f"\nLoading data...")
    data = load_data()
    print(f"Loaded {len(data)} assets")

    signals = {name: calculate_signals(prices) for name, prices in data.items()}

    all_dates = set()
    for sig in signals.values():
        all_dates.update(sig.dropna(subset=['mom_12m']).index)
    dates = sorted([d for d in all_dates if d >= pd.Timestamp('1981-01-01')])

    print(f"Backtesting from {dates[0].date()} to {dates[-1].date()}")

    capital = PARAMS['initial_capital']
    positions = {}
    equity_curve = []
    put_purchases = 0

    for date in dates:
        positions_to_close = []

        for asset, pos in positions.items():
            if asset not in signals or date not in signals[asset].index:
                continue

            row = signals[asset].loc[date]
            current_price = row['close']
            vol = row['hist_vol']

            if pd.isna(current_price):
                continue

            # Tactical: Check if we should buy protection
            if tactical and pos.leverage > 1 and not pos.has_put:
                needs_protection, reason = should_buy_protection(row, pos)
                if needs_protection:
                    cost = pos.buy_protection(current_price, vol)
                    capital -= cost
                    put_purchases += 1

            pos.update_value(current_price, vol)

            # Exit checks
            should_exit = False
            atr = row['atr']
            if not pd.isna(atr) and atr > 0:
                atr_mult = PARAMS['trailing_atr_leveraged'] if pos.leverage > 1 else PARAMS['trailing_atr_base']
                if current_price < pos.high_price - atr_mult * atr:
                    should_exit = True

            if count_signals(row) < 2:
                should_exit = True

            if should_exit:
                positions_to_close.append(asset)

        for asset in positions_to_close:
            capital += positions[asset].get_current_value()
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

                pos = TacticalPosition(asset, date, row['close'], investment, get_leverage(sc))
                positions[asset] = pos
                capital -= investment

        total_equity = capital + sum(p.get_current_value() for p in positions.values())
        equity_curve.append({'date': date, 'equity': total_equity})

    print(f"Total put purchases: {put_purchases}")
    return pd.DataFrame(equity_curve).set_index('date')


def calculate_metrics(equity_df, name):
    equity = equity_df['equity']

    years = (equity.index[-1] - equity.index[0]).days / 365.25
    cagr = (equity.iloc[-1] / equity.iloc[0]) ** (1/years) - 1

    rolling_max = equity.cummax()
    drawdown = (equity - rolling_max) / rolling_max
    max_dd = drawdown.min()

    daily_returns = equity.pct_change().dropna()
    vol = daily_returns.std() * np.sqrt(252)

    sharpe = (cagr - 0.03) / vol if vol > 0 else 0
    calmar = cagr / abs(max_dd) if max_dd != 0 else 0

    print(f"\n{name}:")
    print(f"  CAGR:           {cagr*100:.2f}%")
    print(f"  Max Drawdown:   {max_dd*100:.2f}%")
    print(f"  Volatility:     {vol*100:.2f}%")
    print(f"  Sharpe:         {sharpe:.2f}")
    print(f"  Calmar:         {calmar:.2f}")

    return {'cagr': cagr, 'max_dd': max_dd, 'vol': vol, 'sharpe': sharpe, 'calmar': calmar}


if __name__ == '__main__':
    print("\n" + "="*70)
    print("TACTICAL OPTIONS STRATEGY")
    print("="*70)
    print("""
Strategy: Only buy puts when DANGER SIGNALS appear:
  - Volatility spike (vol > 35%)
  - Momentum decay (50% off peak)
  - Price pullback (1.5% from high)

Benefits:
  - No premium drag during good times
  - Protection when it matters most
""")

    print("\n>>> With TACTICAL Puts...")
    tactical_eq = run_backtest(tactical=True)

    print("\n>>> WITHOUT Puts...")
    no_puts_eq = run_backtest(tactical=False)

    print("\n" + "="*70)
    print("RESULTS")
    print("="*70)

    tactical_m = calculate_metrics(tactical_eq, "TACTICAL PUTS")
    no_puts_m = calculate_metrics(no_puts_eq, "NO PUTS")

    print("\n" + "="*70)
    print("COMPARISON")
    print("="*70)
    print(f"\n{'Metric':<18} {'Tactical':<14} {'No Puts':<14} {'Diff':<14}")
    print("-"*60)
    print(f"{'CAGR':<18} {tactical_m['cagr']*100:>11.2f}% {no_puts_m['cagr']*100:>11.2f}% {(tactical_m['cagr']-no_puts_m['cagr'])*100:>+11.2f}%")
    print(f"{'Max DD':<18} {tactical_m['max_dd']*100:>11.2f}% {no_puts_m['max_dd']*100:>11.2f}% {(tactical_m['max_dd']-no_puts_m['max_dd'])*100:>+11.2f}%")
    print(f"{'Calmar':<18} {tactical_m['calmar']:>11.2f}  {no_puts_m['calmar']:>11.2f}  {tactical_m['calmar']-no_puts_m['calmar']:>+11.2f}")
