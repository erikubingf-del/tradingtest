#!/usr/bin/env python3
"""
SNIPER SCANNER V2: Comprehensive Put Options Finder
====================================================

Scans 600+ stocks for put options opportunities.
Includes S&P 500, Nasdaq 100, and high-volatility stocks.
Now includes SIGNAL AGE to show when signal first appeared.

Usage:
    python sniper_scanner_v2.py                    # Full scan
    python sniper_scanner_v2.py --min-cap 1000     # Min $1B market cap
    python sniper_scanner_v2.py --quick            # Quick scan (top 200 only)
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import argparse
import warnings
import time
import sys
warnings.filterwarnings('ignore')

# ============================================================================
# COMPREHENSIVE STOCK UNIVERSE - 600+ STOCKS
# ============================================================================

# S&P 500 (as of 2024)
SP500 = [
    'AAPL', 'ABBV', 'ABT', 'ACN', 'ADBE', 'ADI', 'ADM', 'ADP', 'ADSK', 'AEE',
    'AEP', 'AES', 'AFL', 'AIG', 'AIZ', 'AJG', 'AKAM', 'ALB', 'ALGN', 'ALL',
    'ALLE', 'AMAT', 'AMCR', 'AMD', 'AME', 'AMGN', 'AMP', 'AMT', 'AMZN', 'ANET',
    'ANSS', 'AON', 'AOS', 'APA', 'APD', 'APH', 'APTV', 'ARE', 'ATO', 'AVB',
    'AVGO', 'AVY', 'AWK', 'AXON', 'AXP', 'AZO', 'BA', 'BAC', 'BALL', 'BAX',
    'BBWI', 'BBY', 'BDX', 'BEN', 'BF-B', 'BG', 'BIIB', 'BIO', 'BK', 'BKNG',
    'BKR', 'BLDR', 'BLK', 'BMY', 'BR', 'BRK-B', 'BRO', 'BSX', 'BWA', 'BXP',
    'C', 'CAG', 'CAH', 'CARR', 'CAT', 'CB', 'CBOE', 'CBRE', 'CCI', 'CCL',
    'CDNS', 'CDW', 'CE', 'CEG', 'CF', 'CFG', 'CHD', 'CHRW', 'CHTR', 'CI',
    'CINF', 'CL', 'CLX', 'CMA', 'CMCSA', 'CME', 'CMG', 'CMI', 'CMS', 'CNC',
    'CNP', 'COF', 'COO', 'COP', 'COR', 'COST', 'CPAY', 'CPB', 'CPRT', 'CPT',
    'CRL', 'CRM', 'CSCO', 'CSGP', 'CSX', 'CTAS', 'CTLT', 'CTRA', 'CTSH', 'CTVA',
    'CVS', 'CVX', 'CZR', 'D', 'DAL', 'DD', 'DE', 'DECK', 'DFS', 'DG',
    'DGX', 'DHI', 'DHR', 'DIS', 'DLR', 'DLTR', 'DOC', 'DOV', 'DOW', 'DPZ',
    'DRI', 'DTE', 'DUK', 'DVA', 'DVN', 'DXCM', 'EA', 'EBAY', 'ECL', 'ED',
    'EFX', 'EG', 'EIX', 'EL', 'ELV', 'EMN', 'EMR', 'ENPH', 'EOG', 'EPAM',
    'EQIX', 'EQR', 'EQT', 'ES', 'ESS', 'ETN', 'ETR', 'ETSY', 'EVRG', 'EW',
    'EXC', 'EXPD', 'EXPE', 'EXR', 'F', 'FANG', 'FAST', 'FCX', 'FDS', 'FDX',
    'FE', 'FFIV', 'FI', 'FICO', 'FIS', 'FITB', 'FLT', 'FMC', 'FOX', 'FOXA',
    'FRT', 'FSLR', 'FTNT', 'FTV', 'GD', 'GDDY', 'GE', 'GEHC', 'GEN', 'GILD',
    'GIS', 'GL', 'GLW', 'GM', 'GNRC', 'GOOG', 'GOOGL', 'GPC', 'GPN', 'GRMN',
    'GS', 'GWW', 'HAL', 'HAS', 'HBAN', 'HCA', 'HD', 'HES', 'HIG', 'HII',
    'HLT', 'HOLX', 'HON', 'HPE', 'HPQ', 'HRL', 'HSIC', 'HST', 'HSY', 'HUBB',
    'HUM', 'HWM', 'IBM', 'ICE', 'IDXX', 'IEX', 'IFF', 'ILMN', 'INCY', 'INTC',
    'INTU', 'INVH', 'IP', 'IPG', 'IQV', 'IR', 'IRM', 'ISRG', 'IT', 'ITW',
    'IVZ', 'J', 'JBHT', 'JBL', 'JCI', 'JKHY', 'JNJ', 'JNPR', 'JPM', 'K',
    'KDP', 'KEY', 'KEYS', 'KHC', 'KIM', 'KLAC', 'KMB', 'KMI', 'KMX', 'KO',
    'KR', 'KVUE', 'L', 'LDOS', 'LEN', 'LH', 'LHX', 'LIN', 'LKQ', 'LLY',
    'LMT', 'LNT', 'LOW', 'LRCX', 'LULU', 'LUV', 'LVS', 'LW', 'LYB', 'LYV',
    'MA', 'MAA', 'MAR', 'MAS', 'MCD', 'MCHP', 'MCK', 'MCO', 'MDLZ', 'MDT',
    'MET', 'META', 'MGM', 'MHK', 'MKC', 'MKTX', 'MLM', 'MMC', 'MMM', 'MNST',
    'MO', 'MOH', 'MOS', 'MPC', 'MPWR', 'MRK', 'MRNA', 'MRO', 'MS', 'MSCI',
    'MSFT', 'MSI', 'MTB', 'MTCH', 'MTD', 'MU', 'NCLH', 'NDAQ', 'NDSN', 'NEE',
    'NEM', 'NFLX', 'NI', 'NKE', 'NOC', 'NOW', 'NRG', 'NSC', 'NTAP', 'NTRS',
    'NUE', 'NVDA', 'NVR', 'NWS', 'NWSA', 'NXPI', 'O', 'ODFL', 'OKE', 'OMC',
    'ON', 'ORCL', 'ORLY', 'OTIS', 'OXY', 'PANW', 'PARA', 'PAYC', 'PAYX', 'PCAR',
    'PCG', 'PEG', 'PEP', 'PFE', 'PFG', 'PG', 'PGR', 'PH', 'PHM', 'PKG',
    'PLD', 'PM', 'PNC', 'PNR', 'PNW', 'PODD', 'POOL', 'PPG', 'PPL', 'PRU',
    'PSA', 'PSX', 'PTC', 'PWR', 'PXD', 'PYPL', 'QCOM', 'QRVO', 'RCL', 'REG',
    'REGN', 'RF', 'RJF', 'RL', 'RMD', 'ROK', 'ROL', 'ROP', 'ROST', 'RSG',
    'RTX', 'RVTY', 'SBAC', 'SBUX', 'SCHW', 'SHW', 'SJM', 'SLB', 'SMCI', 'SNA',
    'SNPS', 'SO', 'SPG', 'SPGI', 'SRE', 'STE', 'STLD', 'STT', 'STX', 'STZ',
    'SWK', 'SWKS', 'SYF', 'SYK', 'SYY', 'T', 'TAP', 'TDG', 'TDY', 'TECH',
    'TEL', 'TER', 'TFC', 'TFX', 'TGT', 'TJX', 'TMO', 'TMUS', 'TPR', 'TRGP',
    'TRMB', 'TROW', 'TRV', 'TSCO', 'TSLA', 'TSN', 'TT', 'TTWO', 'TXN', 'TXT',
    'TYL', 'UAL', 'UBER', 'UDR', 'UHS', 'ULTA', 'UNH', 'UNP', 'UPS', 'URI',
    'USB', 'V', 'VFC', 'VICI', 'VLO', 'VLTO', 'VMC', 'VRSK', 'VRSN', 'VRTX',
    'VST', 'VTR', 'VTRS', 'VZ', 'WAB', 'WAT', 'WBA', 'WBD', 'WDC', 'WEC',
    'WELL', 'WFC', 'WM', 'WMB', 'WMT', 'WRB', 'WRK', 'WST', 'WTW', 'WY',
    'WYNN', 'XEL', 'XOM', 'XYL', 'YUM', 'ZBH', 'ZBRA', 'ZION', 'ZTS',
]

# High Volatility Stocks (great for puts)
HIGH_VOL = [
    # Meme/Retail
    'GME', 'AMC', 'BB', 'BBBY', 'WISH', 'CLOV', 'SOFI', 'PLTR', 'HOOD', 'UPST', 'AFRM',
    'SKLZ', 'OPEN', 'SPCE', 'ASTS', 'IONQ', 'DNA', 'RKLB',

    # Crypto miners
    'MARA', 'RIOT', 'COIN', 'MSTR', 'HUT', 'BITF', 'CLSK', 'CIFR', 'CAN', 'GREE',
    'BTBT', 'SOS', 'BTDR', 'IREN', 'WULF',

    # EV / Clean Energy
    'RIVN', 'LCID', 'FSR', 'NKLA', 'GOEV', 'WKHS', 'RIDE', 'ARVL', 'FFIE', 'MULN',
    'PLUG', 'FCEL', 'BE', 'BLDP', 'BLNK', 'CHPT', 'STEM', 'RUN', 'NOVA', 'ARRY',
    'SHLS', 'MAXN', 'SPWR', 'SUNW', 'JKS', 'CSIQ', 'DQ',

    # China ADRs
    'BABA', 'JD', 'PDD', 'BIDU', 'NIO', 'XPEV', 'LI', 'BILI', 'TME', 'IQ',
    'DIDI', 'TAL', 'EDU', 'GOTU', 'YY', 'HUYA', 'DOYU', 'VIPS', 'ZH',

    # Cannabis
    'TLRY', 'CGC', 'ACB', 'CRON', 'SNDL', 'HEXO', 'OGI', 'VFF', 'GRWG',

    # High-vol Software/Tech
    'PATH', 'DOCN', 'BILL', 'U', 'RBLX', 'SNOW', 'DDOG', 'NET', 'CRWD', 'ZS',
    'OKTA', 'MDB', 'ESTC', 'CFLT', 'GTLB', 'SUMO', 'NEWR', 'DT', 'HUBS',

    # Biotech (high IV)
    'MRNA', 'BNTX', 'NVAX', 'SGEN', 'SRPT', 'BMRN', 'ALNY', 'RARE', 'IONS',
    'EXAS', 'PACB', 'TWST', 'BEAM', 'CRSP', 'NTLA', 'EDIT', 'VERV',

    # Other volatile
    'PTON', 'W', 'CHWY', 'FUBO', 'LAZR', 'VLDR', 'SNAP', 'ROKU', 'DOCU', 'ZM',
    'ASAN', 'FVRR', 'APPS', 'DKNG', 'PENN', 'DASH', 'ABNB', 'LYFT', 'UBER',

    # Travel/Cruise (volatile)
    'AAL', 'DAL', 'UAL', 'LUV', 'JBLU', 'SAVE', 'CCL', 'RCL', 'NCLH',

    # Retail
    'ETSY', 'SHOP', 'SQ', 'PYPL', 'AFRM', 'UPST',
]

# Combine all stocks
ALL_STOCKS = list(set(SP500 + HIGH_VOL))
print(f"Total stocks in universe: {len(ALL_STOCKS)}")

# ============================================================================
# SCANNER FUNCTIONS
# ============================================================================

def get_stock_data(ticker, retries=2):
    """Fetch stock data with retry logic."""
    for attempt in range(retries):
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            market_cap = info.get('marketCap', 0) or 0

            df = stock.history(period='15mo')
            if len(df) < 200:
                return None

            df = df.reset_index()
            df['Date'] = pd.to_datetime(df['Date']).dt.tz_localize(None)

            current_price = df['Close'].iloc[-1]
            high_52w = df['Close'].rolling(252, min_periods=200).max().iloc[-1]

            # 12-month momentum
            if len(df) >= 252:
                price_12m_ago = df['Close'].iloc[-252]
                momentum_12m = (current_price / price_12m_ago - 1) * 100
            else:
                price_start = df['Close'].iloc[0]
                days = len(df)
                momentum_12m = ((current_price / price_start - 1) * (252 / days)) * 100

            # Drop from high
            pct_from_high = (current_price / high_52w - 1) * 100

            # RSI
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss
            rsi = (100 - (100 / (1 + rs))).iloc[-1]

            # Moving averages
            sma_50 = df['Close'].rolling(50).mean().iloc[-1]
            sma_200 = df['Close'].rolling(200).mean().iloc[-1] if len(df) >= 200 else current_price

            # Calculate signal age (when did signal first appear?)
            signal_age_info = calculate_signal_age(df)

            return {
                'ticker': ticker,
                'price': current_price,
                'market_cap': market_cap,
                'market_cap_B': market_cap / 1e9,
                'high_52w': high_52w,
                'momentum_12m': momentum_12m,
                'pct_from_high': pct_from_high,
                'rsi': rsi,
                'below_sma_50': current_price < sma_50,
                'below_sma_200': current_price < sma_200,
                'df': df,  # Keep dataframe for signal age calculation
                **signal_age_info,
            }
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(0.5)
            continue
    return None


def calculate_signal_age(df, min_momentum=1.0, min_drop=-0.50, max_rsi=60):
    """Calculate when the signal first appeared."""
    try:
        # Calculate indicators for full history
        df = df.copy()
        df['high_52w'] = df['Close'].rolling(252, min_periods=200).max()
        df['pct_from_high'] = (df['Close'] - df['high_52w']) / df['high_52w']
        df['mom_12m'] = df['Close'].pct_change(252)

        # RSI
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))

        # Check signal for each day
        df['signal'] = (
            (df['mom_12m'] >= min_momentum) &
            (df['pct_from_high'] <= min_drop) &
            (df['rsi'] < max_rsi)
        )

        # Find first signal in recent history (last 60 days)
        recent = df.tail(60)
        signals = recent[recent['signal'] == True]

        if len(signals) == 0:
            return {
                'signal_age_days': None,
                'first_signal_date': None,
                'first_signal_price': None,
                'price_since_signal': None,
                'action': 'NO_SIGNAL',
            }

        first_signal_date = signals['Date'].iloc[0]
        first_signal_price = signals['Close'].iloc[0]
        current_price = df['Close'].iloc[-1]
        days_since = (datetime.now() - first_signal_date).days
        price_change = (current_price / first_signal_price - 1) * 100

        # Determine action
        if days_since <= 5:
            action = 'ENTER'
        elif days_since <= 10 and price_change < 15:
            action = 'ENTER'
        elif days_since <= 14 and price_change < 10:
            action = 'CAUTION'
        else:
            action = 'SKIP'

        return {
            'signal_age_days': days_since,
            'first_signal_date': first_signal_date.strftime('%Y-%m-%d'),
            'first_signal_price': first_signal_price,
            'price_since_signal': price_change,
            'action': action,
        }

    except Exception as e:
        return {
            'signal_age_days': None,
            'first_signal_date': None,
            'first_signal_price': None,
            'price_since_signal': None,
            'action': 'UNKNOWN',
        }


def check_entry_signal(data, min_momentum=100, min_drop=50, max_rsi=60):
    """Check if stock meets entry criteria."""
    if data is None:
        return False, []

    signals = []
    has_momentum = data['momentum_12m'] >= min_momentum
    has_dropped = data['pct_from_high'] <= -min_drop
    rsi_ok = data['rsi'] < max_rsi

    if has_momentum:
        signals.append(f"Mom: +{data['momentum_12m']:.0f}%")
    if has_dropped:
        signals.append(f"Drop: {data['pct_from_high']:.0f}%")
    if rsi_ok:
        signals.append(f"RSI: {data['rsi']:.0f}")
    if data['below_sma_200']:
        signals.append("Below 200SMA")

    return (has_momentum and has_dropped and rsi_ok), signals


def estimate_premium(data):
    """Estimate 6-month ATM put premium."""
    drop = abs(data['pct_from_high'])
    if drop > 70:
        pct = 0.20
    elif drop > 60:
        pct = 0.15
    elif drop > 50:
        pct = 0.12
    else:
        pct = 0.10
    return pct, data['price'] * pct * 100


def run_scan(stocks, min_cap=500, min_momentum=100, min_drop=50, max_rsi=60):
    """Run the full scan."""
    results = []
    errors = []

    total = len(stocks)
    for i, ticker in enumerate(stocks):
        pct = (i + 1) / total * 100
        print(f"\r  [{pct:5.1f}%] Scanning {ticker:<6} ({i+1}/{total})...", end='', flush=True)

        data = get_stock_data(ticker)
        if data is None:
            errors.append(ticker)
            continue

        # Market cap filter
        if data['market_cap'] < min_cap * 1e6:
            continue

        is_signal, signals = check_entry_signal(data, min_momentum, min_drop, max_rsi)

        if is_signal:
            prem_pct, prem_dollar = estimate_premium(data)
            data['signals'] = signals
            data['premium_pct'] = prem_pct
            data['premium_dollar'] = prem_dollar
            results.append(data)

        time.sleep(0.05)  # Rate limiting

    print(f"\r  [100.0%] Complete! Found {len(results)} opportunities.              ")
    return results, errors


def display_results(results):
    """Display scan results."""
    if not results:
        print("\n" + "="*100)
        print("NO OPPORTUNITIES FOUND TODAY")
        print("="*100)
        print("\nThis is normal - we expect ~8 trades per year.")
        print("Run the scanner daily to catch opportunities.")
        return

    # Sort by action priority (ENTER first) then by drop
    action_priority = {'ENTER': 0, 'CAUTION': 1, 'SKIP': 2, 'UNKNOWN': 3, 'NO_SIGNAL': 4}
    results = sorted(results, key=lambda x: (action_priority.get(x.get('action', 'UNKNOWN'), 3), x['pct_from_high']))

    print("\n" + "="*100)
    print(f"🎯 FOUND {len(results)} PUT OPPORTUNITIES")
    print("="*100)

    # Signal age legend
    print("\n📊 ACTION GUIDE: ✅ ENTER = Fresh signal | ⚠️ CAUTION = Consider entry | ❌ SKIP = Too old")

    print(f"\n{'Ticker':<7} {'Price':<9} {'Drop':<8} {'Mom12m':<8} {'RSI':<5} {'Signal Age':<12} {'Since Signal':<14} {'Action'}")
    print("-"*100)

    for r in results:
        # Format signal age
        age = r.get('signal_age_days')
        if age is not None:
            age_str = f"{age}d ago"
            first_date = r.get('first_signal_date', '')[:10]
        else:
            age_str = "N/A"
            first_date = ""

        # Format price change since signal
        price_chg = r.get('price_since_signal')
        if price_chg is not None:
            price_chg_str = f"{price_chg:+.1f}%"
        else:
            price_chg_str = "N/A"

        # Format action with emoji
        action = r.get('action', 'UNKNOWN')
        if action == 'ENTER':
            action_str = "✅ ENTER"
        elif action == 'CAUTION':
            action_str = "⚠️  CAUTION"
        elif action == 'SKIP':
            action_str = "❌ SKIP"
        else:
            action_str = "❓ CHECK"

        print(f"{r['ticker']:<7} ${r['price']:<7.2f} {r['pct_from_high']:>+5.0f}% {r['momentum_12m']:>+6.0f}% {r['rsi']:>4.0f} {age_str:<12} {price_chg_str:<14} {action_str}")

    # Detailed recommendations
    print("\n" + "="*100)
    print("DETAILED ANALYSIS")
    print("="*100)

    for r in results:
        action = r.get('action', 'UNKNOWN')
        age = r.get('signal_age_days', 'N/A')
        first_date = r.get('first_signal_date', 'N/A')
        first_price = r.get('first_signal_price')
        price_chg = r.get('price_since_signal')

        if action == 'ENTER':
            emoji = "✅"
            recommendation = "ENTER NOW - Fresh signal, good entry point"
        elif action == 'CAUTION':
            emoji = "⚠️"
            recommendation = "CAUTION - Signal is aging, consider entry but not ideal"
        elif action == 'SKIP':
            emoji = "❌"
            recommendation = "SKIP - Signal too old or price moved too much"
        else:
            emoji = "❓"
            recommendation = "Check manually"

        price_at_signal = f"${first_price:.2f}" if first_price else "N/A"
        price_chg_str = f"{price_chg:+.1f}%" if price_chg is not None else "N/A"

        print(f"""
{emoji} {r['ticker']}
   Current Price: ${r['price']:.2f} (down {abs(r['pct_from_high']):.0f}% from ${r['high_52w']:.2f} high)
   12M Momentum: {r['momentum_12m']:+.0f}%  |  RSI: {r['rsi']:.0f}

   Signal First Appeared: {first_date} ({age} days ago)
   Price at Signal: {price_at_signal}
   Price Change Since: {price_chg_str}

   {recommendation}

   TRADE: Buy 6-month ATM Put @ ${r['price']:.0f} strike
   Est. Premium: ${r['premium_dollar']:,.0f}/contract ({r['premium_pct']*100:.0f}%)
""")


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Sniper Scanner V2')
    parser.add_argument('--min-cap', type=int, default=500, help='Min market cap in $M (default: 500)')
    parser.add_argument('--min-momentum', type=int, default=100, help='Min 12m momentum %% (default: 100)')
    parser.add_argument('--min-drop', type=int, default=50, help='Min drop from high %% (default: 50)')
    parser.add_argument('--max-rsi', type=int, default=60, help='Max RSI (default: 60)')
    parser.add_argument('--quick', action='store_true', help='Quick scan (volatile stocks only)')

    args = parser.parse_args()

    print("""
╔══════════════════════════════════════════════════════════════════════════════════════════════╗
║                           SNIPER SCANNER V2 - Put Options Finder                             ║
║                                                                                              ║
║  Scans 600+ stocks for crashed hype stocks                                                   ║
║  Strategy: Buy puts on stocks that gained 100%+ then crashed 50%+                            ║
║                                                                                              ║
║  Historical Performance (1998-2025):                                                         ║
║  • Win Rate: 49%                                                                             ║
║  • Avg Return: +85%                                                                          ║
║  • Annual P&L: +$6,600                                                                       ║
╚══════════════════════════════════════════════════════════════════════════════════════════════╝
    """)

    # Select stock universe
    if args.quick:
        stocks = HIGH_VOL
        print(f"Quick scan mode: {len(stocks)} volatile stocks")
    else:
        stocks = ALL_STOCKS
        print(f"Full scan mode: {len(stocks)} stocks")

    print(f"Filters: Market Cap > ${args.min_cap}M, Momentum > {args.min_momentum}%, Drop > {args.min_drop}%, RSI < {args.max_rsi}")
    print()

    results, errors = run_scan(
        stocks,
        min_cap=args.min_cap,
        min_momentum=args.min_momentum,
        min_drop=args.min_drop,
        max_rsi=args.max_rsi
    )

    display_results(results)

    if errors and len(errors) <= 20:
        print(f"\n⚠️  Could not fetch: {', '.join(errors)}")
    elif errors:
        print(f"\n⚠️  Could not fetch {len(errors)} stocks")

    print("\n" + "="*100)
    print("Run daily. When opportunity found:")
    print("  1. Verify options liquidity (bid-ask spread < 10%)")
    print("  2. Buy 6-month ATM put")
    print("  3. Position size: $1,000 per trade")
    print("="*100)
