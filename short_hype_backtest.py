#!/usr/bin/env python3
"""
SHORT THE HYPE - Backtest

Strategy: Short assets after parabolic runs when they show breakdown signals.

Theory: Emotional buying creates bubbles. When bubbles pop, crashes are:
- More predictable than rallies
- Faster and more violent (panic selling)
- Usually 50-90% from peak

This backtest applies the concept to indices, commodities, and sectors.
"""

import pandas as pd
import numpy as np
import zipfile
from datetime import datetime

# ============================================================================
# STRATEGY PARAMETERS
# ============================================================================

PARAMS = {
    # SCAN CRITERIA (identify bubble candidates)
    'min_12m_return': 1.00,        # 100%+ in 12 months (was 200%, lowered for more signals)
    'min_6m_return': 0.50,         # 50%+ in 6 months
    'min_pct_above_200sma': 0.50,  # 50%+ above 200 SMA
    'min_rsi_peak': 70,            # RSI was > 70 recently

    # ENTRY SIGNALS (when to short)
    'break_50sma': True,           # Price breaks below 50 SMA
    'rsi_below': 50,               # RSI drops below 50
    'lower_high_pct': 0.05,        # 5% below recent high

    # EXIT RULES
    'profit_target_1': 0.20,       # Take 50% profit at 20% gain
    'profit_target_2': 0.40,       # Take rest at 40% gain
    'stop_loss': 0.15,             # Stop loss at 15% loss
    'time_stop_days': 126,         # Exit after 6 months regardless

    # POSITION SIZING
    'position_size': 0.03,         # 3% per short position
    'max_positions': 5,            # Max 5 shorts at once
    'max_exposure': 0.15,          # Max 15% short exposure

    # PORTFOLIO
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
    """Load historical data"""
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

def calculate_rsi(prices, period=14):
    """Calculate RSI"""
    delta = prices.diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_signals(prices):
    """Calculate all signals for short candidates"""
    close = prices['close']
    high = prices['high']

    # Returns
    ret_12m = close.pct_change(252)
    ret_6m = close.pct_change(126)
    ret_3m = close.pct_change(63)
    ret_1m = close.pct_change(21)

    # Moving averages
    sma_50 = close.rolling(50).mean()
    sma_200 = close.rolling(200).mean()

    # Percent above 200 SMA
    pct_above_200 = (close / sma_200) - 1

    # RSI
    rsi = calculate_rsi(close)
    rsi_peak_20d = rsi.rolling(20).max()  # Recent RSI peak

    # Recent high (for lower high detection)
    high_20d = high.rolling(20).max()
    high_60d = high.rolling(60).max()

    # Breakdown signal: below 50 SMA
    below_50sma = close < sma_50

    # Volume trend (using price volatility as proxy)
    volatility = close.pct_change().rolling(20).std()

    return pd.DataFrame({
        'close': close,
        'high': high,
        'ret_12m': ret_12m,
        'ret_6m': ret_6m,
        'ret_3m': ret_3m,
        'ret_1m': ret_1m,
        'sma_50': sma_50,
        'sma_200': sma_200,
        'pct_above_200': pct_above_200,
        'rsi': rsi,
        'rsi_peak_20d': rsi_peak_20d,
        'high_20d': high_20d,
        'high_60d': high_60d,
        'below_50sma': below_50sma,
        'volatility': volatility,
    })


def is_bubble_candidate(row):
    """Check if asset is a bubble candidate (had massive run)"""
    if pd.isna(row['ret_12m']) or pd.isna(row['pct_above_200']):
        return False, 0

    score = 0

    # Had massive run-up
    if row['ret_12m'] > PARAMS['min_12m_return']:
        score += 2
    elif row['ret_12m'] > PARAMS['min_12m_return'] * 0.5:
        score += 1

    if row['ret_6m'] > PARAMS['min_6m_return']:
        score += 1

    # Way above 200 SMA
    if row['pct_above_200'] > PARAMS['min_pct_above_200sma']:
        score += 2
    elif row['pct_above_200'] > PARAMS['min_pct_above_200sma'] * 0.5:
        score += 1

    # RSI was overbought recently
    if row['rsi_peak_20d'] > PARAMS['min_rsi_peak']:
        score += 1

    return score >= 3, score


def is_breakdown_signal(row, prev_row):
    """Check if breakdown signal is triggered"""
    if pd.isna(row['close']) or pd.isna(row['sma_50']):
        return False, []

    signals = []

    # Price breaks below 50 SMA
    if row['below_50sma'] and not prev_row['below_50sma']:
        signals.append('broke_50sma')

    # RSI drops below 50 from high
    if row['rsi'] < PARAMS['rsi_below'] and prev_row['rsi'] >= PARAMS['rsi_below']:
        signals.append('rsi_breakdown')

    # Lower high (current high is below 60-day high by threshold)
    if row['high'] < row['high_60d'] * (1 - PARAMS['lower_high_pct']):
        signals.append('lower_high')

    # Momentum turning negative
    if row['ret_1m'] < 0 and prev_row['ret_1m'] > 0:
        signals.append('momentum_flip')

    return len(signals) >= 2, signals


class ShortPosition:
    """Track a short position"""

    def __init__(self, asset, entry_date, entry_price, shares, investment):
        self.asset = asset
        self.entry_date = entry_date
        self.entry_price = entry_price
        self.shares = shares  # Negative for short
        self.investment = investment
        self.current_value = investment
        self.low_price = entry_price  # Track lowest price (best for short)
        self.days_held = 0
        self.partial_covered = False

    def update(self, current_price):
        """Update position value"""
        self.days_held += 1
        self.low_price = min(self.low_price, current_price)

        # Short P&L: profit when price goes DOWN
        price_change = self.entry_price - current_price
        pnl = (price_change / self.entry_price) * self.investment
        self.current_value = self.investment + pnl

        return self.current_value

    def get_return(self, current_price):
        """Get return percentage (positive = profit for short)"""
        return (self.entry_price - current_price) / self.entry_price

    def should_take_profit(self, current_price):
        """Check profit targets"""
        ret = self.get_return(current_price)
        if ret >= PARAMS['profit_target_2']:
            return 'full', ret
        elif ret >= PARAMS['profit_target_1'] and not self.partial_covered:
            return 'partial', ret
        return None, ret

    def should_stop_loss(self, current_price):
        """Check stop loss (price went UP against short)"""
        ret = self.get_return(current_price)
        return ret <= -PARAMS['stop_loss']

    def should_time_stop(self):
        """Check time-based exit"""
        return self.days_held >= PARAMS['time_stop_days']


def run_backtest():
    """Run the short-hype backtest"""
    print("Loading data...")
    data = load_data()
    print(f"Loaded {len(data)} assets")

    # Calculate signals
    print("Calculating signals...")
    signals = {}
    for name, prices in data.items():
        signals[name] = calculate_signals(prices)

    # Get date range
    all_dates = set()
    for sig in signals.values():
        all_dates.update(sig.dropna(subset=['ret_12m']).index)
    dates = sorted([d for d in all_dates if d >= pd.Timestamp('1981-01-01')])
    print(f"Backtesting {dates[0].date()} to {dates[-1].date()}")

    # Portfolio tracking
    capital = PARAMS['initial_capital']
    positions = {}  # asset -> ShortPosition
    equity_curve = []
    trades = []

    # Track bubble candidates over time
    bubble_history = {}

    for i, date in enumerate(dates):
        if i == 0:
            continue

        # Update existing positions
        positions_to_close = []

        for asset, pos in positions.items():
            if asset not in signals or date not in signals[asset].index:
                continue

            row = signals[asset].loc[date]
            current_price = row['close']

            if pd.isna(current_price):
                continue

            pos.update(current_price)

            # Check exit conditions
            should_close = False
            close_reason = ""

            # Profit target
            profit_action, ret = pos.should_take_profit(current_price)
            if profit_action == 'full':
                should_close = True
                close_reason = f"profit_target ({ret*100:.1f}%)"
            elif profit_action == 'partial' and not pos.partial_covered:
                # Take partial profit
                cover_value = pos.current_value * 0.5
                capital += cover_value
                pos.investment *= 0.5
                pos.shares *= 0.5
                pos.partial_covered = True
                trades.append({
                    'date': date, 'asset': asset, 'action': 'PARTIAL_COVER',
                    'price': current_price, 'pnl_pct': ret * 100
                })

            # Stop loss
            if pos.should_stop_loss(current_price):
                should_close = True
                close_reason = f"stop_loss ({pos.get_return(current_price)*100:.1f}%)"

            # Time stop
            if pos.should_time_stop():
                should_close = True
                close_reason = f"time_stop ({pos.days_held} days)"

            if should_close:
                positions_to_close.append((asset, close_reason, pos.get_return(current_price)))

        # Close positions
        for asset, reason, ret in positions_to_close:
            pos = positions[asset]
            capital += pos.current_value
            trades.append({
                'date': date, 'asset': asset, 'action': 'COVER',
                'price': signals[asset].loc[date]['close'],
                'pnl_pct': ret * 100, 'reason': reason
            })
            del positions[asset]

        # Look for new short candidates
        if len(positions) < PARAMS['max_positions']:
            prev_date = dates[i - 1]

            for asset in signals:
                if asset in positions:
                    continue
                if date not in signals[asset].index or prev_date not in signals[asset].index:
                    continue

                row = signals[asset].loc[date]
                prev_row = signals[asset].loc[prev_date]

                # First check if it's a bubble candidate
                is_bubble, bubble_score = is_bubble_candidate(row)

                if is_bubble:
                    # Track as bubble candidate
                    bubble_history[asset] = {
                        'first_seen': date,
                        'score': bubble_score,
                        'peak_price': row['high_60d']
                    }

                # Check for breakdown signal on bubble candidates
                if asset in bubble_history:
                    is_breakdown, breakdown_signals = is_breakdown_signal(row, prev_row)

                    if is_breakdown:
                        # Calculate position size
                        current_exposure = sum(p.investment for p in positions.values())
                        max_new = PARAMS['max_exposure'] * PARAMS['initial_capital'] - current_exposure
                        position_value = min(
                            capital * PARAMS['position_size'],
                            max_new
                        )

                        if position_value > 1000 and len(positions) < PARAMS['max_positions']:
                            current_price = row['close']
                            shares = position_value / current_price

                            pos = ShortPosition(asset, date, current_price, -shares, position_value)
                            positions[asset] = pos
                            capital -= position_value

                            trades.append({
                                'date': date, 'asset': asset, 'action': 'SHORT',
                                'price': current_price,
                                'signals': breakdown_signals,
                                'bubble_score': bubble_history[asset]['score']
                            })

                            # Remove from bubble candidates (already shorted)
                            del bubble_history[asset]

        # Calculate total equity
        total_equity = capital + sum(p.current_value for p in positions.values())
        equity_curve.append({'date': date, 'equity': total_equity})

    return pd.DataFrame(equity_curve).set_index('date'), trades


def calculate_metrics(equity_df):
    """Calculate performance metrics"""
    equity = equity_df['equity']

    initial = equity.iloc[0]
    final = equity.iloc[-1]
    years = (equity.index[-1] - equity.index[0]).days / 365.25

    total_return = final / initial - 1
    cagr = (final / initial) ** (1/years) - 1

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

    return {
        'total_return': total_return,
        'cagr': cagr,
        'max_dd': max_dd,
        'volatility': volatility,
        'sharpe': sharpe,
        'calmar': calmar,
    }


def analyze_trades(trades):
    """Analyze trade statistics"""
    if not trades:
        return {}

    shorts = [t for t in trades if t['action'] == 'SHORT']
    covers = [t for t in trades if t['action'] in ['COVER', 'PARTIAL_COVER']]

    if not covers:
        return {'total_shorts': len(shorts)}

    pnls = [t['pnl_pct'] for t in covers if 'pnl_pct' in t]
    winners = [p for p in pnls if p > 0]
    losers = [p for p in pnls if p <= 0]

    return {
        'total_shorts': len(shorts),
        'total_covers': len(covers),
        'win_rate': len(winners) / len(pnls) * 100 if pnls else 0,
        'avg_winner': np.mean(winners) if winners else 0,
        'avg_loser': np.mean(losers) if losers else 0,
        'avg_pnl': np.mean(pnls) if pnls else 0,
        'best_trade': max(pnls) if pnls else 0,
        'worst_trade': min(pnls) if pnls else 0,
    }


if __name__ == '__main__':
    print("\n" + "="*70)
    print("SHORT THE HYPE - BACKTEST")
    print("="*70)
    print("""
Strategy: Short assets after parabolic runs when breakdown signals appear

Entry Criteria:
- Had 100%+ return in 12 months (bubble candidate)
- Price 50%+ above 200 SMA
- RSI was > 70 recently
- Breakdown: Breaks 50 SMA + RSI < 50 + lower high

Exit Rules:
- Take partial profit at 20% gain
- Take full profit at 40% gain
- Stop loss at 15%
- Time stop at 6 months
""")

    equity_df, trades = run_backtest()

    print("\n" + "="*70)
    print("RESULTS")
    print("="*70)

    metrics = calculate_metrics(equity_df)
    print(f"\nPerformance:")
    print(f"  Total Return: {metrics['total_return']*100:.1f}%")
    print(f"  CAGR:         {metrics['cagr']*100:.2f}%")
    print(f"  Max Drawdown: {metrics['max_dd']*100:.2f}%")
    print(f"  Volatility:   {metrics['volatility']*100:.2f}%")
    print(f"  Sharpe Ratio: {metrics['sharpe']:.2f}")
    print(f"  Calmar Ratio: {metrics['calmar']:.2f}")

    trade_stats = analyze_trades(trades)
    print(f"\nTrade Statistics:")
    for key, value in trade_stats.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.2f}")
        else:
            print(f"  {key}: {value}")

    # Show some example trades
    print("\n" + "="*70)
    print("SAMPLE TRADES")
    print("="*70)

    shorts = [t for t in trades if t['action'] == 'SHORT'][:10]
    for t in shorts:
        print(f"\n{t['date'].strftime('%Y-%m-%d')} SHORT {t['asset']} @ ${t['price']:.2f}")
        print(f"  Signals: {t.get('signals', [])}")
        print(f"  Bubble Score: {t.get('bubble_score', 'N/A')}")

    # Save results
    equity_df.to_csv('short_hype_equity.csv')
    pd.DataFrame(trades).to_csv('short_hype_trades.csv', index=False)
    print("\nSaved: short_hype_equity.csv, short_hype_trades.csv")
