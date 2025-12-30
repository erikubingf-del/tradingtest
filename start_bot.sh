#!/bin/bash
# BTCRegimeHold4h Trading Bot Startup Script

echo "=========================================="
echo "  BTCRegimeHold4h Bot - Binance Futures"
echo "=========================================="

# Check if API keys are configured
if grep -q '"key": ""' config-production.json; then
    echo ""
    echo "ERROR: Binance API keys not configured!"
    echo ""
    echo "Please edit config-production.json and add:"
    echo '  "key": "YOUR_BINANCE_API_KEY",'
    echo '  "secret": "YOUR_BINANCE_SECRET_KEY"'
    echo ""
    exit 1
fi

# Check dry_run status
if grep -q '"dry_run": true' config-production.json; then
    echo ""
    echo "MODE: DRY-RUN (Paper Trading)"
    echo "No real money will be used."
    echo ""
else
    echo ""
    echo "WARNING: LIVE TRADING MODE"
    echo "Real money will be used!"
    echo ""
    read -p "Are you sure you want to continue? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        echo "Aborted."
        exit 1
    fi
fi

echo "Starting bot..."
echo "Press Ctrl+C to stop"
echo ""

freqtrade trade \
    --config config-production.json \
    --strategy BTCRegimeHold4h \
    --logfile user_data/logs/freqtrade.log
