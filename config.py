"""
Trend Following Backtesting System - Configuration

Based on research from:
- AQR "A Century of Evidence on Trend-Following Investing"
- Turtle Trading Rules (Richard Dennis & William Eckhardt)
- Dual Momentum (Gary Antonacci)
- Moskowitz, Ooi, Pedersen (2012) "Time Series Momentum"
"""

from dataclasses import dataclass, field
from typing import List, Dict
from datetime import datetime


@dataclass
class TurtleConfig:
    """
    Turtle Trading System Configuration
    Based on the original Turtle Trading rules from 1983
    """
    # Entry channels
    system1_entry_days: int = 20  # Short-term breakout
    system2_entry_days: int = 55  # Long-term breakout

    # Exit channels
    system1_exit_days: int = 10   # Exit on 10-day low/high
    system2_exit_days: int = 20   # Exit on 20-day low/high

    # Position sizing
    atr_period: int = 20          # N calculation period
    risk_per_trade: float = 0.01  # 1% risk per unit
    max_units_per_market: int = 4 # Max 4 units per market
    max_correlated_units: int = 10  # Max units in correlated markets
    max_direction_units: int = 12   # Max units in one direction

    # Pyramiding
    pyramid_threshold: float = 0.5  # Add every 0.5N above entry

    # Stop loss
    stop_atr_multiple: float = 2.0  # 2N stop loss

    # Drawdown rule
    drawdown_threshold: float = 0.10  # 10% drawdown triggers reduction
    position_reduction: float = 0.20   # Reduce by 20%


@dataclass
class MomentumConfig:
    """
    Time Series Momentum Configuration
    Based on AQR research and Moskowitz et al. (2012)
    """
    # Lookback periods to test
    lookback_months: int = 12     # Standard 12-month lookback
    holding_period_months: int = 1  # Monthly rebalancing

    # Alternative lookback periods for ensemble
    alt_lookbacks: List[int] = field(default_factory=lambda: [1, 3, 6, 12])

    # Volatility targeting
    target_volatility: float = 0.10  # 10% annualized vol target
    vol_lookback: int = 60          # 60-day realized vol


@dataclass
class DualMomentumConfig:
    """
    Dual Momentum Configuration
    Based on Gary Antonacci's research
    """
    # Lookback period
    lookback_months: int = 12

    # Absolute momentum threshold (use cash if below)
    abs_momentum_threshold: float = 0.0  # Must beat cash

    # Relative momentum: compare against benchmark
    use_relative_momentum: bool = True


@dataclass
class MovingAverageConfig:
    """
    Moving Average Crossover Configuration
    Classic trend following
    """
    fast_period: int = 50
    slow_period: int = 200

    # Alternative: single MA trend filter
    trend_filter_period: int = 200


@dataclass
class RiskManagement:
    """
    Portfolio-level risk management
    """
    # Position sizing
    initial_position_pct: float = 0.02   # Start with 2% of portfolio
    max_position_pct: float = 0.10       # Max 10% per asset
    scale_up_threshold: float = 0.05     # Scale up after 5% profit
    scale_up_increment: float = 0.02     # Add 2% on scale up

    # Portfolio limits
    max_total_exposure: float = 1.0      # 100% max long exposure
    max_correlated_exposure: float = 0.30  # 30% in correlated assets

    # Stop losses
    trailing_stop_atr: float = 3.0       # 3 ATR trailing stop
    hard_stop_pct: float = 0.20          # 20% max loss per position

    # Correlation thresholds
    correlation_threshold: float = 0.70  # Consider correlated if > 0.7


@dataclass
class TransactionCosts:
    """
    Realistic transaction cost modeling
    """
    # Slippage (% of price)
    slippage_pct: float = 0.001   # 0.1% slippage

    # Commission structure
    commission_pct: float = 0.001  # 0.1% commission
    min_commission: float = 1.0    # Minimum $1

    # Crypto-specific
    crypto_slippage_pct: float = 0.002  # Higher for crypto
    crypto_commission_pct: float = 0.001


@dataclass
class BacktestConfig:
    """
    Main backtesting configuration
    """
    # Date range
    start_date: str = "1990-01-01"
    end_date: str = "2024-12-31"

    # Initial capital
    initial_capital: float = 100000.0

    # Target CAGR (for validation)
    target_cagr: float = 0.20  # 20% target

    # Rebalancing frequency
    rebalance_frequency: str = "monthly"  # daily, weekly, monthly

    # Strategy to use
    strategy: str = "combined"  # turtle, momentum, dual_momentum, combined

    # Sub-configs
    turtle: TurtleConfig = field(default_factory=TurtleConfig)
    momentum: MomentumConfig = field(default_factory=MomentumConfig)
    dual_momentum: DualMomentumConfig = field(default_factory=DualMomentumConfig)
    moving_average: MovingAverageConfig = field(default_factory=MovingAverageConfig)
    risk: RiskManagement = field(default_factory=RiskManagement)
    costs: TransactionCosts = field(default_factory=TransactionCosts)


# Asset Universe - 50+ diversified assets across multiple classes
ASSET_UNIVERSE = {
    # US Equity Indices
    "equity_us": [
        ("SPY", "S&P 500 ETF"),
        ("QQQ", "NASDAQ 100 ETF"),
        ("IWM", "Russell 2000 ETF"),
        ("DIA", "Dow Jones ETF"),
    ],

    # International Equity
    "equity_intl": [
        ("EFA", "MSCI EAFE ETF"),
        ("EEM", "Emerging Markets ETF"),
        ("VGK", "Europe ETF"),
        ("EWJ", "Japan ETF"),
        ("FXI", "China Large Cap ETF"),
        ("EWZ", "Brazil ETF"),
        ("INDA", "India ETF"),
    ],

    # Commodities
    "commodities": [
        ("GLD", "Gold ETF"),
        ("SLV", "Silver ETF"),
        ("USO", "Oil ETF"),
        ("UNG", "Natural Gas ETF"),
        ("DBA", "Agriculture ETF"),
        ("DBB", "Base Metals ETF"),
        ("PDBC", "Optimum Yield Diversified Commodity"),
    ],

    # Bonds
    "bonds": [
        ("TLT", "20+ Year Treasury ETF"),
        ("IEF", "7-10 Year Treasury ETF"),
        ("LQD", "Investment Grade Corporate ETF"),
        ("HYG", "High Yield Corporate ETF"),
        ("TIP", "TIPS ETF"),
    ],

    # Currencies (via ETFs)
    "currencies": [
        ("UUP", "US Dollar Index ETF"),
        ("FXE", "Euro ETF"),
        ("FXY", "Japanese Yen ETF"),
        ("FXB", "British Pound ETF"),
        ("FXA", "Australian Dollar ETF"),
        ("FXC", "Canadian Dollar ETF"),
    ],

    # Real Estate
    "real_estate": [
        ("VNQ", "US REIT ETF"),
        ("VNQI", "International REIT ETF"),
    ],

    # Sector ETFs (for rotation)
    "sectors": [
        ("XLF", "Financials"),
        ("XLE", "Energy"),
        ("XLK", "Technology"),
        ("XLV", "Healthcare"),
        ("XLI", "Industrials"),
        ("XLP", "Consumer Staples"),
        ("XLY", "Consumer Discretionary"),
        ("XLU", "Utilities"),
        ("XLB", "Materials"),
    ],

    # Cryptocurrencies (using proxy ETFs or direct tickers)
    "crypto": [
        ("BTC-USD", "Bitcoin"),
        ("ETH-USD", "Ethereum"),
        ("SOL-USD", "Solana"),
        ("AVAX-USD", "Avalanche"),
        ("MATIC-USD", "Polygon"),
        ("LINK-USD", "Chainlink"),
        ("ADA-USD", "Cardano"),
        ("DOT-USD", "Polkadot"),
    ],
}

# For longer historical backtests (pre-ETF era), use futures proxies
FUTURES_PROXIES = {
    # Equity indices - use index data
    "^GSPC": "S&P 500 Index",
    "^DJI": "Dow Jones Industrial",
    "^IXIC": "NASDAQ Composite",

    # Commodities - futures continuous
    "GC=F": "Gold Futures",
    "SI=F": "Silver Futures",
    "CL=F": "Crude Oil Futures",
    "NG=F": "Natural Gas Futures",
    "ZC=F": "Corn Futures",
    "ZS=F": "Soybean Futures",
    "ZW=F": "Wheat Futures",
    "KC=F": "Coffee Futures",
    "CT=F": "Cotton Futures",
    "HG=F": "Copper Futures",

    # Currencies
    "EURUSD=X": "EUR/USD",
    "GBPUSD=X": "GBP/USD",
    "USDJPY=X": "USD/JPY",
    "AUDUSD=X": "AUD/USD",
    "USDCAD=X": "USD/CAD",
    "USDCHF=X": "USD/CHF",

    # Bonds (Treasury yield proxies)
    "^TNX": "10-Year Treasury Yield",
    "^TYX": "30-Year Treasury Yield",
}

# Correlation groups for risk management
CORRELATION_GROUPS = {
    "us_equity": ["SPY", "QQQ", "IWM", "DIA"],
    "intl_equity": ["EFA", "EEM", "VGK", "EWJ"],
    "precious_metals": ["GLD", "SLV"],
    "energy": ["USO", "UNG", "XLE"],
    "bonds": ["TLT", "IEF", "LQD"],
    "crypto_major": ["BTC-USD", "ETH-USD"],
    "crypto_alt": ["SOL-USD", "AVAX-USD", "MATIC-USD", "ADA-USD"],
}


def get_full_universe() -> List[str]:
    """Get all tickers from the asset universe."""
    tickers = []
    for category, assets in ASSET_UNIVERSE.items():
        for ticker, name in assets:
            tickers.append(ticker)
    return tickers


def get_category_tickers(category: str) -> List[str]:
    """Get tickers for a specific category."""
    if category in ASSET_UNIVERSE:
        return [ticker for ticker, name in ASSET_UNIVERSE[category]]
    return []
