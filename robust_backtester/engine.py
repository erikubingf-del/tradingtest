"""
Lightweight daily trend-following backtester.

Design goals:
- Asset agnostic (equities, ETFs, futures proxies, FX, crypto)
- Robust signals (regime SMA, Donchian breakout, EMA slope confirm)
- ATR-based position sizing and trailing stop
- Cross-sectional momentum ranking with top-N selection and leverage caps

Assumptions:
- Input OHLCV per asset in a CSV with columns: Date, Open, High, Low, Close, Volume
- All prices are already adjusted for splits/rolls (if applicable)
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


@dataclass
class AssetConfig:
    symbol: str
    path: Path
    allow_short: bool = True
    fee_bps: float = 1.0  # round-turn in basis points
    slippage_bps: float = 1.0  # one-way slippage in basis points
    multiplier: float = 1.0  # contract multiplier for futures


@dataclass
class BacktestConfig:
    start: Optional[pd.Timestamp] = None
    end: Optional[pd.Timestamp] = None
    regime_sma: int = 200
    ema_fast: int = 20
    ema_slow: int = 50
    breakout_entry: int = 55
    breakout_exit: int = 20
    atr_period: int = 20
    atr_stop_mult: float = 2.5
    risk_per_trade: float = 0.0075  # 0.75% of equity
    top_n: int = 10
    momentum_lookback: int = 90
    gross_leverage_cap: float = 3.0
    per_asset_notional_cap: float = 0.2  # 20% of equity
    allow_shorts: bool = True


def load_prices(asset: AssetConfig) -> pd.DataFrame:
    df = pd.read_csv(asset.path)
    if "Date" not in df.columns:
        raise ValueError(f"Missing Date column in {asset.path}")
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"])
    cols = ["Open", "High", "Low", "Close", "Volume"]
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns {missing} in {asset.path}")
    for c in cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=cols)
    df = df.sort_values("Date").set_index("Date")
    df["symbol"] = asset.symbol
    return df[cols]


def talib_atr(df: pd.DataFrame, period: int) -> pd.Series:
    high = df["High"]
    low = df["Low"]
    close = df["Close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            (high - low),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.rolling(period, min_periods=1).mean()


def compute_indicators(df: pd.DataFrame, cfg: BacktestConfig) -> pd.DataFrame:
    out = df.copy()
    out["sma_regime"] = out["Close"].rolling(cfg.regime_sma, min_periods=1).mean()
    out["ema_fast"] = out["Close"].ewm(span=cfg.ema_fast, min_periods=1, adjust=False).mean()
    out["ema_slow"] = out["Close"].ewm(span=cfg.ema_slow, min_periods=1, adjust=False).mean()
    out["donchian_high"] = out["High"].rolling(cfg.breakout_entry, min_periods=1).max().shift(1)
    out["donchian_low"] = out["Low"].rolling(cfg.breakout_entry, min_periods=1).min().shift(1)
    out["exit_high"] = out["High"].rolling(cfg.breakout_exit, min_periods=1).max().shift(1)
    out["exit_low"] = out["Low"].rolling(cfg.breakout_exit, min_periods=1).min().shift(1)
    out["atr"] = talib_atr(out, cfg.atr_period)
    out["momentum"] = out["Close"].pct_change(cfg.momentum_lookback)
    return out


def align_data(asset_data: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
    # Union of all dates, forward-fill within each asset to align calendars
    all_dates = sorted(set().union(*[df.index for df in asset_data.values()]))
    aligned = {}
    for sym, df in asset_data.items():
        aligned[sym] = df.reindex(all_dates).ffill()
    return aligned


def backtest(
    assets: List[AssetConfig],
    cfg: BacktestConfig,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    # Load and indicator-augment data
    raw = {a.symbol: load_prices(a) for a in assets}
    raw = align_data(raw)
    data = {sym: compute_indicators(df, cfg) for sym, df in raw.items()}

    # Apply date filter
    if cfg.start:
        data = {k: v.loc[v.index >= cfg.start] for k, v in data.items()}
    if cfg.end:
        data = {k: v.loc[v.index <= cfg.end] for k, v in data.items()}

    dates = sorted(set().union(*[df.index for df in data.values()]))
    equity_curve = []
    positions = {sym: {"qty": 0.0, "side": 0, "entry": 0.0, "stop": 0.0} for sym in data}
    cash = 100_000.0

    for dt in dates:
        # Exit logic and stop updates
        for sym, state in positions.items():
            if state["qty"] == 0:
                continue
            df = data[sym]
            if dt not in df.index:
                continue
            row = df.loc[dt]
            price = row["Close"]
            atr = row["atr"]
            side = state["side"]
            # Trail stop
            if side > 0:
                state["stop"] = max(state["stop"], price - cfg.atr_stop_mult * atr)
                hit_stop = price < state["stop"]
                exit_break = price < row["exit_low"] or price < row["sma_regime"]
            else:
                state["stop"] = min(state["stop"], price + cfg.atr_stop_mult * atr)
                hit_stop = price > state["stop"]
                exit_break = price > row["exit_high"] or price > row["sma_regime"]
            exit_now = hit_stop or exit_break
            if exit_now:
                pnl = state["qty"] * (price - state["entry"]) * side
                fee = abs(state["qty"] * price) * (state.get("fee", 0) or 0)
                cash += pnl - fee
                positions[sym] = {"qty": 0.0, "side": 0, "entry": 0.0, "stop": 0.0}

        # Compute ranking
        universe_rows = []
        for a in assets:
            df = data[a.symbol]
            if dt not in df.index:
                continue
            row = df.loc[dt]
            long_ok = (
                row["Close"] > row["donchian_high"]
                and row["Close"] > row["sma_regime"]
                and row["ema_fast"] > row["ema_slow"]
            )
            short_ok = (
                cfg.allow_shorts
                and a.allow_short
                and row["Close"] < row["donchian_low"]
                and row["Close"] < row["sma_regime"]
                and row["ema_fast"] < row["ema_slow"]
            )
            universe_rows.append(
                {
                    "symbol": a.symbol,
                    "momentum": row["momentum"],
                    "long_ok": bool(long_ok),
                    "short_ok": bool(short_ok),
                    "close": row["Close"],
                    "atr": row["atr"],
                    "fee": (a.fee_bps / 10_000.0) * row["Close"],
                    "slip": (a.slippage_bps / 10_000.0) * row["Close"],
                }
            )
        universe = pd.DataFrame(universe_rows)
        if universe.empty:
            equity_curve.append({"Date": dt, "Equity": cash})
            continue

        # Rank by momentum
        ranked = universe.sort_values("momentum", ascending=False)
        candidates = ranked.head(cfg.top_n)

        # Allocate positions
        gross_notional = sum(
            abs(state["qty"] * data[sym].loc[dt, "Close"]) for sym, state in positions.items()
        )
        for _, row in candidates.iterrows():
            sym = row["symbol"]
            state = positions[sym]
            if state["qty"] != 0:
                continue  # already in
            go_long = row["long_ok"]
            go_short = row["short_ok"] and not go_long  # prefer long if both true
            if not (go_long or go_short):
                continue
            side = 1 if go_long else -1
            atr = row["atr"]
            price = row["close"] + row["slip"] * side
            if atr <= 0 or price <= 0:
                continue
            stop_dist = cfg.atr_stop_mult * atr
            risk_dollars = cash * cfg.risk_per_trade
            size = risk_dollars / (stop_dist * a.multiplier)
            notional = size * price * a.multiplier
            # Caps
            notional_cap = cash * cfg.per_asset_notional_cap
            if notional > notional_cap:
                size = notional_cap / (price * a.multiplier)
                notional = notional_cap
            if gross_notional + notional > cash * cfg.gross_leverage_cap:
                continue
            fee = notional * (row["fee"] / price)
            cash -= fee
            gross_notional += notional
            stop = price - stop_dist if side > 0 else price + stop_dist
            positions[sym] = {
                "qty": size,
                "side": side,
                "entry": price,
                "stop": stop,
                "fee": row["fee"],
                "multiplier": a.multiplier,
            }

        # Mark-to-market
        mtm = 0.0
        for sym, state in positions.items():
            if state["qty"] == 0:
                continue
            if dt not in data[sym].index:
                continue
            px = data[sym].loc[dt, "Close"]
            mtm += state["qty"] * px * state["multiplier"] * state["side"]
        equity_curve.append({"Date": dt, "Equity": cash + mtm})

    equity = pd.DataFrame(equity_curve).set_index("Date")
    final_positions = pd.DataFrame(
        [{"symbol": sym, **state} for sym, state in positions.items() if state["qty"] != 0]
    )
    return equity, final_positions


def performance_stats(equity: pd.DataFrame) -> Dict[str, float]:
    equity = equity.dropna()
    rets = equity["Equity"].pct_change().fillna(0.0)
    total_days = len(rets)
    if total_days == 0:
        return {}
    cagr = (equity["Equity"].iloc[-1] / equity["Equity"].iloc[0]) ** (252 / total_days) - 1
    vol = rets.std() * np.sqrt(252)
    sharpe = cagr / vol if vol > 0 else np.nan
    cummax = equity["Equity"].cummax()
    dd = equity["Equity"] / cummax - 1
    max_dd = dd.min()
    calmar = cagr / abs(max_dd) if max_dd < 0 else np.nan
    return {
        "CAGR": cagr,
        "Volatility": vol,
        "Sharpe": sharpe,
        "MaxDrawdown": max_dd,
        "Calmar": calmar,
        "TotalDays": total_days,
    }
