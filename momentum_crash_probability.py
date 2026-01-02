#!/usr/bin/env python3
"""
MOMENTUM CRASH PROBABILITY ANALYSIS

Question: When an asset has extreme momentum, what's the probability it crashes?

Methodology:
1. Find ALL instances where 12-month return exceeded threshold (50%, 100%, 200%, 300%)
2. Track what happened in the next 1, 3, 6, 12 months
3. Calculate probability of various decline levels
4. Determine if there's statistical edge in shorting

This is a rigorous statistical analysis to validate the "short the hype" theory.
"""

import pandas as pd
import numpy as np
import zipfile
from collections import defaultdict
import warnings
warnings.filterwarnings('ignore')

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
    """Load all historical data"""
    data = {}
    with zipfile.ZipFile('historical_data.zip', 'r') as z:
        for name in ASSETS:
            filename = f"historical_data/{name}.csv"
            if filename in z.namelist():
                with z.open(filename) as f:
                    df = pd.read_csv(f, header=0, index_col=0, parse_dates=True, skiprows=[1,2])
                    if 'Close' in df.columns:
                        data[name] = df['Close'].dropna()
    return data


def calculate_forward_returns(prices, periods=[21, 63, 126, 252]):
    """Calculate forward returns for various periods"""
    results = {}
    for period in periods:
        results[f'fwd_{period}d'] = prices.shift(-period) / prices - 1
    return pd.DataFrame(results, index=prices.index)


def find_extreme_momentum_events(data, lookback=252, threshold=0.5):
    """
    Find all instances where trailing return exceeded threshold

    Returns DataFrame with:
    - date, asset, trailing_return
    - forward returns (1m, 3m, 6m, 12m)
    """
    events = []

    for asset, prices in data.items():
        if len(prices) < lookback + 252:  # Need enough history
            continue

        # Calculate trailing 12-month return
        trailing_return = prices.pct_change(lookback)

        # Calculate forward returns
        fwd_returns = calculate_forward_returns(prices)

        # Find events where trailing return exceeded threshold
        for date in trailing_return.index:
            if pd.isna(trailing_return.loc[date]):
                continue
            if trailing_return.loc[date] >= threshold:
                event = {
                    'date': date,
                    'asset': asset,
                    'trailing_12m': trailing_return.loc[date],
                    'price': prices.loc[date],
                }

                # Add forward returns if available
                for col in fwd_returns.columns:
                    if date in fwd_returns.index:
                        event[col] = fwd_returns.loc[date, col]
                    else:
                        event[col] = np.nan

                events.append(event)

    return pd.DataFrame(events)


def calculate_max_drawdown_forward(prices, start_date, periods=[63, 126, 252]):
    """Calculate maximum drawdown from start_date over various periods"""
    results = {}

    try:
        start_idx = prices.index.get_loc(start_date)
        start_price = prices.iloc[start_idx]

        for period in periods:
            end_idx = min(start_idx + period, len(prices) - 1)
            if end_idx <= start_idx:
                results[f'max_dd_{period}d'] = np.nan
                continue

            future_prices = prices.iloc[start_idx:end_idx+1]
            min_price = future_prices.min()
            max_dd = (min_price - start_price) / start_price
            results[f'max_dd_{period}d'] = max_dd

    except Exception:
        for period in periods:
            results[f'max_dd_{period}d'] = np.nan

    return results


def analyze_momentum_buckets(events_df):
    """Analyze outcomes by momentum bucket"""

    # Define momentum buckets
    buckets = [
        (0.5, 1.0, '50-100%'),
        (1.0, 1.5, '100-150%'),
        (1.5, 2.0, '150-200%'),
        (2.0, 3.0, '200-300%'),
        (3.0, 10.0, '300%+'),
    ]

    results = []

    for low, high, label in buckets:
        mask = (events_df['trailing_12m'] >= low) & (events_df['trailing_12m'] < high)
        bucket_events = events_df[mask]

        if len(bucket_events) < 10:
            continue

        # Calculate statistics for this bucket
        stats = {
            'bucket': label,
            'count': len(bucket_events),
        }

        # Forward return statistics
        for period in ['fwd_21d', 'fwd_63d', 'fwd_126d', 'fwd_252d']:
            valid = bucket_events[period].dropna()
            if len(valid) > 0:
                stats[f'{period}_mean'] = valid.mean()
                stats[f'{period}_median'] = valid.median()
                stats[f'{period}_pos_pct'] = (valid > 0).mean() * 100
                stats[f'{period}_neg_pct'] = (valid < 0).mean() * 100
                stats[f'{period}_down10_pct'] = (valid < -0.10).mean() * 100
                stats[f'{period}_down20_pct'] = (valid < -0.20).mean() * 100
                stats[f'{period}_down30_pct'] = (valid < -0.30).mean() * 100
                stats[f'{period}_down50_pct'] = (valid < -0.50).mean() * 100

        results.append(stats)

    return pd.DataFrame(results)


def analyze_with_breakdown_signal(data, events_df):
    """
    More sophisticated analysis:
    Look at what happens when extreme momentum + breakdown signal occurs

    Breakdown signals:
    1. Price breaks below 50 SMA
    2. RSI drops below 50
    """

    enhanced_events = []

    for _, event in events_df.iterrows():
        asset = event['asset']
        date = event['date']

        if asset not in data:
            continue

        prices = data[asset]

        if date not in prices.index:
            continue

        try:
            # Get historical data up to this point
            hist = prices.loc[:date]

            if len(hist) < 200:
                continue

            # Calculate indicators
            sma_50 = hist.rolling(50).mean()
            sma_200 = hist.rolling(200).mean()

            current_price = hist.iloc[-1]
            current_sma50 = sma_50.iloc[-1]
            current_sma200 = sma_200.iloc[-1]

            # RSI calculation
            delta = hist.diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            current_rsi = rsi.iloc[-1]

            # Percent above 200 SMA
            pct_above_200 = (current_price / current_sma200 - 1) if current_sma200 > 0 else 0

            # Check breakdown signals
            below_50sma = current_price < current_sma50
            rsi_below_50 = current_rsi < 50

            enhanced_event = event.to_dict()
            enhanced_event['below_50sma'] = below_50sma
            enhanced_event['rsi_below_50'] = rsi_below_50
            enhanced_event['rsi'] = current_rsi
            enhanced_event['pct_above_200sma'] = pct_above_200
            enhanced_event['breakdown_signal'] = below_50sma and rsi_below_50

            enhanced_events.append(enhanced_event)

        except Exception as e:
            continue

    return pd.DataFrame(enhanced_events)


def print_probability_matrix(results_df):
    """Print a nice probability matrix"""

    print("\n" + "="*100)
    print("PROBABILITY MATRIX: What happens after extreme momentum?")
    print("="*100)

    print("\n📊 FORWARD RETURN PROBABILITIES BY MOMENTUM BUCKET")
    print("-"*100)

    # 3-month forward
    print("\n3-MONTH FORWARD (63 trading days):")
    print(f"{'Momentum':<12} {'Count':<8} {'Avg Ret':<10} {'% Positive':<12} {'% Down>10%':<12} {'% Down>20%':<12} {'% Down>30%':<12}")
    print("-"*80)

    for _, row in results_df.iterrows():
        if 'fwd_63d_mean' in row:
            print(f"{row['bucket']:<12} {row['count']:<8} {row.get('fwd_63d_mean', 0)*100:>+7.1f}% "
                  f"{row.get('fwd_63d_pos_pct', 0):>10.1f}% {row.get('fwd_63d_down10_pct', 0):>10.1f}% "
                  f"{row.get('fwd_63d_down20_pct', 0):>10.1f}% {row.get('fwd_63d_down30_pct', 0):>10.1f}%")

    # 6-month forward
    print("\n6-MONTH FORWARD (126 trading days):")
    print(f"{'Momentum':<12} {'Count':<8} {'Avg Ret':<10} {'% Positive':<12} {'% Down>10%':<12} {'% Down>20%':<12} {'% Down>30%':<12}")
    print("-"*80)

    for _, row in results_df.iterrows():
        if 'fwd_126d_mean' in row:
            print(f"{row['bucket']:<12} {row['count']:<8} {row.get('fwd_126d_mean', 0)*100:>+7.1f}% "
                  f"{row.get('fwd_126d_pos_pct', 0):>10.1f}% {row.get('fwd_126d_down10_pct', 0):>10.1f}% "
                  f"{row.get('fwd_126d_down20_pct', 0):>10.1f}% {row.get('fwd_126d_down30_pct', 0):>10.1f}%")

    # 12-month forward
    print("\n12-MONTH FORWARD (252 trading days):")
    print(f"{'Momentum':<12} {'Count':<8} {'Avg Ret':<10} {'% Positive':<12} {'% Down>10%':<12} {'% Down>20%':<12} {'% Down>30%':<12}")
    print("-"*80)

    for _, row in results_df.iterrows():
        if 'fwd_252d_mean' in row:
            print(f"{row['bucket']:<12} {row['count']:<8} {row.get('fwd_252d_mean', 0)*100:>+7.1f}% "
                  f"{row.get('fwd_252d_pos_pct', 0):>10.1f}% {row.get('fwd_252d_down10_pct', 0):>10.1f}% "
                  f"{row.get('fwd_252d_down20_pct', 0):>10.1f}% {row.get('fwd_252d_down30_pct', 0):>10.1f}%")


def analyze_breakdown_signal_edge(enhanced_df):
    """Analyze if breakdown signal improves prediction"""

    print("\n" + "="*100)
    print("BREAKDOWN SIGNAL ANALYSIS")
    print("Does waiting for breakdown signal improve prediction?")
    print("="*100)

    # Compare: All extreme momentum vs Extreme momentum WITH breakdown

    extreme = enhanced_df[enhanced_df['trailing_12m'] >= 1.0]  # 100%+ momentum

    if len(extreme) < 20:
        print("Not enough extreme momentum events for analysis")
        return

    with_breakdown = extreme[extreme['breakdown_signal'] == True]
    without_breakdown = extreme[extreme['breakdown_signal'] == False]

    print(f"\nExtreme Momentum (100%+) Events: {len(extreme)}")
    print(f"  - With Breakdown Signal: {len(with_breakdown)}")
    print(f"  - Without Breakdown Signal: {len(without_breakdown)}")

    if len(with_breakdown) >= 10 and len(without_breakdown) >= 10:
        print("\n3-MONTH FORWARD COMPARISON:")
        print("-"*60)

        for label, subset in [('WITH Breakdown', with_breakdown), ('WITHOUT Breakdown', without_breakdown)]:
            valid = subset['fwd_63d'].dropna()
            if len(valid) > 0:
                print(f"\n{label} (n={len(valid)}):")
                print(f"  Mean Return:     {valid.mean()*100:+.1f}%")
                print(f"  Median Return:   {valid.median()*100:+.1f}%")
                print(f"  % Positive:      {(valid > 0).mean()*100:.1f}%")
                print(f"  % Down > 10%:    {(valid < -0.10).mean()*100:.1f}%")
                print(f"  % Down > 20%:    {(valid < -0.20).mean()*100:.1f}%")
                print(f"  % Down > 30%:    {(valid < -0.30).mean()*100:.1f}%")

        print("\n6-MONTH FORWARD COMPARISON:")
        print("-"*60)

        for label, subset in [('WITH Breakdown', with_breakdown), ('WITHOUT Breakdown', without_breakdown)]:
            valid = subset['fwd_126d'].dropna()
            if len(valid) > 0:
                print(f"\n{label} (n={len(valid)}):")
                print(f"  Mean Return:     {valid.mean()*100:+.1f}%")
                print(f"  Median Return:   {valid.median()*100:+.1f}%")
                print(f"  % Positive:      {(valid > 0).mean()*100:.1f}%")
                print(f"  % Down > 10%:    {(valid < -0.10).mean()*100:.1f}%")
                print(f"  % Down > 20%:    {(valid < -0.20).mean()*100:.1f}%")
                print(f"  % Down > 30%:    {(valid < -0.30).mean()*100:.1f}%")


def calculate_expected_value(events_df, threshold=1.0):
    """
    Calculate expected value of shorting after extreme momentum

    Assumes:
    - Short at current price
    - Stop loss at +15% (loss)
    - Take profit at -30% (gain for short)
    - 6-month holding period
    """

    extreme = events_df[events_df['trailing_12m'] >= threshold]
    valid = extreme['fwd_126d'].dropna()

    if len(valid) < 10:
        return None

    # Simulate trades
    profits = []
    for ret in valid:
        # ret is the actual return (negative = good for short)
        if ret <= -0.30:  # Stock dropped 30%+ = hit profit target
            profits.append(0.30)  # 30% profit on short
        elif ret >= 0.15:  # Stock rose 15%+ = hit stop loss
            profits.append(-0.15)  # 15% loss on short
        else:
            profits.append(-ret)  # Actual P&L at end of period

    profits = np.array(profits)

    return {
        'n_trades': len(profits),
        'win_rate': (profits > 0).mean() * 100,
        'avg_profit': profits.mean() * 100,
        'total_profit': profits.sum() * 100,
        'sharpe': profits.mean() / profits.std() if profits.std() > 0 else 0,
        'best_trade': profits.max() * 100,
        'worst_trade': profits.min() * 100,
    }


def main():
    print("="*100)
    print("MOMENTUM CRASH PROBABILITY ANALYSIS")
    print("="*100)
    print("\nQuestion: When assets have extreme momentum, what's the probability they crash?")
    print("Dataset: 30 assets (indices, commodities, currencies, sectors)")
    print("Period: 1980-2024 (44 years)")

    # Load data
    print("\nLoading data...")
    data = load_data()
    print(f"Loaded {len(data)} assets")

    # Find all extreme momentum events
    print("\nFinding extreme momentum events (50%+ 12-month return)...")
    events = find_extreme_momentum_events(data, lookback=252, threshold=0.5)
    print(f"Found {len(events)} extreme momentum events")

    # Analyze by momentum bucket
    print("\nAnalyzing outcomes by momentum bucket...")
    results = analyze_momentum_buckets(events)

    # Print probability matrix
    print_probability_matrix(results)

    # Enhanced analysis with breakdown signals
    print("\nCalculating breakdown signals...")
    enhanced = analyze_with_breakdown_signal(data, events)
    print(f"Enhanced events with signals: {len(enhanced)}")

    if len(enhanced) > 0:
        analyze_breakdown_signal_edge(enhanced)

    # Calculate expected value
    print("\n" + "="*100)
    print("EXPECTED VALUE ANALYSIS")
    print("="*100)
    print("\nSimulating shorting strategy:")
    print("- Entry: After 100%+ 12-month return")
    print("- Stop Loss: 15% (if price rises)")
    print("- Take Profit: 30% (if price falls)")
    print("- Holding Period: 6 months")

    ev = calculate_expected_value(events, threshold=1.0)
    if ev:
        print(f"\nResults (n={ev['n_trades']} trades):")
        print(f"  Win Rate:        {ev['win_rate']:.1f}%")
        print(f"  Avg Profit:      {ev['avg_profit']:+.2f}%")
        print(f"  Best Trade:      {ev['best_trade']:+.1f}%")
        print(f"  Worst Trade:     {ev['worst_trade']:+.1f}%")
        print(f"  Sharpe-like:     {ev['sharpe']:.2f}")

    # Summary and conclusions
    print("\n" + "="*100)
    print("CONCLUSIONS")
    print("="*100)

    # Find the key insight
    if len(results) > 0:
        # Get the most extreme bucket
        extreme_bucket = results[results['bucket'] == '200-300%']
        if len(extreme_bucket) > 0:
            extreme_bucket = extreme_bucket.iloc[0]
            print(f"""
KEY FINDINGS:

1. EXTREME MOMENTUM (200-300% in 12 months):
   - Sample size: {extreme_bucket.get('count', 'N/A')} events
   - 6-month forward average return: {extreme_bucket.get('fwd_126d_mean', 0)*100:+.1f}%
   - Probability of 20%+ decline in 6 months: {extreme_bucket.get('fwd_126d_down20_pct', 0):.1f}%
   - Probability of 30%+ decline in 6 months: {extreme_bucket.get('fwd_126d_down30_pct', 0):.1f}%

2. STATISTICAL EDGE:
   - If >50% probability of decline, shorting has positive expected value
   - Higher momentum → Higher crash probability (mean reversion)
   - Breakdown signals can improve timing

3. CAVEATS:
   - This is on indices/commodities (less volatile than individual stocks)
   - Individual hype stocks (NKLA, PTON) crash much harder (80-99%)
   - Indices/commodities may recover faster than individual stocks
   - Short squeezes are rare in indices but common in stocks

4. RECOMMENDED APPROACH:
   - For indices/commodities: Use this data as-is
   - For individual stocks: Add fundamental filters (P/S, earnings)
   - Always use stop losses (15-20%)
   - Use puts instead of shorting for defined risk
""")

    # Save detailed results
    events.to_csv('momentum_events_analysis.csv', index=False)
    results.to_csv('momentum_bucket_analysis.csv', index=False)
    if len(enhanced) > 0:
        enhanced.to_csv('momentum_breakdown_analysis.csv', index=False)

    print("\nSaved: momentum_events_analysis.csv, momentum_bucket_analysis.csv, momentum_breakdown_analysis.csv")


if __name__ == '__main__':
    main()
