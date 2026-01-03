#!/usr/bin/env python3
"""
SNIPER ALERT: Automated Put Options Scanner with Email Alerts
==============================================================

Scans for put options opportunities and sends email alerts.

Setup:
1. Create a Gmail App Password (not your regular password):
   - Go to https://myaccount.google.com/apppasswords
   - Generate an "App Password" for "Mail"

2. Set environment variables:
   export ALERT_EMAIL="your_email@gmail.com"
   export ALERT_PASSWORD="your_app_password"

3. Run manually or set up as cron job:
   python sniper_alert.py

4. For daily alerts, add to crontab:
   crontab -e
   # Run at 4:30 PM ET (after market close) every weekday
   30 16 * * 1-5 cd /path/to/tradingtest && python sniper_alert.py

Usage:
    python sniper_alert.py                    # Scan and email if signals found
    python sniper_alert.py --test             # Test email setup
    python sniper_alert.py --no-email         # Just print, no email
    python sniper_alert.py --always-email     # Email even if no signals
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import argparse
import warnings
import time
import sys
import os
import json
warnings.filterwarnings('ignore')

# ============================================================================
# STOCK UNIVERSE
# ============================================================================

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

HIGH_VOL = [
    'GME', 'AMC', 'BB', 'BBBY', 'WISH', 'CLOV', 'SOFI', 'PLTR', 'HOOD', 'UPST', 'AFRM',
    'SKLZ', 'OPEN', 'SPCE', 'ASTS', 'IONQ', 'DNA', 'RKLB',
    'MARA', 'RIOT', 'COIN', 'MSTR', 'HUT', 'BITF', 'CLSK', 'CIFR', 'CAN', 'GREE',
    'BTBT', 'SOS', 'BTDR', 'IREN', 'WULF',
    'RIVN', 'LCID', 'FSR', 'NKLA', 'GOEV', 'WKHS', 'RIDE', 'ARVL', 'FFIE', 'MULN',
    'PLUG', 'FCEL', 'BE', 'BLDP', 'BLNK', 'CHPT', 'STEM', 'RUN', 'NOVA', 'ARRY',
    'SHLS', 'MAXN', 'SPWR', 'SUNW', 'JKS', 'CSIQ', 'DQ',
    'BABA', 'JD', 'PDD', 'BIDU', 'NIO', 'XPEV', 'LI', 'BILI', 'TME', 'IQ',
    'DIDI', 'TAL', 'EDU', 'GOTU', 'YY', 'HUYA', 'DOYU', 'VIPS', 'ZH',
    'TLRY', 'CGC', 'ACB', 'CRON', 'SNDL', 'HEXO', 'OGI', 'VFF', 'GRWG',
    'PATH', 'DOCN', 'BILL', 'U', 'RBLX', 'SNOW', 'DDOG', 'NET', 'CRWD', 'ZS',
    'OKTA', 'MDB', 'ESTC', 'CFLT', 'GTLB', 'SUMO', 'NEWR', 'DT', 'HUBS',
    'BNTX', 'NVAX', 'SGEN', 'SRPT', 'BMRN', 'ALNY', 'RARE', 'IONS',
    'EXAS', 'PACB', 'TWST', 'BEAM', 'CRSP', 'NTLA', 'EDIT', 'VERV',
    'PTON', 'W', 'CHWY', 'FUBO', 'LAZR', 'VLDR', 'SNAP', 'ROKU', 'DOCU', 'ZM',
    'ASAN', 'FVRR', 'APPS', 'DKNG', 'PENN', 'DASH', 'ABNB', 'LYFT',
    'AAL', 'DAL', 'UAL', 'LUV', 'JBLU', 'SAVE', 'CCL', 'RCL', 'NCLH',
    'SHOP', 'SQ',
]

ALL_STOCKS = list(set(SP500 + HIGH_VOL))

# ============================================================================
# SCANNER FUNCTIONS
# ============================================================================

def scan_stock(ticker):
    """Scan a single stock for put opportunity."""
    try:
        stock = yf.Ticker(ticker)

        # Get 14 months of data
        df = stock.history(period='14mo')
        if len(df) < 252:
            return None

        df = df.reset_index()

        # Current price
        current_price = df['Close'].iloc[-1]

        # 52-week high
        high_52w = df['Close'].rolling(252).max().iloc[-1]
        pct_from_high = (current_price - high_52w) / high_52w

        # 12-month momentum
        if len(df) >= 252:
            price_12m_ago = df['Close'].iloc[-252]
            mom_12m = (current_price / price_12m_ago) - 1
        else:
            return None

        # RSI
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        rsi = (100 - (100 / (1 + rs))).iloc[-1]

        # Market cap
        info = stock.info
        market_cap = info.get('marketCap', 0) or 0

        # Check criteria: Mom >= 100%, Drop >= 50%, RSI < 60
        if mom_12m >= 1.0 and pct_from_high <= -0.50 and rsi < 60:
            return {
                'ticker': ticker,
                'price': current_price,
                'high_52w': high_52w,
                'pct_from_high': pct_from_high * 100,
                'mom_12m': mom_12m * 100,
                'rsi': rsi,
                'market_cap': market_cap / 1e9,  # In billions
                'premium_est': current_price * 0.12,  # 12% premium estimate
            }
        return None
    except Exception as e:
        return None


def run_scan():
    """Run full scan on all stocks."""
    print(f"Scanning {len(ALL_STOCKS)} stocks...")

    signals = []
    for i, ticker in enumerate(ALL_STOCKS):
        if (i + 1) % 50 == 0:
            print(f"  Progress: {i+1}/{len(ALL_STOCKS)}")

        result = scan_stock(ticker)
        if result:
            signals.append(result)

        time.sleep(0.05)  # Rate limit

    return signals


# ============================================================================
# EMAIL FUNCTIONS
# ============================================================================

def send_email(subject, body_html, body_text):
    """Send email alert."""
    email = os.environ.get('ALERT_EMAIL')
    password = os.environ.get('ALERT_PASSWORD')

    if not email or not password:
        print("ERROR: Email not configured. Set ALERT_EMAIL and ALERT_PASSWORD environment variables.")
        print("See script header for setup instructions.")
        return False

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = email
    msg['To'] = email

    msg.attach(MIMEText(body_text, 'plain'))
    msg.attach(MIMEText(body_html, 'html'))

    try:
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(email, password)
        server.sendmail(email, email, msg.as_string())
        server.quit()
        print(f"Email sent to {email}")
        return True
    except Exception as e:
        print(f"ERROR sending email: {e}")
        return False


def format_alert_email(signals):
    """Format signals as HTML email."""
    date_str = datetime.now().strftime('%Y-%m-%d')

    if not signals:
        body_html = f"""
        <html>
        <body>
        <h2>Sniper Scanner - {date_str}</h2>
        <p>No signals found today.</p>
        <p>Criteria: Momentum >= 100%, Drop >= 50%, RSI < 60</p>
        </body>
        </html>
        """
        body_text = f"Sniper Scanner - {date_str}\n\nNo signals found today."
        return "Sniper: No Signals", body_html, body_text

    # Build HTML table
    rows = ""
    for s in signals:
        rows += f"""
        <tr>
            <td><b>{s['ticker']}</b></td>
            <td>${s['price']:.2f}</td>
            <td>{s['pct_from_high']:.0f}%</td>
            <td>{s['mom_12m']:.0f}%</td>
            <td>{s['rsi']:.0f}</td>
            <td>${s['market_cap']:.1f}B</td>
            <td>${s['premium_est']:.2f}</td>
        </tr>
        """

    body_html = f"""
    <html>
    <body>
    <h2>🎯 SNIPER ALERT - {date_str}</h2>
    <p><b>{len(signals)} signal(s) found!</b></p>

    <table border="1" cellpadding="8" cellspacing="0">
    <tr style="background-color: #f0f0f0;">
        <th>Ticker</th>
        <th>Price</th>
        <th>From High</th>
        <th>12M Mom</th>
        <th>RSI</th>
        <th>Mkt Cap</th>
        <th>Put Premium</th>
    </tr>
    {rows}
    </table>

    <h3>Strategy:</h3>
    <ul>
        <li><b>Trade:</b> Buy 6-month ATM Put</li>
        <li><b>Size:</b> $1,000 per trade</li>
        <li><b>Hold:</b> Until expiration</li>
        <li><b>Expected:</b> 49% win rate, +87% avg return</li>
    </ul>

    <p style="color: gray; font-size: 12px;">
    Backtest (1998-2025): 253 trades, $219K total profit
    </p>
    </body>
    </html>
    """

    # Plain text version
    body_text = f"SNIPER ALERT - {date_str}\n\n"
    body_text += f"{len(signals)} signal(s) found:\n\n"
    for s in signals:
        body_text += f"{s['ticker']}: ${s['price']:.2f} ({s['pct_from_high']:.0f}% from high, {s['mom_12m']:.0f}% momentum)\n"

    subject = f"🎯 Sniper: {len(signals)} Signal(s) - {', '.join([s['ticker'] for s in signals[:3]])}"

    return subject, body_html, body_text


# ============================================================================
# HISTORY TRACKING (avoid duplicate alerts)
# ============================================================================

HISTORY_FILE = os.path.join(os.path.dirname(__file__), 'sniper_history.json')

def load_history():
    """Load alert history."""
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r') as f:
            return json.load(f)
    return {'alerted': {}}


def save_history(history):
    """Save alert history."""
    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f, indent=2)


def filter_new_signals(signals, history):
    """Filter out signals we've already alerted on recently."""
    today = datetime.now().strftime('%Y-%m-%d')
    new_signals = []

    for s in signals:
        ticker = s['ticker']
        last_alert = history['alerted'].get(ticker)

        # Alert if never alerted or last alert was > 7 days ago
        if not last_alert:
            new_signals.append(s)
            history['alerted'][ticker] = today
        else:
            last_date = datetime.strptime(last_alert, '%Y-%m-%d')
            if (datetime.now() - last_date).days > 7:
                new_signals.append(s)
                history['alerted'][ticker] = today

    return new_signals, history


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description='Sniper Scanner with Email Alerts')
    parser.add_argument('--test', action='store_true', help='Test email setup')
    parser.add_argument('--no-email', action='store_true', help='Print only, no email')
    parser.add_argument('--always-email', action='store_true', help='Email even if no signals')
    parser.add_argument('--ignore-history', action='store_true', help='Alert on all signals (ignore history)')
    args = parser.parse_args()

    print("="*60)
    print("SNIPER ALERT SCANNER")
    print("="*60)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"Stocks: {len(ALL_STOCKS)}")
    print()

    # Test mode
    if args.test:
        print("Testing email setup...")
        subject = "Sniper Alert - Test"
        body_html = "<h2>Test Email</h2><p>Your email alerts are working!</p>"
        body_text = "Test Email - Your email alerts are working!"
        success = send_email(subject, body_html, body_text)
        if success:
            print("SUCCESS! Email test passed.")
        return

    # Run scan
    signals = run_scan()

    print(f"\n{'='*60}")
    print(f"RESULTS: {len(signals)} signal(s) found")
    print("="*60)

    if signals:
        print(f"\n{'Ticker':<8} {'Price':>10} {'From High':>12} {'Momentum':>10} {'RSI':>8} {'Mkt Cap':>10}")
        print("-"*65)
        for s in signals:
            print(f"{s['ticker']:<8} ${s['price']:>8.2f} {s['pct_from_high']:>10.0f}% {s['mom_12m']:>9.0f}% {s['rsi']:>7.0f} ${s['market_cap']:>8.1f}B")
    else:
        print("\nNo signals today.")

    # Filter for new signals (unless ignoring history)
    if not args.ignore_history:
        history = load_history()
        new_signals, history = filter_new_signals(signals, history)
        save_history(history)

        if len(new_signals) < len(signals):
            print(f"\n({len(signals) - len(new_signals)} signal(s) already alerted recently)")
        signals = new_signals

    # Send email
    if not args.no_email:
        if signals or args.always_email:
            subject, body_html, body_text = format_alert_email(signals)
            print(f"\nSending email alert...")
            send_email(subject, body_html, body_text)
        else:
            print("\nNo new signals - skipping email.")

    # Save signals to CSV
    if signals:
        df = pd.DataFrame(signals)
        filename = f"signals_{datetime.now().strftime('%Y%m%d')}.csv"
        df.to_csv(filename, index=False)
        print(f"\nSignals saved to {filename}")


if __name__ == "__main__":
    main()
