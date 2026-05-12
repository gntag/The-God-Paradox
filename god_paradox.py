"""
The God Paradox
==============
Revisiting "Even God Couldn't Beat Dollar-Cost Averaging" with a stricter God.

Original experiment (of-dollars-and-data): God invests at every market bottom
(inter all-time-high dip). Result: DCA wins ~70% of rolling 40-year windows.

This experiment: God invests ONCE PER DECADE at the single lowest price of that
decade. Cash accumulates at 0% between buys — identical assumption to the
original. Both strategies invest $100/month from 1930 to 2026.

Dividends are reinvested monthly (DRIP) for shares already held. God's idle
cash earns no dividends — only invested shares compound with dividend yield.

All tunable parameters live in config.yaml next to this file.
"""

from __future__ import annotations

import yaml
import pandas as pd
import numpy as np
from pathlib import Path
from typing import NamedTuple

# ---------------------------------------------------------------------------
# Configuration — loaded once at import time
# ---------------------------------------------------------------------------
_CFG_FILE = Path(__file__).parent / "config.yaml"


def load_config(path: Path = _CFG_FILE) -> dict:
    """Load and return the YAML config dict."""
    with open(path) as f:
        return yaml.safe_load(f)


CFG = load_config()

# Resolve all paths relative to the config file's directory
_BASE         = _CFG_FILE.parent
DATA_DIR      = (_BASE / CFG["paths"]["data_dir"]).resolve()
NOMINAL_CSV   = DATA_DIR / CFG["paths"]["nominal_csv"]
DIVIDEND_XLSX = DATA_DIR / CFG["paths"]["dividend_xlsx"]
SHILLER_XLSX  = (_BASE / CFG["paths"]["shiller_xlsx"]).resolve()
DGS1_XLSX     = (_BASE / CFG["paths"]["dgs1_xlsx"]).resolve()
CHARTS_DIR    = _BASE / CFG["paths"]["charts_dir"]
EXPORTS_DIR   = _BASE / CFG["paths"]["exports_dir"]

EXPERIMENT_START     = CFG["experiment"]["start_date"]
MONTHLY_CONTRIBUTION = float(CFG["experiment"]["monthly_contribution"])
PERIOD_YEARS         = int(CFG["experiment"].get("period_years", 10))

CHARTS_DIR.mkdir(exist_ok=True)
EXPORTS_DIR.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_prices(csv_path: Path, start: str = EXPERIMENT_START) -> pd.Series:
    """Load monthly S&P 500 prices; index normalised to month-end timestamps."""
    df = pd.read_csv(csv_path, parse_dates=["Date"])
    df = df.sort_values("Date").set_index("Date")["Value"]
    df.index = df.index.to_period("M").to_timestamp("M")
    return df[df.index >= start].rename(csv_path.stem)


def load_dividends(xlsx_path: Path = DIVIDEND_XLSX) -> pd.Series:
    """
    Load monthly S&P 500 annual dividend yield (decimal, e.g. 0.0425 = 4.25%).
    Index normalised to month-end timestamps to match load_prices output.
    """
    df = pd.read_excel(xlsx_path, usecols=["Date", "Value"])
    df = df.sort_values("Date").set_index("Date")["Value"]
    df.index = df.index.to_period("M").to_timestamp("M")
    df = df[~df.index.duplicated(keep="last")]
    return df.rename("div_yield_annual")


def load_bond_yields(prices: pd.Series) -> pd.Series:
    """
    Build a monthly 1-year T-bill yield series aligned to `prices`.
      - 1930–1961: Shiller annual short rate (chapt26.xlsx), constant within each year
      - 1962–2026: FRED DGS1 daily rates (DGS1.xlsx), averaged to calendar month
    Returns annual yield in decimal (e.g. 0.035 = 3.5%).
    """
    # --- Shiller annual (1871–~2011): column R = One-Year Interest Rate ---
    sh = pd.read_excel(SHILLER_XLSX, header=None, skiprows=8, usecols=[0, 4])
    sh.columns = ["Year", "R"]
    sh["Year"] = pd.to_numeric(sh["Year"], errors="coerce")
    sh = sh.dropna(subset=["Year", "R"])
    sh["Year"] = sh["Year"].astype(int)

    # Expand annual → monthly (same rate applied to all 12 months of the year)
    rows: list[tuple[pd.Timestamp, float]] = []
    for _, row in sh.iterrows():
        for m in range(1, 13):
            ts = pd.Timestamp(year=int(row["Year"]), month=m, day=1).to_period("M").to_timestamp("M")
            rows.append((ts, row["R"] / 100.0))
    shiller_monthly = pd.Series(dict(rows), name="bond_yield")

    # --- FRED DGS1 daily → monthly average ---
    dgs1 = pd.read_excel(DGS1_XLSX, sheet_name="Daily")
    dgs1["observation_date"] = pd.to_datetime(dgs1["observation_date"])
    dgs1 = dgs1.set_index("observation_date")["DGS1"]
    dgs1 = pd.to_numeric(dgs1, errors="coerce")
    dgs1_monthly = dgs1.resample("ME").mean()
    dgs1_monthly.index = dgs1_monthly.index.to_period("M").to_timestamp("M")
    dgs1_monthly = (dgs1_monthly / 100.0).rename("bond_yield")

    # Shiller covers pre-1962; FRED covers 1962 onward
    cutoff = pd.Timestamp("1962-01-31")
    combined = pd.concat([shiller_monthly[shiller_monthly.index < cutoff], dgs1_monthly])
    combined = combined.sort_index()
    combined = combined[~combined.index.duplicated(keep="last")]

    return combined.reindex(prices.index, method="ffill").bfill().rename("bond_yield_annual")


# ---------------------------------------------------------------------------
# Decade helpers
# ---------------------------------------------------------------------------
def calendar_periods(prices: pd.Series, period_years: int = PERIOD_YEARS) -> list[pd.Series]:
    """
    Split prices into fixed-length calendar periods of `period_years` years.
    E.g. period_years=5 → 1925-1929, 1930-1934, 1935-1939, …
    The last bucket covers whatever remains (e.g., 2025-2026).
    """
    start_year    = prices.index[0].year
    end_year      = prices.index[-1].year
    period_start  = (start_year // period_years) * period_years
    periods: list[pd.Series] = []

    while period_start <= end_year:
        mask  = (prices.index.year >= period_start) & (prices.index.year <= period_start + period_years - 1)
        chunk = prices[mask]
        if not chunk.empty:
            periods.append(chunk)
        period_start += period_years

    return periods


def inter_ath_troughs(prices: pd.Series) -> dict[pd.Timestamp, str]:
    """
    Perfect-foresight buy schedule: every inter-ATH trough (Maggiulli 2019 style).
    Between each consecutive pair of ATH months, finds the month with the lowest
    price. Returns {trough_date: 'YYYY-MM' label}.
    Pairs with no months in between (back-to-back ATH months) are skipped.
    """
    running_max = -np.inf
    ath_dates: list[pd.Timestamp] = []
    for date, price in prices.items():
        if price > running_max:
            ath_dates.append(date)
            running_max = price

    buy_schedule: dict[pd.Timestamp, str] = {}
    for i in range(len(ath_dates) - 1):
        segment = prices.loc[ath_dates[i] : ath_dates[i + 1]].iloc[1:-1]
        if segment.empty:
            continue
        trough_date = segment.idxmin()
        buy_schedule[trough_date] = trough_date.strftime("%Y-%m")

    return buy_schedule


# ---------------------------------------------------------------------------
# Strategy: Dollar-Cost Averaging (with optional dividend reinvestment)
# ---------------------------------------------------------------------------
def run_dca(
    prices: pd.Series,
    div_yields: pd.Series | None = None,
    monthly: float = MONTHLY_CONTRIBUTION,
) -> pd.Series:
    """
    DCA: invest `monthly` each month; optionally reinvest dividends (DRIP).

    Each month:
      1. Existing shares receive dividends  → shares *= (1 + annual_yield/12)
      2. Buy new shares with the monthly contribution

    div_yields=None → price-only mode (no dividend reinvestment).
    """
    yields = div_yields.reindex(prices.index, method="ffill").bfill() if div_yields is not None else None
    shares = 0.0
    values: list[float] = []

    for i, (_, price) in enumerate(prices.items()):
        if yields is not None:
            shares *= 1.0 + yields.iloc[i] / 12.0
        shares += monthly / price
        values.append(shares * price)

    return pd.Series(values, index=prices.index, name="DCA")


# ---------------------------------------------------------------------------
# Strategy: God (perfect foresight — one buy per decade at the decade low)
# ---------------------------------------------------------------------------
class GodBuy(NamedTuple):
    date:         pd.Timestamp
    price:        float
    cash_deployed: float
    decade_label: str


def run_god(
    prices: pd.Series,
    div_yields: pd.Series | None = None,
    bond_yields: pd.Series | None = None,
    monthly: float = MONTHLY_CONTRIBUTION,
    track_cash: bool = False,
    _buy_schedule: dict[pd.Timestamp, str] | None = None,
    period_years: int = PERIOD_YEARS,
) -> tuple[pd.Series, list[GodBuy]] | tuple[pd.Series, list[GodBuy], pd.Series]:
    """
    God: accumulates cash (earning 1-yr T-bill rate when bond_yields provided),
    deploys ALL of it at each buy date. Invested shares earn DRIP dividends.

    Args:
        bond_yields:    annual yield series (decimal) aligned to prices index.
                        If None, idle cash earns 0%.
        track_cash:     if True, return a third element (God's idle cash series).
        _buy_schedule:  {date: label} override. If None, uses calendar_periods.
                        Pass inter_ath_troughs(prices) for Maggiulli-style timing.
        period_years:   calendar period length for the period-based strategy.
                        Ignored when _buy_schedule is provided.

    Returns (always):  (portfolio_series, buys)
    Returns (track_cash=True): (portfolio_series, buys, cash_series)
    """
    yields = div_yields.reindex(prices.index, method="ffill").bfill() if div_yields is not None else None

    if _buy_schedule is not None:
        buy_dates = _buy_schedule
    else:
        buy_dates = {}
        for chunk in calendar_periods(prices, period_years):
            min_date = chunk.idxmin()
            label    = f"{chunk.index[0].year}-{chunk.index[-1].year}"
            buy_dates[min_date] = label

    cash   = 0.0
    shares = 0.0
    values:      list[float] = []
    cash_values: list[float] = []
    buys:        list[GodBuy] = []

    for i, (date, price) in enumerate(prices.items()):
        if yields is not None:
            shares *= 1.0 + yields.iloc[i] / 12.0
        if bond_yields is not None:
            cash *= 1.0 + bond_yields.iloc[i] / 12.0

        cash += monthly

        if date in buy_dates:
            buys.append(GodBuy(date=date, price=price,
                               cash_deployed=cash, decade_label=buy_dates[date]))
            shares += cash / price
            cash    = 0.0

        values.append(shares * price + cash)
        cash_values.append(cash)

    portfolio   = pd.Series(values,      index=prices.index, name="God")
    cash_series = pd.Series(cash_values, index=prices.index, name="God_Cash")

    return (portfolio, buys, cash_series) if track_cash else (portfolio, buys)


# ---------------------------------------------------------------------------
# Decade-by-decade breakdown table
# ---------------------------------------------------------------------------
def decade_breakdown(
    prices: pd.Series,
    dca: pd.Series,
    god: pd.Series,
    buys: list[GodBuy],
) -> pd.DataFrame:
    """Show each decade's God buy details and portfolio values at decade-end."""
    buy_map = {b.decade_label: b for b in buys}
    rows    = []

    for chunk in calendar_periods(prices):
        label     = f"{chunk.index[0].year}-{chunk.index[-1].year}"
        last_date = chunk.index[-1]
        dca_val   = dca.loc[last_date]
        god_val   = god.loc[last_date]
        buy       = buy_map.get(label)

        rows.append({
            "Decade":        label,
            "God buys on":   buy.date.strftime("%b %Y")   if buy else "never",
            "Buy price":     f"${buy.price:,.2f}"          if buy else "-",
            "Cash deployed": f"${buy.cash_deployed:,.0f}"  if buy else "-",
            "DCA value":     f"${dca_val:,.0f}",
            "God value":     f"${god_val:,.0f}",
            "Leader":        "God" if god_val > dca_val else "DCA",
        })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Single-strategy experiment (backward-compatible, used by export.py)
# ---------------------------------------------------------------------------
def run_experiment(label: str, csv_path: Path, div_yields: pd.Series,
                   period_years: int = PERIOD_YEARS) -> dict:
    """
    Full pipeline for one price series with dividends and T-bill cash.
    Returns a dict consumed by export.py and the legacy single-strategy notebook path.
    """
    prices      = load_prices(csv_path)
    bond_yields = load_bond_yields(prices)
    dca         = run_dca(prices, div_yields)
    god, buys, god_cash = run_god(prices, div_yields, bond_yields,
                                   track_cash=True, period_years=period_years)

    final_dca         = dca.iloc[-1]
    final_god         = god.iloc[-1]
    total_contributed = MONTHLY_CONTRIBUTION * len(prices)
    winner            = "God" if final_god > final_dca else "DCA"
    god_advantage_pct = (final_god / final_dca - 1) * 100

    print(f"\n{'='*60}")
    print(f"  {label.upper()}  ({prices.index[0].strftime('%b %Y')} – {prices.index[-1].strftime('%b %Y')})")
    print(f"{'='*60}")
    print(f"  Total contributed (each):  ${total_contributed:>12,.0f}")
    print(f"  DCA final portfolio:       ${final_dca:>12,.0f}")
    print(f"  God final portfolio:       ${final_god:>12,.0f}")
    print(f"  God vs DCA:               {god_advantage_pct:>+.1f}%")
    print(f"  WINNER: {winner}")
    print()
    bd = decade_breakdown(prices, dca, god, buys)
    print(bd.to_string(index=False))

    return {
        "label": label, "prices": prices, "dca": dca,
        "god": god, "god_cash": god_cash, "buys": buys, "breakdown": bd,
        "final_dca": final_dca, "final_god": final_god,
        "total_contributed": total_contributed,
        "winner": winner, "god_advantage_pct": god_advantage_pct,
    }


# ---------------------------------------------------------------------------
# Three-strategy experiment (canonical entry point for charts / notebook)
# ---------------------------------------------------------------------------
def run_all_strategies(
    prices: pd.Series,
    div_yields: pd.Series,
    bond_yields: pd.Series,
    label: str = "Nominal + Dividends",
) -> dict:
    """
    Run DCA + all three God strategies simultaneously on the same price series.
    Strategies share identical dividends and T-bill cash assumptions.

    Returns a combined result dict consumed by charts.plot_all_multi and the
    multi-strategy notebook cells.
    """
    dca = run_dca(prices, div_yields)

    sched_mag        = inter_ath_troughs(prices)
    god_mag,  buys_mag  = run_god(prices, div_yields, bond_yields, _buy_schedule=sched_mag)
    god_5yr,  buys_5yr  = run_god(prices, div_yields, bond_yields, period_years=5)
    god_10yr, buys_10yr = run_god(prices, div_yields, bond_yields, period_years=10)

    total = MONTHLY_CONTRIBUTION * len(prices)

    def _adv(s: pd.Series) -> float:
        return (s.iloc[-1] / dca.iloc[-1] - 1) * 100

    print(f"\n{'='*66}")
    print(f"  {label.upper()}  ({prices.index[0].strftime('%b %Y')} – {prices.index[-1].strftime('%b %Y')})")
    print(f"{'='*66}")
    print(f"  Total contributed (each):      ${total:>14,.0f}")
    print(f"  DCA final:                     ${dca.iloc[-1]:>14,.0f}")
    print(f"  God Maggiulli final:           ${god_mag.iloc[-1]:>14,.0f}   ({_adv(god_mag):>+.1f}% vs DCA)  {len(buys_mag)} buys")
    print(f"  God 5-Year final:              ${god_5yr.iloc[-1]:>14,.0f}   ({_adv(god_5yr):>+.1f}% vs DCA)  {len(buys_5yr)} buys")
    print(f"  God 10-Year final:             ${god_10yr.iloc[-1]:>14,.0f}   ({_adv(god_10yr):>+.1f}% vs DCA)  {len(buys_10yr)} buys")

    return {
        "label":             label,
        "prices":            prices,
        "dca":               dca,
        "god_mag":           god_mag,   "buys_mag":   buys_mag,
        "god_5yr":           god_5yr,   "buys_5yr":   buys_5yr,
        "god_10yr":          god_10yr,  "buys_10yr":  buys_10yr,
        "final_dca":         dca.iloc[-1],
        "final_mag":         god_mag.iloc[-1],
        "final_5yr":         god_5yr.iloc[-1],
        "final_10yr":        god_10yr.iloc[-1],
        "adv_mag":           _adv(god_mag),
        "adv_5yr":           _adv(god_5yr),
        "adv_10yr":          _adv(god_10yr),
        "total_contributed": total,
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    prices      = load_prices(NOMINAL_CSV)
    div_yields  = load_dividends()
    bond_yields = load_bond_yields(prices)

    result = run_all_strategies(prices, div_yields, bond_yields)

    from charts import plot_all_multi
    plot_all_multi(result)

    print(f"\nCharts  -> {CHARTS_DIR}")
