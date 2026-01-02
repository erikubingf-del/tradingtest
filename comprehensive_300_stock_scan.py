#!/usr/bin/env python3
"""
COMPREHENSIVE 300+ STOCK SCANNER
================================

Scan 300+ stocks across 30-40 years to find put option opportunities
with high statistical confidence.

STOCK UNIVERSE:
- All S&P 500 stocks (current + historical)
- Nasdaq 100 stocks
- High-profile momentum stocks from each decade
- IPO bubbles and crashes

Run locally with: python comprehensive_300_stock_scan.py
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# ============================================================================
# COMPREHENSIVE STOCK UNIVERSE (300+ stocks across all sectors)
# ============================================================================

# Current S&P 500 top holdings + historical momentum stocks
STOCK_UNIVERSE = {
    # MEGA CAPS (Always in market)
    'mega_tech': [
        'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'TSLA',
        'AVGO', 'ORCL', 'CRM', 'ADBE', 'CSCO', 'ACN', 'IBM', 'INTC',
        'AMD', 'QCOM', 'TXN', 'NOW', 'INTU', 'AMAT', 'MU', 'LRCX',
        'ADI', 'KLAC', 'SNPS', 'CDNS', 'MRVL', 'NXPI', 'MCHP'
    ],

    # FINANCIALS
    'financials': [
        'JPM', 'BAC', 'WFC', 'GS', 'MS', 'C', 'BLK', 'SCHW', 'AXP',
        'SPGI', 'CME', 'ICE', 'MCO', 'MSCI', 'COF', 'USB', 'PNC',
        'TFC', 'BK', 'STT', 'DFS', 'AIG', 'MET', 'PRU', 'ALL'
    ],

    # HEALTHCARE
    'healthcare': [
        'UNH', 'JNJ', 'LLY', 'PFE', 'MRK', 'ABBV', 'TMO', 'ABT',
        'DHR', 'BMY', 'AMGN', 'GILD', 'ISRG', 'MDT', 'CVS', 'ELV',
        'CI', 'SYK', 'REGN', 'VRTX', 'BSX', 'ZTS', 'BDX', 'HUM'
    ],

    # CONSUMER
    'consumer': [
        'WMT', 'PG', 'KO', 'PEP', 'COST', 'HD', 'MCD', 'NKE', 'SBUX',
        'TGT', 'LOW', 'TJX', 'BKNG', 'MAR', 'CMG', 'YUM', 'DG', 'DLTR',
        'ORLY', 'AZO', 'ROST', 'ULTA', 'BBY', 'GM', 'F', 'TSLA'
    ],

    # ENERGY & MATERIALS
    'energy_materials': [
        'XOM', 'CVX', 'COP', 'SLB', 'EOG', 'MPC', 'PSX', 'VLO', 'OXY',
        'PXD', 'DVN', 'HES', 'HAL', 'BKR', 'FANG', 'LIN', 'APD', 'SHW',
        'ECL', 'DD', 'NEM', 'FCX', 'NUE', 'DOW', 'LYB', 'PPG'
    ],

    # INDUSTRIALS
    'industrials': [
        'CAT', 'DE', 'UNP', 'HON', 'BA', 'RTX', 'LMT', 'GE', 'MMM',
        'UPS', 'FDX', 'WM', 'ETN', 'ITW', 'EMR', 'PH', 'ROK', 'CMI',
        'NSC', 'CSX', 'PCAR', 'ODFL', 'GD', 'NOC', 'TT', 'CARR'
    ],

    # UTILITIES & REITS
    'utilities_reits': [
        'NEE', 'DUK', 'SO', 'D', 'AEP', 'SRE', 'EXC', 'XEL', 'PEG',
        'AWK', 'ES', 'WEC', 'ED', 'EIX', 'DTE', 'AMT', 'PLD', 'CCI',
        'EQIX', 'PSA', 'O', 'WELL', 'SPG', 'DLR', 'AVB', 'EQR'
    ],

    # TELECOM & MEDIA
    'telecom_media': [
        'T', 'VZ', 'TMUS', 'CMCSA', 'DIS', 'NFLX', 'WBD', 'PARA',
        'FOX', 'FOXA', 'OMC', 'IPG', 'EA', 'TTWO', 'ATVI', 'RBLX',
        'MTCH', 'ZG', 'PINS', 'SNAP', 'TWTR', 'SPOT', 'LYV', 'CHTR'
    ],

    # HIGH VOLATILITY / MEME STOCKS
    'high_vol_meme': [
        'GME', 'AMC', 'BBBY', 'BB', 'NOK', 'CLOV', 'WISH', 'WKHS',
        'RIDE', 'GOEV', 'NKLA', 'LCID', 'RIVN', 'FSR', 'QS', 'MVST',
        'SPCE', 'PLTR', 'SOFI', 'HOOD', 'UPST', 'AFRM', 'COIN', 'MARA'
    ],

    # CRYPTO & SPECULATIVE
    'crypto_spec': [
        'MARA', 'RIOT', 'COIN', 'MSTR', 'HUT', 'BITF', 'CLSK', 'CIFR',
        'BTBT', 'CAN', 'SOS', 'EBON', 'GREE', 'IREN', 'WULF', 'BTDR'
    ],

    # BIOTECH (High volatility)
    'biotech': [
        'MRNA', 'BNTX', 'NVAX', 'SGEN', 'BIIB', 'ALXN', 'ILMN', 'DXCM',
        'EXAS', 'ALGN', 'HOLX', 'IDXX', 'TECH', 'BIO', 'IONS', 'BMRN',
        'SAREPTA', 'JAZZ', 'NBIX', 'ALNY', 'EXEL', 'PCVX', 'RARE', 'RCUS'
    ],

    # CHINA / EMERGING MARKET ADRs
    'china_em': [
        'BABA', 'JD', 'PDD', 'BIDU', 'NIO', 'XPEV', 'LI', 'BILI',
        'TME', 'IQ', 'VIPS', 'YY', 'HUYA', 'DOYU', 'TAL', 'EDU',
        'GOTU', 'DIDI', 'LKNCY', 'GSX', 'ZH', 'MNSO', 'DDL', 'DAO'
    ],

    # SPAC & DE-SPAC (High crash potential)
    'spac_despac': [
        'PSTH', 'CCIV', 'IPOE', 'IPOF', 'DKNG', 'SKLZ', 'OPEN', 'CLOV',
        'BARK', 'BODY', 'PTRA', 'HIMS', 'OUST', 'MVST', 'VIEW', 'ASTS',
        'RDW', 'SLDP', 'IONQ', 'DNA', 'DNAY', 'VLD', 'JOBY', 'LILM'
    ],

    # DOT-COM ERA (Historical - some still exist)
    'dotcom_era': [
        'CSCO', 'INTC', 'MSFT', 'ORCL', 'DELL', 'HPQ', 'JNPR', 'EMC',
        'SUNW', 'YHOO', 'EBAY', 'AMZN', 'QCOM', 'AMAT', 'KLAC', 'LRCX',
        'NVDA', 'TXN', 'ADI', 'MXIM', 'XLNX', 'ALTR', 'BRCM', 'MRVL'
    ],

    # 2008 CRISIS STOCKS
    'crisis_2008': [
        'C', 'BAC', 'AIG', 'LEH', 'BSC', 'MER', 'WB', 'WM', 'CFC',
        'FNM', 'FRE', 'GS', 'MS', 'JPM', 'WFC', 'USB', 'PNC', 'KEY',
        'RF', 'STI', 'NCC', 'FITB', 'HBAN', 'MI', 'ZION', 'CMA'
    ],

    # RECENT IPOs (2019-2024)
    'recent_ipos': [
        'UBER', 'LYFT', 'PINS', 'ZM', 'CRWD', 'DDOG', 'NET', 'SNOW',
        'ABNB', 'DASH', 'RBLX', 'COIN', 'RIVN', 'LCID', 'HOOD', 'SOFI',
        'AFRM', 'PATH', 'DOCN', 'MNDY', 'APP', 'GLBE', 'GTLB', 'IOT'
    ],

    # CANNABIS (Highly volatile)
    'cannabis': [
        'TLRY', 'CGC', 'ACB', 'CRON', 'SNDL', 'HEXO', 'OGI', 'VFF',
        'GRWG', 'CURLF', 'GTBIF', 'TCNNF', 'CRLBF', 'TRSSF', 'MSOS'
    ],

    # CLEAN ENERGY (Bubble 2020-2021)
    'clean_energy': [
        'PLUG', 'FCEL', 'BLDP', 'BE', 'ENPH', 'SEDG', 'RUN', 'NOVA',
        'MAXN', 'ARRY', 'JKS', 'CSIQ', 'DQ', 'SPWR', 'SHLS', 'STEM'
    ],

    # TRAVEL & LEISURE (COVID crash)
    'travel_leisure': [
        'AAL', 'DAL', 'UAL', 'LUV', 'JBLU', 'ALK', 'SAVE', 'CCL',
        'RCL', 'NCLH', 'MAR', 'HLT', 'H', 'WH', 'EXPE', 'BKNG',
        'ABNB', 'TRIP', 'MTCH', 'LYV', 'SIX', 'FUN', 'SEAS', 'DRI'
    ],

    # SOFTWARE (High multiple / high crash potential)
    'software_saas': [
        'CRM', 'NOW', 'ADBE', 'INTU', 'WDAY', 'SPLK', 'PANW', 'OKTA',
        'ZS', 'CRWD', 'DDOG', 'NET', 'MDB', 'SNOW', 'PLTR', 'U',
        'DOCN', 'BILL', 'HUBS', 'VEEV', 'COUP', 'ZI', 'ESTC', 'CFLT'
    ],
}

# Flatten to unique list
ALL_STOCKS = list(set(
    stock
    for category in STOCK_UNIVERSE.values()
    for stock in category
))

print(f"Total unique stocks to scan: {len(ALL_STOCKS)}")

# ============================================================================
# DOWNLOAD AND ANALYZE
# ============================================================================

def download_stock_data(ticker, start='1985-01-01'):
    """Download historical data for a stock."""
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(start=start, end=datetime.now().strftime('%Y-%m-%d'))
        if len(df) < 252:  # Need at least 1 year
            return None
        df['ticker'] = ticker
        return df
    except Exception as e:
        return None


def calculate_indicators(df):
    """Calculate technical indicators."""
    df = df.copy()

    # Moving averages
    df['sma_50'] = df['Close'].rolling(50).mean()
    df['sma_200'] = df['Close'].rolling(200).mean()

    # Momentum
    df['mom_12m'] = df['Close'].pct_change(252)
    df['mom_6m'] = df['Close'].pct_change(126)
    df['mom_3m'] = df['Close'].pct_change(63)

    # 52-week high
    df['high_52w'] = df['Close'].rolling(252).max()
    df['pct_from_high'] = (df['Close'] - df['high_52w']) / df['high_52w']

    # RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))

    # Forward returns
    df['fwd_1m'] = df['Close'].shift(-21) / df['Close'] - 1
    df['fwd_3m'] = df['Close'].shift(-63) / df['Close'] - 1
    df['fwd_6m'] = df['Close'].shift(-126) / df['Close'] - 1
    df['fwd_12m'] = df['Close'].shift(-252) / df['Close'] - 1

    return df


def find_breakdown_signals(df, ticker):
    """Find breakdown signals in price data."""
    signals = []

    for i in range(252, len(df) - 126):  # Need history and forward data
        row = df.iloc[i]
        date = df.index[i]

        # Skip if missing data
        if pd.isna(row['mom_12m']) or pd.isna(row['fwd_6m']):
            continue

        # SIGNAL 1: Down 50%+ from high with prior momentum
        if row['pct_from_high'] < -0.50 and row['mom_12m'] > 0.5:
            signals.append({
                'date': date,
                'ticker': ticker,
                'pattern': 'down_50_from_high',
                'mom_12m': row['mom_12m'],
                'rsi': row['rsi'],
                'pct_from_high': row['pct_from_high'],
                'fwd_6m': row['fwd_6m'],
                'fwd_12m': row['fwd_12m'],
            })

        # SIGNAL 2: Death cross with high momentum
        if i > 0:
            prev = df.iloc[i-1]
            if (prev['sma_50'] > prev['sma_200'] and
                row['sma_50'] < row['sma_200'] and
                row['mom_12m'] > 0.5):
                signals.append({
                    'date': date,
                    'ticker': ticker,
                    'pattern': 'death_cross',
                    'mom_12m': row['mom_12m'],
                    'rsi': row['rsi'],
                    'pct_from_high': row['pct_from_high'],
                    'fwd_6m': row['fwd_6m'],
                    'fwd_12m': row['fwd_12m'],
                })

        # SIGNAL 3: Below 200 SMA after big run
        if row['Close'] < row['sma_200'] and row['mom_12m'] > 1.0:
            signals.append({
                'date': date,
                'ticker': ticker,
                'pattern': 'below_200sma',
                'mom_12m': row['mom_12m'],
                'rsi': row['rsi'],
                'pct_from_high': row['pct_from_high'],
                'fwd_6m': row['fwd_6m'],
                'fwd_12m': row['fwd_12m'],
            })

        # SIGNAL 4: RSI < 30 after 200%+ gain
        if row['rsi'] < 30 and row['mom_12m'] > 2.0:
            signals.append({
                'date': date,
                'ticker': ticker,
                'pattern': 'deep_oversold',
                'mom_12m': row['mom_12m'],
                'rsi': row['rsi'],
                'pct_from_high': row['pct_from_high'],
                'fwd_6m': row['fwd_6m'],
                'fwd_12m': row['fwd_12m'],
            })

    return signals


def calculate_put_return(stock_return_6m, premium_pct=0.12):
    """Calculate put option return based on stock movement."""
    if stock_return_6m < 0:
        intrinsic_value = abs(stock_return_6m)
        put_return = (intrinsic_value - premium_pct) / premium_pct
        put_return = min(put_return, 10.0)
    else:
        if stock_return_6m < 0.05:
            put_return = -0.80
        elif stock_return_6m < 0.15:
            put_return = -0.95
        else:
            put_return = -1.00
    return put_return


# ============================================================================
# MAIN SCAN
# ============================================================================

if __name__ == "__main__":
    print("="*100)
    print("COMPREHENSIVE 300+ STOCK PUT OPTIONS SCANNER")
    print("="*100)

    all_signals = []
    successful_stocks = 0
    failed_stocks = []

    for i, ticker in enumerate(ALL_STOCKS):
        print(f"\rProcessing {i+1}/{len(ALL_STOCKS)}: {ticker}...", end='', flush=True)

        df = download_stock_data(ticker)
        if df is None:
            failed_stocks.append(ticker)
            continue

        df = calculate_indicators(df)
        signals = find_breakdown_signals(df, ticker)

        if signals:
            all_signals.extend(signals)
            successful_stocks += 1

    print(f"\n\nScan Complete!")
    print(f"Successful stocks: {successful_stocks}")
    print(f"Failed stocks: {len(failed_stocks)}")
    print(f"Total signals found: {len(all_signals)}")

    if not all_signals:
        print("No signals found!")
        exit()

    # Convert to DataFrame
    signals_df = pd.DataFrame(all_signals)
    signals_df['date'] = pd.to_datetime(signals_df['date'])
    signals_df['year'] = signals_df['date'].dt.year

    # Calculate put returns
    signals_df['put_return'] = signals_df['fwd_6m'].apply(calculate_put_return)

    # ========================================================================
    # ANALYSIS
    # ========================================================================

    print("\n" + "="*100)
    print("PUT OPTIONS PERFORMANCE BY PATTERN")
    print("="*100)

    print(f"\n{'Pattern':<20} {'Signals':<10} {'Put Win%':<12} {'Avg Put Ret':<15}")
    print("-"*60)

    for pattern in signals_df['pattern'].unique():
        p_df = signals_df[signals_df['pattern'] == pattern]
        win_rate = (p_df['put_return'] > 0).mean() * 100
        avg_ret = p_df['put_return'].mean() * 100
        print(f"{pattern:<20} {len(p_df):<10} {win_rate:>8.1f}% {avg_ret:>+12.1f}%")

    # Best filter: High momentum + Low RSI
    print("\n" + "="*100)
    print("FILTERED STRATEGY: Momentum >= 100%, RSI < 50")
    print("="*100)

    filtered = signals_df[
        (signals_df['mom_12m'] >= 1.0) &
        (signals_df['rsi'] < 50)
    ].copy()

    print(f"\nTotal filtered signals: {len(filtered)}")
    print(f"Put Win Rate: {(filtered['put_return'] > 0).mean()*100:.1f}%")
    print(f"Average Put Return: {filtered['put_return'].mean()*100:+.1f}%")

    # Yearly performance
    print("\n" + "="*100)
    print("YEARLY PERFORMANCE (Filtered Strategy)")
    print("="*100)

    print(f"\n{'Year':<8} {'Trades':<10} {'Put Win%':<12} {'Avg Return':<15}")
    print("-"*50)

    # One trade per stock per quarter
    filtered['quarter'] = filtered['date'].dt.to_period('Q')
    deduped = filtered.drop_duplicates(subset=['ticker', 'quarter'])

    for year in sorted(deduped['year'].unique()):
        y_df = deduped[deduped['year'] == year]
        if len(y_df) == 0:
            continue
        win_rate = (y_df['put_return'] > 0).mean() * 100
        avg_ret = y_df['put_return'].mean() * 100
        print(f"{year:<8} {len(y_df):<10} {win_rate:>8.1f}% {avg_ret:>+12.1f}%")

    # Summary stats
    total_trades = len(deduped)
    years = deduped['year'].max() - deduped['year'].min() + 1
    trades_per_year = total_trades / years

    print("\n" + "="*100)
    print("SUMMARY STATISTICS")
    print("="*100)

    print(f"""
Stocks Analyzed: {successful_stocks}
Date Range: {signals_df['date'].min().strftime('%Y-%m-%d')} to {signals_df['date'].max().strftime('%Y-%m-%d')}
Years: {years}

Raw Signals: {len(signals_df)}
Filtered Signals (Mom>=100%, RSI<50): {len(filtered)}
Unique Trades (1 per stock/quarter): {total_trades}

Trades per Year: {trades_per_year:.1f}
Overall Win Rate: {(deduped['put_return'] > 0).mean()*100:.1f}%
Average Put Return: {deduped['put_return'].mean()*100:+.1f}%

Estimated Annual P&L ($1,000 per trade):
${trades_per_year * deduped['put_return'].mean() * 1000:,.0f}
""")

    # Save results
    signals_df.to_csv('comprehensive_signals_all.csv', index=False)
    deduped.to_csv('comprehensive_signals_filtered.csv', index=False)

    print("Saved: comprehensive_signals_all.csv, comprehensive_signals_filtered.csv")
