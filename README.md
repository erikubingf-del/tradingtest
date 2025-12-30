# BTC Momentum Trading Bot

A Bitcoin futures trading bot using Freqtrade with a momentum-based strategy.

## Quick Start

### Prerequisites
- Docker and Docker Compose installed
- Binance Futures account (for live trading)

### 1. Download Historical Data

```bash
docker compose --profile download up download-data
```

This downloads BTC/USDT data from Jan 2024 to present.

### 2. Run Backtest

```bash
docker compose --profile backtest up backtesting
```

Check results in `user_data/backtest_results/`.

### 3. Optimize Strategy (Hyperopt)

```bash
docker compose --profile hyperopt up hyperopt
```

This runs 500 epochs to find optimal parameters. Results saved to `user_data/hyperopt_results/`.

### 4. Paper Trading (Dry Run)

```bash
docker compose up freqtrade
```

The bot runs in dry-run mode by default (`dry_run: true` in config.json).

Access the web UI at: http://localhost:8080
- Username: `freqtrade`
- Password: `your-secure-password` (change in config.json!)

### 5. Live Trading

**WARNING: Only do this after successful paper trading!**

1. Edit `config.json`:
   - Set `dry_run: false`
   - Add your Binance API keys:
     ```json
     "exchange": {
         "key": "your-api-key",
         "secret": "your-api-secret"
     }
     ```

2. Generate secure tokens:
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```
   Update `jwt_secret_key` and `ws_token` in config.json.

3. Start the bot:
   ```bash
   docker compose up -d freqtrade
   ```

## Strategy Overview

### BTCMomentum Strategy

| Parameter | Value |
|-----------|-------|
| Timeframe | 4 hours |
| Leverage | 3x |
| Stake per trade | $100 |
| Max open trades | 3 |
| Stop Loss | 2% |
| Take Profit | 4-6% |

### Entry Conditions (Long)
- Price above 50 EMA (uptrend)
- RSI crosses above 30 (oversold bounce)
- 20 EMA > 50 EMA (trend confirmation)
- Volume > 1.5x average
- MACD histogram positive

### Entry Conditions (Short)
- Price below 50 EMA (downtrend)
- RSI crosses below 70 (overbought rejection)
- 20 EMA < 50 EMA (trend confirmation)
- Volume > 1.5x average
- MACD histogram negative

### Risk Management
- 2% stop loss per trade
- Trailing stop: activates at 2% profit, trails at 1%
- Maximum 3 concurrent positions
- $100 per trade (configurable)

## Project Structure

```
tradingtest/
├── config.json                 # Main configuration
├── docker-compose.yml          # Docker services
├── requirements.txt            # Python dependencies
├── user_data/
│   ├── strategies/
│   │   └── BTCMomentum.py     # Main strategy
│   ├── data/                   # Downloaded price data
│   ├── logs/                   # Bot logs
│   ├── backtest_results/       # Backtest reports
│   └── hyperopt_results/       # Optimization results
└── hft/                        # HFT code (for future use)
    ├── backtest.py
    ├── strategy.py
    └── data_loader.py
```

## Commands Reference

| Command | Description |
|---------|-------------|
| `docker compose up freqtrade` | Start bot (dry-run by default) |
| `docker compose down` | Stop bot |
| `docker compose logs -f freqtrade` | View live logs |
| `docker compose --profile backtest up backtesting` | Run backtest |
| `docker compose --profile hyperopt up hyperopt` | Optimize parameters |
| `docker compose --profile download up download-data` | Download data |
| `docker compose --profile plot up plot` | Generate charts |

## Configuration

### Key Settings in config.json

| Setting | Description | Default |
|---------|-------------|---------|
| `dry_run` | Paper trading mode | `true` |
| `stake_amount` | USD per trade | `100` |
| `max_open_trades` | Maximum positions | `3` |
| `trading_mode` | Spot or futures | `futures` |

### Telegram Notifications (Optional)

1. Create a Telegram bot via [@BotFather](https://t.me/BotFather)
2. Get your chat ID via [@userinfobot](https://t.me/userinfobot)
3. Update config.json:
   ```json
   "telegram": {
       "enabled": true,
       "token": "your-bot-token",
       "chat_id": "your-chat-id"
   }
   ```

## Expected Performance

**Conservative Estimates (after optimization):**

| Metric | Target |
|--------|--------|
| Win Rate | 40-50% |
| Risk/Reward | 2:1 |
| Monthly Return | 5-15% |
| Max Drawdown | <20% |

**Disclaimer:** Past performance does not guarantee future results. Trading involves risk of loss.

## Troubleshooting

### "No data found" error
Run the data download first:
```bash
docker compose --profile download up download-data
```

### Strategy not found
Ensure the strategy name matches exactly:
- File: `user_data/strategies/BTCMomentum.py`
- Class: `BTCMomentum`
- Config/docker-compose: `--strategy BTCMomentum`

### API rate limits
The config includes rate limiting. If issues persist, increase `rateLimit` in config.json.

## Next Steps

1. **Backtest** - Run backtests to validate strategy
2. **Optimize** - Use hyperopt to find best parameters
3. **Paper Trade** - Test with fake money for 2+ weeks
4. **Live Trade** - Start with minimum position size
5. **Scale** - Gradually increase as confidence builds

## License

MIT
