# Trend Following Backtesting System

A comprehensive Python backtesting system for trend-following strategies, designed to achieve **20% CAGR** over 10-year periods by scanning 50+ diversified assets.

## Research Foundation

This system is based on peer-reviewed research and proven methodologies:

### Academic Sources
- **AQR**: ["A Century of Evidence on Trend-Following Investing"](https://www.aqr.com/Insights/Research/Journal-Article/A-Century-of-Evidence-on-Trend-Following-Investing) - Demonstrates consistent profitability from 1880-2013
- **Moskowitz, Ooi, Pedersen (2012)**: "Time Series Momentum" - Journal of Financial Economics
- **Gary Antonacci**: ["Dual Momentum Investing"](https://www.optimalmomentum.com) - Combining absolute and relative momentum
- **Turtle Trading**: Original rules from Richard Dennis's 1983 experiment

### Key Findings
- Time series momentum has been profitable for 58 futures/forwards since 1985
- 12-month lookback period shows highest Sharpe ratio (1.17)
- Trend following generated positive returns in 8/10 of the largest equity drawdowns
- Volatility-scaled positions improve risk-adjusted returns

## Installation

```bash
# Clone and enter directory
cd tradingtest

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Quick Start

```bash
# Run basic backtest with combined strategy
python main.py --strategy combined --quick

# Full backtest with all assets
python main.py --strategy combined --start 2010-01-01 --end 2024-01-01

# Test specific strategy
python main.py --strategy turtle
python main.py --strategy momentum
python main.py --strategy dual_momentum
```

## Strategies Implemented

### 1. Turtle Trading (`turtle`)
The original breakout system from Richard Dennis:
- **Entry**: 20-day or 55-day Donchian channel breakout
- **Exit**: 10-day or 20-day opposite channel breakout
- **Position Sizing**: ATR-based (1% risk per unit)
- **Pyramiding**: Add every 0.5 ATR in profit direction
- **Stop Loss**: 2 × ATR from entry

### 2. Time Series Momentum (`momentum`)
Based on AQR and Moskowitz research:
- **Signal**: 12-month return (long if positive, short if negative)
- **Position Sizing**: Volatility-targeted (10% annual vol target)
- **Ensemble**: Option to combine 1, 3, 6, 12 month signals

### 3. Dual Momentum (`dual_momentum`)
Gary Antonacci's methodology:
- **Absolute Momentum**: Is return > 0?
- **Relative Momentum**: Does asset beat benchmark?
- **Signal**: Long only when both conditions met
- **Safety**: Move to bonds when momentum fails

### 4. Combined Strategy (`combined`)
Ensemble approach for robustness:
- Weights: Turtle (30%), Momentum (40%), MA Filter (30%)
- Entry only when signals agree (>50% threshold)
- Position sized by signal strength and volatility
- Scale-in: Start at 2%, increase to 10% as trend confirms

## Asset Universe

The system scans 50+ diversified assets:

| Category | Assets |
|----------|--------|
| US Equity | SPY, QQQ, IWM, DIA |
| International | EFA, EEM, VGK, EWJ, FXI |
| Commodities | GLD, SLV, USO, UNG, DBA |
| Bonds | TLT, IEF, LQD, HYG, TIP |
| Currencies | UUP, FXE, FXY, FXB, FXA |
| Crypto | BTC-USD, ETH-USD, SOL-USD... |
| Sectors | XLF, XLE, XLK, XLV... |

## Position Sizing Logic

Following your requirements:

1. **Initial Entry**: 2-5% of portfolio per asset
2. **Scale Up**: Add 2% when position shows 5% profit
3. **Maximum**: 10% per single asset
4. **Risk Per Trade**: 1-2% of portfolio
5. **Stops**: 2-3 ATR trailing stops

```python
# Example from position_sizing.py
class ScaleInManager:
    initial_pct = 0.02    # Start with 2%
    max_pct = 0.10        # Cap at 10%
    scale_threshold = 0.05 # Scale up after 5% profit
    scale_increment = 0.02 # Add 2% each time
```

## Advanced Usage

### Parameter Optimization
```bash
python main.py --optimize --strategy combined
```
Tests combinations of:
- Momentum lookback: 3, 6, 12 months
- Initial position: 2%, 3%, 5%
- Max position: 8%, 10%, 15%
- ATR stop: 1.5, 2.0, 2.5, 3.0

### Decade Analysis (20% CAGR Validation)
```bash
python main.py --decade-analysis
```
Tests rolling 10-year periods to validate 20% CAGR target.

### Walk-Forward Analysis
```bash
python main.py --walk-forward
```
Out-of-sample testing with 5-year training, 1-year testing.

### Monte Carlo Simulation
```bash
python main.py --monte-carlo --simulations 1000
```
Bootstrap simulation for robustness testing.

## Output Metrics

The system tracks comprehensive performance metrics:

| Metric | Description | Target |
|--------|-------------|--------|
| CAGR | Compound Annual Growth Rate | ≥20% |
| Sharpe | Risk-adjusted return | ≥1.0 |
| Max Drawdown | Largest peak-to-trough | <30% |
| Calmar | CAGR / Max Drawdown | ≥0.7 |
| Win Rate | Percentage profitable trades | >40% |
| Profit Factor | Gross wins / Gross losses | >1.5 |

## Configuration

Edit `config.py` to customize:

```python
@dataclass
class BacktestConfig:
    start_date: str = "1990-01-01"
    end_date: str = "2024-12-31"
    initial_capital: float = 100000.0
    target_cagr: float = 0.20  # 20% target

    # Risk settings
    risk.initial_position_pct = 0.02  # 2% initial
    risk.max_position_pct = 0.10      # 10% max
    risk.trailing_stop_atr = 3.0      # 3 ATR stop
```

## Project Structure

```
tradingtest/
├── main.py              # Entry point and CLI
├── config.py            # Configuration and asset universe
├── data_fetcher.py      # Multi-source data fetching
├── indicators.py        # Technical indicators
├── strategies.py        # Strategy implementations
├── position_sizing.py   # Position sizing and risk
├── backtester.py        # Backtesting engine
├── visualization.py     # Charts and reports
└── requirements.txt     # Dependencies
```

## Historical Performance Context

Based on research, here's what top trend followers achieved:

| Manager/Index | Period | CAGR | Notes |
|--------------|--------|------|-------|
| Dunn Capital | 1984-2019 | ~15% | Pure trend following |
| SG Trend Index | 2000-2022 | ~7% | CTA average |
| Turtle Traders | 1984-1988 | ~80% | During training |
| AQR Time Series Momentum | 1985-2012 | ~11% | Before fees |

**Important**: Achieving consistent 20% CAGR requires:
- Broad diversification (50+ markets)
- Low correlation between positions
- Disciplined execution
- Reasonable leverage (1-2x)

## Next Steps

1. **Run initial backtest** to establish baseline
2. **Optimize parameters** for your risk tolerance
3. **Validate with walk-forward** analysis
4. **Run Monte Carlo** for confidence intervals
5. **Paper trade** before live deployment

## License

MIT License - Use at your own risk. Past performance does not guarantee future results.

## References

1. [AQR - A Century of Evidence on Trend-Following](https://www.aqr.com/Insights/Research/Journal-Article/A-Century-of-Evidence-on-Trend-Following-Investing)
2. [Dual Momentum - Gary Antonacci](https://www.optimalmomentum.com)
3. [Turtle Trading Strategy](https://www.quantifiedstrategies.com/turtle-trading-strategy/)
4. [Time Series Momentum - Quantpedia](https://quantpedia.com/strategies/time-series-momentum-effect)
5. [CME - Trend Following with Managed Futures](https://www.cmegroup.com/education/articles-and-reports/trend-following-with-managed-futures-historical-perspectives.html)
