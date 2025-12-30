"""
CLI runner for the robust trend-following backtester.

Example:
    python -m robust_backtester.run --config robust_backtester/example_config.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from .engine import AssetConfig, BacktestConfig, backtest, performance_stats


def load_config(path: Path):
    with open(path, "r") as f:
        cfg = json.load(f)
    assets = [
        AssetConfig(
            symbol=a["symbol"],
            path=Path(a["path"]),
            allow_short=a.get("allow_short", True),
            fee_bps=a.get("fee_bps", 1.0),
            slippage_bps=a.get("slippage_bps", 1.0),
        )
        for a in cfg["assets"]
    ]
    bcfg = BacktestConfig(
        start=pd.to_datetime(cfg.get("start")) if cfg.get("start") else None,
        end=pd.to_datetime(cfg.get("end")) if cfg.get("end") else None,
        regime_sma=cfg.get("regime_sma", 200),
        ema_fast=cfg.get("ema_fast", 20),
        ema_slow=cfg.get("ema_slow", 50),
        breakout_entry=cfg.get("breakout_entry", 55),
        breakout_exit=cfg.get("breakout_exit", 20),
        atr_period=cfg.get("atr_period", 20),
        atr_stop_mult=cfg.get("atr_stop_mult", 2.5),
        risk_per_trade=cfg.get("risk_per_trade", 0.0075),
        top_n=cfg.get("top_n", 10),
        momentum_lookback=cfg.get("momentum_lookback", 90),
        gross_leverage_cap=cfg.get("gross_leverage_cap", 3.0),
        per_asset_notional_cap=cfg.get("per_asset_notional_cap", 0.2),
        allow_shorts=cfg.get("allow_shorts", True),
    )
    return assets, bcfg


def main():
    parser = argparse.ArgumentParser(description="Robust trend-following backtester")
    parser.add_argument("--config", type=Path, required=True, help="Path to JSON config")
    parser.add_argument("--equity_out", type=Path, default=None, help="CSV path for equity curve")
    args = parser.parse_args()

    assets, bcfg = load_config(args.config)
    equity, final_positions = backtest(assets, bcfg)
    stats = performance_stats(equity)

    print("=== Performance ===")
    for k, v in stats.items():
        print(f"{k}: {v:.4f}" if isinstance(v, float) else f"{k}: {v}")
    print("\nFinal Positions:")
    if final_positions.empty:
        print("None")
    else:
        print(final_positions)

    if args.equity_out:
        equity.to_csv(args.equity_out)
        print(f"\nSaved equity curve to {args.equity_out}")


if __name__ == "__main__":
    main()
