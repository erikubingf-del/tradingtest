"""
FUTURES DATA LOADER - Professional Grade
=========================================
Loads back-adjusted continuous futures from multiple sources:
1. User-provided CSVs (CSI, Norgate, Kibot format)
2. Quandl/Nasdaq Data Link (CHRIS database - free tier)
3. Yahoo Finance (as fallback proxy)

Contract Specifications:
- Multipliers, tick sizes, tick values
- Margin requirements
- Roll cost estimates

Usage:
    loader = FuturesDataLoader(data_dir='./futures_data')
    data = loader.load_all_contracts(start_date='1990-01-01')
"""

import pandas as pd
import numpy as np
import os
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# =============================================================================
# CONTRACT SPECIFICATIONS (Professional CTA Standard)
# =============================================================================

@dataclass
class ContractSpec:
    """Futures contract specifications"""
    symbol: str
    name: str
    exchange: str
    multiplier: float      # Point value (dollars per point)
    tick_size: float       # Minimum price movement
    tick_value: float      # Dollar value per tick
    margin: float          # Approximate initial margin
    sector: str            # Asset class
    quandl_code: str       # Quandl CHRIS database code
    csi_code: str          # CSI Data code
    start_year: int        # Data available from

# Complete CTA universe with accurate specifications
CONTRACT_SPECS: Dict[str, ContractSpec] = {
    # EQUITY INDICES
    'ES': ContractSpec('ES', 'E-mini S&P 500', 'CME', 50.0, 0.25, 12.50, 12980, 'Equity',
                       'CME_ES', 'ES', 1997),
    'NQ': ContractSpec('NQ', 'E-mini Nasdaq 100', 'CME', 20.0, 0.25, 5.00, 17600, 'Equity',
                       'CME_NQ', 'NQ', 1999),
    'RTY': ContractSpec('RTY', 'E-mini Russell 2000', 'CME', 50.0, 0.10, 5.00, 7150, 'Equity',
                        'CME_RTY', 'RTY', 2002),
    'YM': ContractSpec('YM', 'E-mini Dow Jones', 'CBOT', 5.0, 1.00, 5.00, 9900, 'Equity',
                       'CBOT_YM', 'YM', 2002),

    # FIXED INCOME
    'ZN': ContractSpec('ZN', '10-Year Treasury Note', 'CBOT', 1000.0, 0.015625, 15.625, 2090, 'Bonds',
                       'CBOT_TY', 'TY', 1982),
    'ZB': ContractSpec('ZB', '30-Year Treasury Bond', 'CBOT', 1000.0, 0.03125, 31.25, 4400, 'Bonds',
                       'CBOT_US', 'US', 1977),
    'ZF': ContractSpec('ZF', '5-Year Treasury Note', 'CBOT', 1000.0, 0.0078125, 7.8125, 1320, 'Bonds',
                       'CBOT_FV', 'FV', 1988),
    'ZT': ContractSpec('ZT', '2-Year Treasury Note', 'CBOT', 2000.0, 0.0078125, 15.625, 880, 'Bonds',
                       'CBOT_TU', 'TU', 1990),

    # ENERGY
    'CL': ContractSpec('CL', 'Crude Oil WTI', 'NYMEX', 1000.0, 0.01, 10.00, 6380, 'Energy',
                       'CME_CL', 'CL', 1983),
    'NG': ContractSpec('NG', 'Natural Gas', 'NYMEX', 10000.0, 0.001, 10.00, 2640, 'Energy',
                       'CME_NG', 'NG', 1990),
    'HO': ContractSpec('HO', 'Heating Oil', 'NYMEX', 42000.0, 0.0001, 4.20, 5500, 'Energy',
                       'CME_HO', 'HO', 1978),
    'RB': ContractSpec('RB', 'RBOB Gasoline', 'NYMEX', 42000.0, 0.0001, 4.20, 6600, 'Energy',
                       'CME_RB', 'RB', 2005),

    # METALS
    'GC': ContractSpec('GC', 'Gold', 'COMEX', 100.0, 0.10, 10.00, 9900, 'Metals',
                       'CME_GC', 'GC', 1974),
    'SI': ContractSpec('SI', 'Silver', 'COMEX', 5000.0, 0.005, 25.00, 11000, 'Metals',
                       'CME_SI', 'SI', 1963),
    'HG': ContractSpec('HG', 'Copper', 'COMEX', 25000.0, 0.0005, 12.50, 4950, 'Metals',
                       'CME_HG', 'HG', 1959),
    'PL': ContractSpec('PL', 'Platinum', 'NYMEX', 50.0, 0.10, 5.00, 2750, 'Metals',
                       'CME_PL', 'PL', 1968),

    # GRAINS
    'ZC': ContractSpec('ZC', 'Corn', 'CBOT', 50.0, 0.25, 12.50, 1540, 'Grains',
                       'CBOT_C', 'C', 1959),
    'ZS': ContractSpec('ZS', 'Soybeans', 'CBOT', 50.0, 0.25, 12.50, 2475, 'Grains',
                       'CBOT_S', 'S', 1959),
    'ZW': ContractSpec('ZW', 'Wheat', 'CBOT', 50.0, 0.25, 12.50, 1980, 'Grains',
                       'CBOT_W', 'W', 1959),
    'ZM': ContractSpec('ZM', 'Soybean Meal', 'CBOT', 100.0, 0.10, 10.00, 2200, 'Grains',
                       'CBOT_SM', 'SM', 1959),
    'ZL': ContractSpec('ZL', 'Soybean Oil', 'CBOT', 600.0, 0.01, 6.00, 1430, 'Grains',
                       'CBOT_BO', 'BO', 1959),

    # CURRENCIES
    'EC': ContractSpec('EC', 'Euro FX', 'CME', 125000.0, 0.00005, 6.25, 2310, 'FX',
                       'CME_EC', 'EC', 1999),
    'JY': ContractSpec('JY', 'Japanese Yen', 'CME', 12500000.0, 0.0000005, 6.25, 3300, 'FX',
                       'CME_JY', 'JY', 1972),
    'BP': ContractSpec('BP', 'British Pound', 'CME', 62500.0, 0.0001, 6.25, 2640, 'FX',
                       'CME_BP', 'BP', 1972),
    'CD': ContractSpec('CD', 'Canadian Dollar', 'CME', 100000.0, 0.00005, 5.00, 1100, 'FX',
                       'CME_CD', 'CD', 1972),
    'SF': ContractSpec('SF', 'Swiss Franc', 'CME', 125000.0, 0.0001, 12.50, 3850, 'FX',
                       'CME_SF', 'SF', 1972),
    'AD': ContractSpec('AD', 'Australian Dollar', 'CME', 100000.0, 0.0001, 10.00, 1540, 'FX',
                       'CME_AD', 'AD', 1987),
    'DX': ContractSpec('DX', 'US Dollar Index', 'ICE', 1000.0, 0.005, 5.00, 2200, 'FX',
                       'ICE_DX', 'DX', 1985),

    # SOFTS
    'KC': ContractSpec('KC', 'Coffee C', 'ICE', 375.0, 0.05, 18.75, 5500, 'Softs',
                       'ICE_KC', 'KC', 1972),
    'SB': ContractSpec('SB', 'Sugar #11', 'ICE', 1120.0, 0.01, 11.20, 1210, 'Softs',
                       'ICE_SB', 'SB', 1961),
    'CT': ContractSpec('CT', 'Cotton #2', 'ICE', 500.0, 0.01, 5.00, 2750, 'Softs',
                       'ICE_CT', 'CT', 1959),
    'CC': ContractSpec('CC', 'Cocoa', 'ICE', 10.0, 1.00, 10.00, 2310, 'Softs',
                       'ICE_CC', 'CC', 1959),
    'OJ': ContractSpec('OJ', 'Orange Juice', 'ICE', 150.0, 0.05, 7.50, 1650, 'Softs',
                       'ICE_OJ', 'OJ', 1966),

    # MEATS
    'LC': ContractSpec('LC', 'Live Cattle', 'CME', 400.0, 0.025, 10.00, 2200, 'Meats',
                       'CME_LC', 'LC', 1964),
    'LH': ContractSpec('LH', 'Lean Hogs', 'CME', 400.0, 0.025, 10.00, 1320, 'Meats',
                       'CME_LH', 'LH', 1966),
    'FC': ContractSpec('FC', 'Feeder Cattle', 'CME', 500.0, 0.025, 12.50, 3300, 'Meats',
                       'CME_FC', 'FC', 1971),
}

# Subset for the classic 18-market CTA portfolio
CLASSIC_CTA_UNIVERSE = [
    'ES', 'NQ', 'RTY',           # Equity indices
    'ZN', 'ZB',                   # Bonds
    'CL', 'NG',                   # Energy
    'GC', 'SI', 'HG',            # Metals
    'ZC', 'ZS', 'ZW',            # Grains
    'DX',                         # Currency (Dollar Index)
    'KC', 'SB', 'CT', 'CC'       # Softs
]

# =============================================================================
# DATA LOADER CLASS
# =============================================================================

class FuturesDataLoader:
    """
    Professional futures data loader supporting multiple sources.
    """

    def __init__(self, data_dir: str = './futures_data'):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self.specs = CONTRACT_SPECS

    def load_from_csv(self, symbol: str, filepath: str) -> Optional[pd.DataFrame]:
        """
        Load continuous futures data from CSV file.

        Expected format (CSI/Norgate/Kibot compatible):
        Date,Open,High,Low,Close,Volume[,OpenInterest]

        Date format: YYYY-MM-DD or MM/DD/YYYY
        """
        try:
            # Try different date formats
            for date_format in ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y']:
                try:
                    df = pd.read_csv(filepath, parse_dates=['Date'], index_col='Date',
                                    date_format=date_format)
                    break
                except:
                    continue
            else:
                # Try pandas auto-detection
                df = pd.read_csv(filepath, parse_dates=['Date'], index_col='Date')

            # Standardize column names
            df.columns = [c.strip().capitalize() for c in df.columns]

            # Ensure required columns
            required = ['Open', 'High', 'Low', 'Close']
            for col in required:
                if col not in df.columns:
                    print(f"  Warning: {symbol} missing column {col}")
                    return None

            # Add Volume if missing
            if 'Volume' not in df.columns:
                df['Volume'] = 0

            df = df[['Open', 'High', 'Low', 'Close', 'Volume']]
            df = df.sort_index()

            return df

        except Exception as e:
            print(f"  Error loading {symbol} from {filepath}: {e}")
            return None

    def load_from_quandl(self, symbol: str, start_date: str = '1990-01-01') -> Optional[pd.DataFrame]:
        """
        Load from Quandl/Nasdaq Data Link CHRIS database (free tier).

        Note: Requires `pip install nasdaq-data-link` and API key for full access.
        Free tier has limited history.
        """
        try:
            import nasdaqdatalink as ndl

            spec = self.specs.get(symbol)
            if not spec:
                return None

            # Try CHRIS database (continuous futures)
            quandl_code = f"CHRIS/{spec.quandl_code}1"

            df = ndl.get(quandl_code, start_date=start_date)

            # Standardize columns
            col_map = {
                'Open': 'Open', 'High': 'High', 'Low': 'Low',
                'Settle': 'Close', 'Last': 'Close', 'Close': 'Close',
                'Volume': 'Volume', 'Prev. Day Open Interest': 'OI'
            }

            df = df.rename(columns=col_map)

            if 'Close' not in df.columns:
                # Try to find close price column
                for col in df.columns:
                    if 'close' in col.lower() or 'settle' in col.lower():
                        df['Close'] = df[col]
                        break

            df = df[['Open', 'High', 'Low', 'Close', 'Volume']].dropna()

            return df

        except ImportError:
            print(f"  nasdaq-data-link not installed. Run: pip install nasdaq-data-link")
            return None
        except Exception as e:
            print(f"  Quandl error for {symbol}: {e}")
            return None

    def load_from_yahoo_proxy(self, symbol: str, start_date: str = '1990-01-01') -> Optional[pd.DataFrame]:
        """
        Load ETF proxy data from Yahoo Finance (fallback).
        """
        import yfinance as yf

        # ETF proxy mapping
        PROXY_MAP = {
            'ES': ('SPY', 10),    # Scale factor to approximate futures price
            'NQ': ('QQQ', 40),
            'RTY': ('IWM', 10),
            'ZN': ('IEF', 1.1),
            'ZB': ('TLT', 0.8),
            'CL': ('USO', 1),
            'NG': ('UNG', 1),
            'GC': ('GLD', 5),
            'SI': ('SLV', 1),
            'HG': ('CPER', 1),
            'ZC': ('CORN', 1),
            'ZS': ('SOYB', 1),
            'ZW': ('WEAT', 1),
            'DX': ('UUP', 4),
            'KC': ('JO', 1),
            'SB': ('CANE', 1),
            'CT': ('BAL', 1),
            'CC': ('NIB', 1),
        }

        if symbol not in PROXY_MAP:
            return None

        ticker, scale = PROXY_MAP[symbol]

        try:
            df = yf.download(ticker, start=start_date, progress=False)

            if len(df) < 252:
                return None

            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.droplevel(1)

            df = df[['Open', 'High', 'Low', 'Close', 'Volume']].copy()

            # Scale to approximate futures prices
            for col in ['Open', 'High', 'Low', 'Close']:
                df[col] = df[col] * scale

            return df

        except Exception as e:
            print(f"  Yahoo error for {symbol}: {e}")
            return None

    def load_all_contracts(self,
                          symbols: List[str] = None,
                          start_date: str = '1990-01-01',
                          prefer_source: str = 'csv') -> Dict[str, pd.DataFrame]:
        """
        Load all contracts from available sources.

        Priority:
        1. User CSV files in data_dir
        2. Quandl/Nasdaq Data Link
        3. Yahoo Finance proxy

        Args:
            symbols: List of symbols to load (default: CLASSIC_CTA_UNIVERSE)
            start_date: Start date for data
            prefer_source: 'csv', 'quandl', or 'yahoo'
        """
        if symbols is None:
            symbols = CLASSIC_CTA_UNIVERSE

        print("=" * 70)
        print("LOADING FUTURES DATA")
        print("=" * 70)

        data = {}

        for symbol in symbols:
            print(f"\n{symbol} ({self.specs.get(symbol, ContractSpec(symbol, '', '', 0, 0, 0, 0, '', '', '', 1990)).name}):")

            df = None

            # 1. Try user CSV
            csv_paths = [
                os.path.join(self.data_dir, f"{symbol}.csv"),
                os.path.join(self.data_dir, f"{symbol}_continuous.csv"),
                os.path.join(self.data_dir, f"{symbol.lower()}.csv"),
            ]

            for csv_path in csv_paths:
                if os.path.exists(csv_path):
                    df = self.load_from_csv(symbol, csv_path)
                    if df is not None:
                        print(f"  Loaded from CSV: {len(df)} bars")
                        break

            # 2. Try Quandl
            if df is None and prefer_source in ['quandl', 'all']:
                df = self.load_from_quandl(symbol, start_date)
                if df is not None:
                    print(f"  Loaded from Quandl: {len(df)} bars")

            # 3. Try Yahoo proxy
            if df is None:
                df = self.load_from_yahoo_proxy(symbol, start_date)
                if df is not None:
                    print(f"  Loaded from Yahoo (proxy): {len(df)} bars")

            if df is not None:
                # Validate and clean
                df = df.dropna()
                df = df[df['Close'] > 0]
                df = df[~df.index.duplicated(keep='first')]
                df = df.sort_index()

                if len(df) > 252:
                    data[symbol] = df
                    # Save to CSV for caching
                    cache_path = os.path.join(self.data_dir, f"{symbol}_continuous.csv")
                    df.to_csv(cache_path)
                else:
                    print(f"  Skipped: insufficient data ({len(df)} bars)")
            else:
                print(f"  FAILED: no data source available")

        # Save contract specifications
        self.save_specifications()

        print(f"\n{'='*70}")
        print(f"Loaded {len(data)} contracts")
        print(f"Data directory: {self.data_dir}")

        return data

    def save_specifications(self):
        """Save contract specifications to CSV"""
        specs_list = []
        for symbol, spec in self.specs.items():
            specs_list.append(asdict(spec))

        df = pd.DataFrame(specs_list)
        df.to_csv(os.path.join(self.data_dir, 'contract_specifications.csv'), index=False)

    def get_spec(self, symbol: str) -> Optional[ContractSpec]:
        """Get contract specification for a symbol"""
        return self.specs.get(symbol)

# =============================================================================
# DATA VALIDATION
# =============================================================================

def validate_data(data: Dict[str, pd.DataFrame]) -> Dict[str, dict]:
    """
    Validate loaded data and report statistics.
    """
    print("\n" + "=" * 70)
    print("DATA VALIDATION REPORT")
    print("=" * 70)

    stats = {}

    for symbol, df in data.items():
        spec = CONTRACT_SPECS.get(symbol)

        stat = {
            'start_date': df.index[0].strftime('%Y-%m-%d'),
            'end_date': df.index[-1].strftime('%Y-%m-%d'),
            'total_bars': len(df),
            'years': (df.index[-1] - df.index[0]).days / 365.25,
            'missing_pct': df.isna().sum().sum() / (len(df) * len(df.columns)) * 100,
            'zero_volume_pct': (df['Volume'] == 0).sum() / len(df) * 100,
        }

        stats[symbol] = stat

        print(f"\n{symbol}:")
        print(f"  Period: {stat['start_date']} to {stat['end_date']} ({stat['years']:.1f} years)")
        print(f"  Bars: {stat['total_bars']:,}")
        if stat['missing_pct'] > 0:
            print(f"  Missing: {stat['missing_pct']:.2f}%")

    # Summary
    print("\n" + "-" * 70)
    min_years = min(s['years'] for s in stats.values())
    max_years = max(s['years'] for s in stats.values())
    print(f"Data range: {min_years:.1f} to {max_years:.1f} years")

    return stats

# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    import sys

    # Check for nasdaq-data-link
    try:
        import nasdaqdatalink
        print("nasdaq-data-link is installed")
    except ImportError:
        print("nasdaq-data-link not installed. Install with: pip install nasdaq-data-link")
        print("Set API key with: nasdaqdatalink.ApiConfig.api_key = 'YOUR_KEY'")

    # Load data
    loader = FuturesDataLoader(data_dir='./futures_data')

    # Use Yahoo proxies as fallback
    data = loader.load_all_contracts(
        symbols=CLASSIC_CTA_UNIVERSE,
        start_date='2005-01-01',
        prefer_source='yahoo'  # Will use CSV if available, then fallback to Yahoo
    )

    # Validate
    if len(data) > 0:
        stats = validate_data(data)

        print("\n" + "=" * 70)
        print("INSTRUCTIONS FOR REAL FUTURES DATA")
        print("=" * 70)
        print("""
To use real continuous futures data:

1. NORGATE DATA (Recommended - $50/month):
   - Download: https://norgatedata.com/
   - Export continuous contracts as CSV
   - Place in ./futures_data/ as {SYMBOL}.csv

2. CSI DATA ($20/month):
   - Download: https://www.csidata.com/
   - Export back-adjusted continuous contracts
   - Format: Date,Open,High,Low,Close,Volume

3. QUANDL/NASDAQ DATA LINK (Free tier available):
   - pip install nasdaq-data-link
   - Get API key from https://data.nasdaq.com/
   - Set: nasdaqdatalink.ApiConfig.api_key = 'YOUR_KEY'

4. KIBOT ($60 one-time):
   - Download: https://www.kibot.com/
   - Provides back-adjusted continuous futures

CSV Format Required:
-------------------
Date,Open,High,Low,Close,Volume
2020-01-02,3257.50,3258.25,3253.00,3257.75,1234567
...

File naming: {SYMBOL}.csv or {SYMBOL}_continuous.csv
Example: ES.csv, CL.csv, GC.csv, etc.
        """)
