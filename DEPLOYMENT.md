# BTCRegimeHold4h - Binance Deployment Guide

## Quick Start

### Step 1: Get Binance API Keys

1. Go to [Binance](https://www.binance.com) and log in
2. Navigate to **Account** → **API Management**
3. Create a new API key with these permissions:
   - **Enable Reading** (required)
   - **Enable Futures** (required for trading)
   - **Enable Spot & Margin Trading** (optional)
4. **IP Whitelist**: Add your server's IP address for security
5. Save your **API Key** and **Secret Key** (shown only once)

### Step 2: Configure API Keys

Edit `config-production.json` and add your keys:

```json
"exchange": {
    "name": "binance",
    "key": "YOUR_API_KEY_HERE",
    "secret": "YOUR_SECRET_KEY_HERE",
    ...
}
```

Also change these security settings:
```json
"api_server": {
    "jwt_secret_key": "GENERATE_A_32_CHAR_RANDOM_STRING",
    "ws_token": "GENERATE_ANOTHER_RANDOM_STRING",
    "password": "YOUR_SECURE_PASSWORD"
}
```

### Step 3: Fund Your Binance Futures Account

1. Transfer USDT to your **Futures Wallet** (not Spot)
2. Recommended starting capital: $500-2000
3. The bot uses 95% of available balance per trade with 2x leverage

### Step 4: Run in Dry-Run Mode First (Recommended)

The config is set to `"dry_run": true` by default. This simulates trades without risking real money.

```bash
# Start the bot in dry-run mode
docker compose up -d

# View logs
docker compose logs -f freqtrade

# Check status via web UI
# Open http://localhost:8080 in browser
# Login: freqtrade / YOUR_SECURE_PASSWORD
```

Let it run for a few days to verify it's working correctly.

### Step 5: Go Live

Once you're confident, edit `config-production.json`:

```json
"dry_run": false,
```

Then restart:
```bash
docker compose down
docker compose up -d
```

---

## Commands Reference

```bash
# Start the bot
docker compose up -d

# Stop the bot
docker compose down

# View real-time logs
docker compose logs -f freqtrade

# Download historical data
docker compose --profile download run --rm download-data

# Run backtest
docker compose --profile backtest run --rm backtesting

# Restart after config changes
docker compose restart freqtrade
```

---

## Strategy Details

**BTCRegimeHold4h** - 233 SMA Crossover Strategy

| Parameter | Value |
|-----------|-------|
| MA Period | 233 |
| Buffer | 0.5% |
| Timeframe | 4h |
| Leverage | 2x |
| Stoploss | -25% |
| Position Size | 95% of capital |

**Entry**: When price crosses FROM BELOW to ABOVE SMA(233) * 1.005
**Exit**: When price crosses FROM ABOVE to BELOW SMA(233) * 0.995

**Backtest Results (2020-2025)**:
- Total Profit: +2,756.88%
- Trades: 42
- Win Rate: 31%
- Max Drawdown: 57.96%

---

## Monitoring

### Web UI
- URL: http://localhost:8080
- Username: freqtrade
- Password: (set in config)

### Telegram Notifications (Optional)

1. Create a bot via [@BotFather](https://t.me/BotFather)
2. Get your chat_id from [@userinfobot](https://t.me/userinfobot)
3. Update config-production.json:

```json
"telegram": {
    "enabled": true,
    "token": "YOUR_BOT_TOKEN",
    "chat_id": "YOUR_CHAT_ID"
}
```

---

## Risk Management

1. **Start Small**: Begin with $500-1000 until you trust the system
2. **Max Drawdown**: Expect up to 50-60% drawdown during bear markets
3. **Leverage**: Fixed at 2x (amplifies gains AND losses)
4. **Trades**: ~8 trades per year (long holding periods)
5. **Don't Panic**: The strategy has 31% win rate but big winners

---

## Troubleshooting

### "Insufficient balance"
- Transfer USDT to Futures wallet, not Spot

### "API signature failed"
- Check API key and secret are correct
- Ensure futures trading is enabled on API

### "IP not whitelisted"
- Add your server IP to API whitelist on Binance

### Bot not entering trades
- Strategy only enters on crossover (rare signal)
- Check current BTC price vs 233 SMA
- Normal to wait days/weeks for entry signal

### View detailed logs
```bash
docker compose logs --tail 100 freqtrade
cat user_data/logs/freqtrade.log
```

---

## File Structure

```
tradingtest/
├── config-production.json      # Production config (add your API keys)
├── config.json                 # Backtest config
├── docker-compose.yml          # Docker setup
├── DEPLOYMENT.md               # This file
├── STRATEGY_VERIFICATION.md    # Strategy documentation
└── user_data/
    ├── strategies/
    │   └── BTCRegimeHold4h.py  # The winning strategy
    ├── data/                   # Historical data
    └── logs/                   # Bot logs
```

---

## Important Notes

- **Past performance does not guarantee future results**
- The strategy had 57.96% max drawdown in the 2022 bear market
- Uses 2x leverage which amplifies risk
- Only 31% win rate (relies on big winners)
- Designed for BTC/USDT perpetual futures on Binance
