# BTCRegimeHold4h Strategy Verification Guide

## Strategy Summary

**Claimed Performance:**
- 5-year backtest (May 2020 - Dec 2025): +2,756.88%
- 3-year backtest (Jan 2023 - Dec 2025): +663.37%
- vs Buy & Hold BTC: 3.4x better over 5 years

---

## Exact Strategy Logic

### Core Concept
A regime-based trend-following strategy that:
1. **Enters LONG** when price **crosses above** the 233-period SMA (with 0.5% buffer)
2. **Exits** when price **crosses below** the 233-period SMA
3. Uses **2x leverage** during bull regime
4. Stays in **cash** during bear regime (no shorting)

### Entry Condition (Crossover Detection)
```python
# Enter ONLY when price CROSSES from below to above MA
(
    (close[previous_candle] <= MA_233[previous_candle]) AND  # Was at or below MA
    (close[current_candle] > MA_233 * 1.005) AND             # Now above MA + 0.5% buffer
    (volume > 0)
)
```

### Exit Condition (Crossunder Detection)
```python
# Exit when price CROSSES from above to below MA
(
    (close[previous_candle] >= MA_233[previous_candle]) AND  # Was at or above MA
    (close[current_candle] < MA_233 * 0.995)                 # Now below MA - 0.5% buffer
)
```

### Key Parameters
| Parameter | Value | Description |
|-----------|-------|-------------|
| MA Period | 233 | Simple Moving Average period |
| Cross Buffer | 0.5% (0.005) | Buffer to avoid false signals |
| Timeframe | 4h | 4-hour candles |
| Leverage | 2x | During bull regime only |
| Stoploss | -25% | Wide stop, trusting MA exit |
| ROI | Disabled (100%) | Let position run |
| Trailing Stop | Disabled | Trust MA-based exit |
| Shorting | Disabled | Long only |
| Stake | 95% of available capital | Full investment during bull |

---

## Verification Instructions

### Prerequisites
```bash
# Install freqtrade
pip install freqtrade

# Install TA-Lib (required for indicators)
# macOS: brew install ta-lib
# Linux: apt-get install libta-lib-dev
pip install ta-lib
```

### Step 1: Download Historical Data
```bash
# Download 4h BTC/USDT futures data from Binance
freqtrade download-data \
    -c config.json \
    --timeframe 4h \
    --timerange 20200101- \
    --exchange binance \
    --trading-mode futures \
    --pairs BTC/USDT:USDT
```

### Step 2: Create Strategy File
Save as `user_data/strategies/BTCRegimeHold4h.py`:

```python
from datetime import datetime
from typing import Optional
from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter
from pandas import DataFrame
import talib.abstract as ta

class BTCRegimeHold4h(IStrategy):
    INTERFACE_VERSION = 3

    # Parameters
    ma_period = IntParameter(150, 250, default=233, space="buy", optimize=True)
    cross_buffer = DecimalParameter(0.005, 0.03, default=0.005, space="buy", optimize=True)

    # Settings
    minimal_roi = {"0": 100.0}  # Disabled
    stoploss = -0.25
    trailing_stop = False
    timeframe = '4h'
    can_short = False
    startup_candle_count = 250

    order_types = {
        'entry': 'limit',
        'exit': 'limit',
        'stoploss': 'market',
        'stoploss_on_exchange': True,
    }

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        for period in range(150, 251):
            dataframe[f'ma_{period}'] = ta.SMA(dataframe, timeperiod=period)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        ma_col = f'ma_{self.ma_period.value}'
        buffer_mult = 1 + self.cross_buffer.value

        # CROSSOVER: Was below MA, now above MA + buffer
        dataframe.loc[
            (
                (dataframe['close'].shift(1) <= dataframe[ma_col].shift(1)) &
                (dataframe['close'] > dataframe[ma_col] * buffer_mult) &
                (dataframe['volume'] > 0)
            ),
            'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        ma_col = f'ma_{self.ma_period.value}'
        buffer_mult = 1 - self.cross_buffer.value

        # CROSSUNDER: Was above MA, now below MA - buffer
        dataframe.loc[
            (
                (dataframe['close'].shift(1) >= dataframe[ma_col].shift(1)) &
                (dataframe['close'] < dataframe[ma_col] * buffer_mult)
            ),
            'exit_long'] = 1
        return dataframe

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: Optional[str],
                 side: str, **kwargs) -> float:
        return 2.0

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float],
                            max_stake: float, leverage: float, entry_tag: Optional[str],
                            side: str, **kwargs) -> float:
        return max_stake * 0.95
```

### Step 3: Create Config File
Save as `config.json`:

```json
{
    "max_open_trades": 3,
    "stake_currency": "USDT",
    "stake_amount": 100,
    "tradable_balance_ratio": 0.95,
    "timeframe": "4h",
    "dry_run": true,
    "dry_run_wallet": 1000,
    "trading_mode": "futures",
    "margin_mode": "isolated",
    "exchange": {
        "name": "binance",
        "pair_whitelist": ["BTC/USDT:USDT"],
        "pair_blacklist": []
    },
    "pairlists": [{"method": "StaticPairList"}],
    "telegram": {"enabled": false, "token": "", "chat_id": ""}
}
```

### Step 4: Run Backtests

**5-Year Backtest:**
```bash
freqtrade backtesting \
    -c config.json \
    --strategy BTCRegimeHold4h \
    --timerange 20200401-
```

**3-Year Backtest:**
```bash
freqtrade backtesting \
    -c config.json \
    --strategy BTCRegimeHold4h \
    --timerange 20230101-
```

---

## Expected Results

### 5-Year Backtest (May 2020 - Dec 2025)
| Metric | Expected Value |
|--------|----------------|
| Total Profit | ~2,700-2,800% |
| Trades | ~40-45 |
| Win Rate | ~30-35% |
| Best Trade | ~600%+ |
| Max Drawdown | ~50-60% |
| CAGR | ~80%+ |
| Market Change | ~800% |

### 3-Year Backtest (Jan 2023 - Dec 2025)
| Metric | Expected Value |
|--------|----------------|
| Total Profit | ~650-700% |
| Trades | ~20-25 |
| Win Rate | ~40-45% |
| Max Drawdown | ~15-20% |
| Market Change | ~429% |

---

## Key Points to Verify

1. **Crossover Logic**: Strategy should only enter when price CROSSES above MA, not on every candle above MA
2. **Trade Count**: Should see ~8 trades/year (not hundreds)
3. **Holding Duration**: Winners should average 50+ days, losers ~8 days
4. **Leverage Effect**: 2x leverage amplifies both gains and losses
5. **Full Capital**: Strategy uses 95% of capital, not fixed $100

---

## Common Verification Errors

### Error 1: Too Many Trades
If you see 100+ trades, the entry logic is wrong. Check that you're using the **crossover** condition (checking previous candle was below MA).

### Error 2: Poor Performance
If results are much worse, verify:
- Using SMA (not EMA) for the MA calculation
- MA period is 233 (not 200)
- Using 4h timeframe (not 1d)
- Cross buffer is 0.005 (0.5%)

### Error 3: Config Override
Freqtrade config.json overrides strategy settings. Ensure `timeframe` in config matches strategy.

---

## Prompt for AI Verification

Copy this prompt for another AI to verify:

```
I need you to verify a Bitcoin trading strategy backtest. Here are the exact specifications:

STRATEGY: 233-period SMA crossover with 0.5% buffer
- Enter LONG when: close crosses from below to above SMA(233) * 1.005
- Exit when: close crosses from below to above SMA(233) * 0.995
- Timeframe: 4h candles
- Leverage: 2x
- No shorting, no trailing stop, no ROI limit
- Uses 95% of capital per trade

BACKTEST PARAMETERS:
- Exchange: Binance Futures
- Pair: BTC/USDT perpetual
- Period: May 2020 to December 2025 (~5 years)
- Starting capital: $1,000

CLAIMED RESULTS:
- Total profit: +2,756.88%
- Final balance: $28,568
- 42 trades over 5 years
- 31% win rate
- Best trade: +614%
- Max drawdown: 57.96%
- CAGR: 81.17%

Please verify if these results are plausible by:
1. Checking the math (compounding 42 trades at avg 21% profit)
2. Comparing to BTC price history ($9,000 in May 2020 to ~$93,000 in Dec 2025)
3. Confirming the crossover logic would produce ~8 trades/year
4. Validating that 2x leverage on a regime strategy could achieve these returns

Key: The strategy rides entire bull runs (winners avg 59 days) and cuts losses quickly (losers avg 8 days). It captured the 2020-2021 bull run (+614% best trade) and the 2024-2025 bull run.
```

---

## Files in This Project

- `user_data/strategies/BTCRegimeHold4h.py` - The winning strategy
- `user_data/strategies/BTCRegimeHold.py` - Simplified version (different logic)
- `user_data/strategies/BTC200MARegime.py` - Earlier iteration
- `config.json` - Freqtrade configuration
- `STRATEGY_VERIFICATION.md` - This file

---

## Disclaimer

Past performance does not guarantee future results. This strategy:
- Had a 57.96% drawdown during the 2022 bear market
- Only 31% win rate (relies on big winners)
- Uses 2x leverage which amplifies risk
- Was backtested, not live traded
- May be subject to overfitting on the specific parameters

Always test with paper trading before risking real capital.
