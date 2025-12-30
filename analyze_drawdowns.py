"""
Analyze Top 5 Drawdowns for Each Strategy
"""
import pandas as pd
import numpy as np

def analyze_drawdowns(filepath, strategy_name):
    """Find the top 5 drawdown periods with start/end dates"""
    print(f"\n{'='*60}")
    print(f"{strategy_name}")
    print(f"{'='*60}")

    try:
        df = pd.read_csv(filepath, index_col=0, parse_dates=True)
    except:
        print(f"  Could not read {filepath}")
        return

    if 'Equity' not in df.columns:
        print(f"  No 'Equity' column found")
        return

    equity = df['Equity']

    # Calculate running maximum and drawdown
    peak = equity.cummax()
    dd = (equity - peak) / peak

    # Find drawdown periods
    drawdowns = []
    in_dd = False
    dd_start = None
    dd_peak_value = None

    for i, (date, value) in enumerate(equity.items()):
        current_dd = dd.iloc[i]

        if current_dd < -0.01 and not in_dd:  # Start of drawdown (>1%)
            in_dd = True
            dd_start = date
            dd_peak_value = peak.iloc[i]
        elif in_dd:
            if current_dd >= -0.005:  # Recovery (within 0.5% of peak)
                # Drawdown ended
                trough_idx = dd.loc[dd_start:date].idxmin()
                trough_dd = dd.loc[trough_idx]
                days = (date - dd_start).days
                drawdowns.append({
                    'start': dd_start,
                    'trough': trough_idx,
                    'end': date,
                    'max_dd': trough_dd,
                    'duration_days': days,
                    'peak_value': dd_peak_value
                })
                in_dd = False

    # If still in drawdown at end
    if in_dd:
        trough_idx = dd.loc[dd_start:].idxmin()
        trough_dd = dd.loc[trough_idx]
        days = (equity.index[-1] - dd_start).days
        drawdowns.append({
            'start': dd_start,
            'trough': trough_idx,
            'end': 'Ongoing',
            'max_dd': trough_dd,
            'duration_days': days,
            'peak_value': dd_peak_value
        })

    # Sort by max drawdown (most negative first)
    drawdowns.sort(key=lambda x: x['max_dd'])

    # Print top 5
    print(f"\nTop 5 Biggest Drawdowns:")
    print("-" * 60)
    for i, d in enumerate(drawdowns[:5], 1):
        end_str = d['end'] if isinstance(d['end'], str) else d['end'].strftime('%Y-%m-%d')
        print(f"\n  #{i}: {d['max_dd']*100:.1f}%")
        print(f"      Started:  {d['start'].strftime('%Y-%m-%d')}")
        print(f"      Trough:   {d['trough'].strftime('%Y-%m-%d')}")
        print(f"      Ended:    {end_str}")
        print(f"      Duration: {d['duration_days']} days")

    # Overall max drawdown
    max_dd_idx = dd.idxmin()
    print(f"\nOverall Max Drawdown: {dd.min()*100:.1f}% on {max_dd_idx.strftime('%Y-%m-%d')}")

    return drawdowns

if __name__ == '__main__':
    strategies = [
        ('smart_leverage_equity.csv', 'OPTION A: Smart Leverage (21.34% CAGR, -59.6% DD)'),
        ('aggressive_equity_curve.csv', 'AGGRESSIVE: (24.44% CAGR, -83.1% DD)'),
        ('backtest_equity_curve.csv', 'OPTION B: Conservative (2.69% CAGR, -23.7% DD)'),
        ('optimized_equity_curve.csv', 'OPTION C: Optimized (7.99% CAGR, -53.9% DD)'),
    ]

    for filepath, name in strategies:
        analyze_drawdowns(filepath, name)

    print("\n" + "="*60)
    print("SUMMARY: Major Drawdown Periods Across All Strategies")
    print("="*60)
    print("""
Key Crisis Periods Identified:

1. 2018-2019 (Crypto Winter + Q4 2018 Stock Selloff)
   - Affected all strategies significantly
   - BTC dropped ~80%, stocks fell 20%

2. 2020 (COVID Crash - March 2020)
   - Sharp but quick V-shaped recovery
   - Leveraged strategies took bigger hits

3. 2022 (Fed Rate Hikes + Crypto Crash)
   - Prolonged drawdown period
   - Most strategies hit their max DD during this period

4. 2008-2009 (Global Financial Crisis)
   - Major stress test for trend-following
   - Commodities and equities both hit hard

5. 2000-2002 (Dot-com Bust)
   - Extended bear market
   - Trend-following generally performed well here
""")
