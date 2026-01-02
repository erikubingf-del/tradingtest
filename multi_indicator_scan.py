#!/usr/bin/env python3
"""
MULTI-INDICATOR PATTERN SCANNER - Find All Profitable Short Patterns

Tests 20+ different indicator combinations to find statistically
significant short-selling patterns beyond just the 200 SMA filter.

INDICATORS TESTED:
1. Momentum levels (100%, 150%, 200%, 300%+)
2. RSI levels (>70, >75, >80, <50, <40)
3. Price vs MAs (20, 50, 100, 200)
4. MA crossovers (death cross, etc.)
5. Volume patterns
6. Volatility (ATR)
7. Extension from MAs
8. Rate of change
9. Multiple timeframe momentum
10. Momentum divergence

REQUIREMENTS:
    pip install yfinance pandas numpy tqdm

USAGE:
    python multi_indicator_scan.py
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import warnings
warnings.filterwarnings('ignore')

try:
    import yfinance as yf
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    import yfinance as yf
    HAS_TQDM = False

# ============================================================================
# EXPANDED STOCK UNIVERSE - 300+ STOCKS
# ============================================================================

# All bubble/hype stocks
BUBBLE_STOCKS = [
    # Dot-com survivors
    'CSCO', 'INTC', 'MSFT', 'ORCL', 'QCOM', 'JNPR', 'AMAT', 'AMZN', 'EBAY',
    # Financial crisis
    'BAC', 'C', 'JPM', 'WFC', 'GS', 'MS', 'AIG',
    # Housing
    'DHI', 'LEN', 'PHM', 'TOL', 'KBH', 'HD', 'LOW',
    # Biotech
    'GILD', 'BIIB', 'AMGN', 'REGN', 'VRTX', 'MRNA', 'BNTX', 'NVAX',
    # Cannabis
    'CGC', 'TLRY', 'ACB', 'CRON',
    # Crypto
    'COIN', 'RIOT', 'MARA', 'MSTR', 'SI',
    # EV
    'TSLA', 'NIO', 'XPEV', 'LI', 'RIVN', 'LCID', 'NKLA', 'QS', 'PLUG', 'FCEL',
    # COVID
    'ZM', 'PTON', 'DOCU', 'TDOC', 'CHWY', 'W', 'ETSY', 'SHOP', 'ROKU',
    'SNAP', 'PINS', 'DDOG', 'NET', 'CRWD', 'ZS', 'OKTA', 'SNOW', 'PLTR', 'U',
    # Fintech
    'AFRM', 'HOOD', 'UPST', 'SOFI', 'LMND', 'SQ', 'PYPL',
    # Meme
    'GME', 'AMC', 'BB', 'SPCE', 'WISH', 'CLOV',
    # Solar
    'ENPH', 'SEDG', 'RUN', 'FSLR',
    # AI
    'NVDA', 'AMD', 'SMCI', 'ARM', 'AI', 'PATH',
    # Commodity
    'FCX', 'NEM', 'CLF', 'X', 'OXY', 'DVN',
    # Social
    'META', 'TWTR', 'MTCH',
    # 3D printing
    'DDD', 'SSYS',
    # SPACs
    'LAZR', 'VLDR', 'GOEV', 'FSR',
]

# Quality stocks for comparison
QUALITY_STOCKS = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'AVGO', 'ADBE', 'CRM',
    'JPM', 'V', 'MA', 'JNJ', 'UNH', 'PG', 'KO', 'WMT', 'COST',
]

# Additional large caps for more data
LARGECAP_STOCKS = [
    'XOM', 'CVX', 'T', 'VZ', 'DIS', 'NFLX', 'CMCSA', 'PEP',
    'MRK', 'ABT', 'TMO', 'DHR', 'LLY', 'NKE', 'MCD', 'SBUX',
    'CAT', 'DE', 'BA', 'GE', 'HON', 'UPS', 'FDX',
    'BLK', 'SCHW', 'AXP', 'USB', 'PNC', 'TFC',
]

# Small/mid cap with high volatility
VOLATILE_STOCKS = [
    'BYND', 'CVNA', 'DASH', 'ABNB', 'UBER', 'LYFT', 'RBLX', 'DKNG',
    'PENN', 'WYNN', 'MGM', 'LVS', 'CCL', 'RCL', 'NCLH',
    'AAL', 'UAL', 'DAL', 'LUV', 'SAVE', 'JBLU',
]

ALL_STOCKS = list(set(BUBBLE_STOCKS + QUALITY_STOCKS + LARGECAP_STOCKS + VOLATILE_STOCKS))

# Categorize
STOCK_CATEGORY = {}
for s in BUBBLE_STOCKS: STOCK_CATEGORY[s] = 'bubble'
for s in QUALITY_STOCKS: STOCK_CATEGORY[s] = 'quality'
for s in LARGECAP_STOCKS: STOCK_CATEGORY[s] = 'largecap'
for s in VOLATILE_STOCKS: STOCK_CATEGORY[s] = 'volatile'

print(f"Total stocks to scan: {len(ALL_STOCKS)}")

# ============================================================================
# COMPREHENSIVE INDICATOR CALCULATION
# ============================================================================

def calculate_all_indicators(df):
    """Calculate comprehensive set of technical indicators"""
    close = df['close']
    high = df['high']
    low = df['low']
    volume = df['volume'] if 'volume' in df.columns else pd.Series([0]*len(df))

    # ========== MOMENTUM ==========
    for period in [21, 63, 126, 252]:
        df[f'mom_{period}d'] = close.pct_change(period)

    # Rate of change
    for period in [10, 20, 50]:
        df[f'roc_{period}d'] = close.pct_change(period) * 100

    # ========== MOVING AVERAGES ==========
    for period in [10, 20, 50, 100, 200]:
        df[f'sma_{period}'] = close.rolling(period).mean()
        df[f'above_sma{period}'] = close > df[f'sma_{period}']
        df[f'pct_from_sma{period}'] = (close / df[f'sma_{period}'] - 1) * 100

    # EMA
    for period in [12, 26, 50]:
        df[f'ema_{period}'] = close.ewm(span=period).mean()

    # ========== MA CROSSOVERS ==========
    df['golden_cross'] = (df['sma_50'] > df['sma_200']) & (df['sma_50'].shift(1) <= df['sma_200'].shift(1))
    df['death_cross'] = (df['sma_50'] < df['sma_200']) & (df['sma_50'].shift(1) >= df['sma_200'].shift(1))
    df['days_since_death_cross'] = 0

    # Track days since death cross
    death_cross_count = 0
    for i in range(len(df)):
        if df['death_cross'].iloc[i]:
            death_cross_count = 1
        elif death_cross_count > 0:
            death_cross_count += 1
        df.iloc[i, df.columns.get_loc('days_since_death_cross')] = death_cross_count

    # ========== RSI ==========
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))

    # RSI overbought/oversold
    df['rsi_ob'] = df['rsi'] > 70
    df['rsi_os'] = df['rsi'] < 30

    # RSI from peak
    df['rsi_14d_max'] = df['rsi'].rolling(14).max()
    df['rsi_dropped_from_peak'] = df['rsi_14d_max'] - df['rsi'] > 20

    # ========== MACD ==========
    df['macd'] = df['ema_12'] - df['ema_26']
    df['macd_signal'] = df['macd'].ewm(span=9).mean()
    df['macd_hist'] = df['macd'] - df['macd_signal']
    df['macd_bearish_cross'] = (df['macd'] < df['macd_signal']) & (df['macd'].shift(1) >= df['macd_signal'].shift(1))

    # ========== BOLLINGER BANDS ==========
    df['bb_mid'] = close.rolling(20).mean()
    df['bb_std'] = close.rolling(20).std()
    df['bb_upper'] = df['bb_mid'] + 2 * df['bb_std']
    df['bb_lower'] = df['bb_mid'] - 2 * df['bb_std']
    df['bb_pct'] = (close - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
    df['above_bb_upper'] = close > df['bb_upper']

    # ========== ATR (Volatility) ==========
    tr = pd.DataFrame({
        'hl': high - low,
        'hc': abs(high - close.shift(1)),
        'lc': abs(low - close.shift(1))
    }).max(axis=1)
    df['atr'] = tr.rolling(14).mean()
    df['atr_pct'] = df['atr'] / close * 100

    # ========== VOLUME ==========
    if volume.sum() > 0:
        df['vol_sma_20'] = volume.rolling(20).mean()
        df['vol_ratio'] = volume / df['vol_sma_20']
        df['high_volume'] = df['vol_ratio'] > 2.0

    # ========== PRICE PATTERNS ==========
    # New 52-week high/low
    df['high_52w'] = close.rolling(252).max()
    df['low_52w'] = close.rolling(252).min()
    df['pct_from_52w_high'] = (close / df['high_52w'] - 1) * 100
    df['at_52w_high'] = close >= df['high_52w'] * 0.98
    df['down_20_from_high'] = df['pct_from_52w_high'] < -20
    df['down_50_from_high'] = df['pct_from_52w_high'] < -50

    # ========== MOMENTUM DIVERGENCE ==========
    # Price making higher high but RSI making lower high
    df['price_hh'] = close > close.rolling(20).max().shift(1)
    df['rsi_lh'] = df['rsi'] < df['rsi'].rolling(20).max().shift(1)
    df['bearish_divergence'] = df['price_hh'] & df['rsi_lh']

    # ========== FORWARD RETURNS ==========
    df['fwd_1m'] = close.shift(-21) / close - 1
    df['fwd_3m'] = close.shift(-63) / close - 1
    df['fwd_6m'] = close.shift(-126) / close - 1
    df['fwd_12m'] = close.shift(-252) / close - 1

    # Max drawdown forward
    for period in [63, 126, 252]:
        dd_list = []
        for i in range(len(close)):
            if i + period >= len(close):
                dd_list.append(np.nan)
            else:
                future = close.iloc[i:i+period+1]
                dd_list.append((future.min() - close.iloc[i]) / close.iloc[i])
        df[f'max_dd_{period}d'] = dd_list

    return df


# ============================================================================
# PATTERN DEFINITIONS
# ============================================================================

PATTERNS = {
    # Original pattern (below 200 SMA)
    'below_200sma': lambda df: (df['mom_252d'] >= 1.0) & (df['above_sma200'] == False),

    # Below 50 SMA only
    'below_50sma': lambda df: (df['mom_252d'] >= 1.0) & (df['above_sma50'] == False),

    # High momentum + death cross
    'death_cross': lambda df: (df['mom_252d'] >= 1.0) & (df['days_since_death_cross'] > 0) & (df['days_since_death_cross'] <= 30),

    # RSI breakdown from overbought
    'rsi_breakdown': lambda df: (df['mom_252d'] >= 1.0) & (df['rsi_dropped_from_peak']) & (df['rsi'] < 60),

    # MACD bearish cross with momentum
    'macd_bearish': lambda df: (df['mom_252d'] >= 1.0) & (df['macd_bearish_cross']) & (df['above_sma50'] == False),

    # Extended above BB + reversal
    'bb_reversal': lambda df: (df['mom_252d'] >= 1.0) & (df['bb_pct'] < 0.3) & (df['bb_pct'].shift(20) > 0.8),

    # 20% down from 52-week high
    'down_20_from_high': lambda df: (df['mom_252d'] >= 1.0) & (df['down_20_from_high']),

    # Bearish divergence
    'bearish_div': lambda df: (df['mom_252d'] >= 1.0) & (df['bearish_divergence']),

    # Very high momentum (300%+) with any weakness
    'extreme_mom_300': lambda df: (df['mom_252d'] >= 3.0) & (df['above_sma20'] == False),

    # Extreme momentum 200%+, below 50 SMA, RSI < 50
    'extreme_weak': lambda df: (df['mom_252d'] >= 2.0) & (df['above_sma50'] == False) & (df['rsi'] < 50),

    # Very extended (100%+ above 200 SMA) then breakdown
    'extended_breakdown': lambda df: (df['pct_from_sma200'] < 50) & (df['pct_from_sma200'].shift(20) > 100),

    # Multiple MA breakdown (below 20, 50, 100)
    'triple_breakdown': lambda df: (df['mom_252d'] >= 1.0) & (df['above_sma20'] == False) & (df['above_sma50'] == False) & (df['above_sma100'] == False),

    # Short-term momentum loss with long-term high
    'momentum_loss': lambda df: (df['mom_252d'] >= 1.0) & (df['mom_63d'] < 0),

    # High volatility breakdown
    'high_vol_breakdown': lambda df: (df['mom_252d'] >= 1.0) & (df['atr_pct'] > 5) & (df['above_sma50'] == False),

    # Below 200 SMA + RSI < 40 (deep oversold after momentum)
    'deep_oversold': lambda df: (df['mom_252d'] >= 1.0) & (df['above_sma200'] == False) & (df['rsi'] < 40),

    # Price down 50% from high
    'down_50_from_high': lambda df: (df['mom_252d'] >= 0.5) & (df['down_50_from_high']),

    # Combination: below 200 + death cross happened recently
    'combo_200_death': lambda df: (df['mom_252d'] >= 1.0) & (df['above_sma200'] == False) & (df['days_since_death_cross'] > 0),

    # Lower highs pattern (price below 20-day max)
    'lower_highs': lambda df: (df['mom_252d'] >= 1.0) & (close < close.shift(20)) & (close.shift(20) < close.shift(40)),
}


# ============================================================================
# MAIN SCAN
# ============================================================================

def main():
    print("="*100)
    print("MULTI-INDICATOR PATTERN SCANNER")
    print("="*100)

    all_data = {}
    pattern_results = {name: [] for name in PATTERNS.keys()}

    print(f"\nScanning {len(ALL_STOCKS)} stocks with {len(PATTERNS)} patterns...")

    iterator = tqdm(ALL_STOCKS) if HAS_TQDM else ALL_STOCKS

    for ticker in iterator:
        if not HAS_TQDM:
            print(f"  {ticker}...", end=" ", flush=True)

        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period='max')

            if df is None or len(df) < 300:
                if not HAS_TQDM:
                    print("SKIP (insufficient data)")
                continue

            df.columns = [c.lower() for c in df.columns]
            df = df.dropna(subset=['close'])

            # Need to define 'close' for patterns that use it directly
            global close
            close = df['close']

            # Calculate indicators
            df = calculate_all_indicators(df)

            category = STOCK_CATEGORY.get(ticker, 'other')

            # Test each pattern
            for pattern_name, pattern_func in PATTERNS.items():
                try:
                    mask = pattern_func(df)
                    signals = df[mask].copy()

                    for idx, row in signals.iterrows():
                        if pd.isna(row.get('fwd_12m')):
                            continue

                        pattern_results[pattern_name].append({
                            'date': idx,
                            'ticker': ticker,
                            'category': category,
                            'mom_12m': row['mom_252d'],
                            'rsi': row['rsi'],
                            'fwd_6m': row['fwd_6m'],
                            'fwd_12m': row['fwd_12m'],
                            'max_dd_6m': row['max_dd_126d'],
                        })
                except Exception as e:
                    continue

            if not HAS_TQDM:
                print(f"OK")

            time.sleep(0.05)

        except Exception as e:
            if not HAS_TQDM:
                print(f"ERROR: {e}")
            continue

    # ============================================================================
    # ANALYZE PATTERNS
    # ============================================================================

    print("\n" + "="*100)
    print("PATTERN ANALYSIS RESULTS")
    print("="*100)

    results_summary = []

    print(f"\n{'Pattern':<25} {'Signals':<10} {'Win Rate':<12} {'Avg Short':<12} {'Quality':<10}")
    print("-"*80)

    for pattern_name, signals in pattern_results.items():
        if len(signals) < 10:
            continue

        df = pd.DataFrame(signals)

        # Calculate metrics
        win_rate = (df['fwd_12m'] < 0).mean() * 100
        avg_short_ret = -df['fwd_12m'].mean() * 100

        # Exclude quality stocks
        non_quality = df[df['category'] != 'quality']
        if len(non_quality) < 5:
            continue

        nq_win_rate = (non_quality['fwd_12m'] < 0).mean() * 100
        nq_avg_ret = -non_quality['fwd_12m'].mean() * 100

        # Quality score (win rate * avg return) - higher is better
        quality = nq_win_rate * nq_avg_ret / 100 if nq_avg_ret > 0 else nq_win_rate * nq_avg_ret / 100

        print(f"{pattern_name:<25} {len(non_quality):<10} {nq_win_rate:>8.1f}% {nq_avg_ret:>+10.1f}% {quality:>+8.1f}")

        results_summary.append({
            'pattern': pattern_name,
            'signals': len(non_quality),
            'win_rate': nq_win_rate,
            'avg_short_return': nq_avg_ret,
            'quality_score': quality,
        })

    # Sort by quality score
    results_summary = sorted(results_summary, key=lambda x: x['quality_score'], reverse=True)

    print("\n" + "="*100)
    print("TOP PATTERNS (sorted by quality score)")
    print("="*100)

    print(f"\n{'Rank':<6} {'Pattern':<25} {'Signals':<10} {'Win Rate':<12} {'Avg Short':<12}")
    print("-"*70)

    for i, result in enumerate(results_summary[:10], 1):
        print(f"{i:<6} {result['pattern']:<25} {result['signals']:<10} "
              f"{result['win_rate']:>8.1f}% {result['avg_short_return']:>+10.1f}%")

    # Detailed analysis of top patterns
    print("\n" + "="*100)
    print("DETAILED ANALYSIS OF TOP 5 PATTERNS")
    print("="*100)

    for result in results_summary[:5]:
        pattern_name = result['pattern']
        signals = pattern_results[pattern_name]
        df = pd.DataFrame(signals)
        non_quality = df[df['category'] != 'quality']

        print(f"\n{'='*50}")
        print(f"PATTERN: {pattern_name}")
        print(f"{'='*50}")
        print(f"Total signals: {len(non_quality)}")
        print(f"Win rate: {result['win_rate']:.1f}%")
        print(f"Avg short return: {result['avg_short_return']:+.1f}%")

        # By year
        non_quality['year'] = pd.to_datetime(non_quality['date']).dt.year
        print(f"\nBy Year:")
        for year in sorted(non_quality['year'].unique()):
            yt = non_quality[non_quality['year'] == year]
            wr = (yt['fwd_12m'] < 0).mean() * 100
            ar = -yt['fwd_12m'].mean() * 100
            print(f"  {year}: {len(yt)} signals, Win {wr:.0f}%, Avg {ar:+.1f}%")

        # By category
        print(f"\nBy Category:")
        for cat in sorted(non_quality['category'].unique()):
            ct = non_quality[non_quality['category'] == cat]
            if len(ct) < 3:
                continue
            wr = (ct['fwd_12m'] < 0).mean() * 100
            ar = -ct['fwd_12m'].mean() * 100
            print(f"  {cat}: {len(ct)} signals, Win {wr:.0f}%, Avg {ar:+.1f}%")

    # Save results
    pd.DataFrame(results_summary).to_csv('pattern_analysis_results.csv', index=False)

    # Save all signals for top patterns
    for result in results_summary[:5]:
        pattern_name = result['pattern']
        signals = pattern_results[pattern_name]
        if signals:
            df = pd.DataFrame(signals)
            df.to_csv(f'signals_{pattern_name}.csv', index=False)

    print("\n" + "="*100)
    print("FILES SAVED")
    print("="*100)
    print("- pattern_analysis_results.csv: Summary of all patterns")
    print("- signals_*.csv: Individual signals for top patterns")


if __name__ == '__main__':
    main()
