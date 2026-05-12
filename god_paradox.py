"""
The God Paradox
===============
Canonical Shiller real-total-return implementation.

Equity prices are Shiller's real total return S&P 500 index from
ie_data.xls column J. Dividends and inflation adjustment are already embedded,
so no separate dividend-yield series is applied.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import NamedTuple

import numpy as np
import pandas as pd
import xlrd
import yaml


_CFG_FILE = Path(__file__).parent / "config.yaml"


def load_config(path: Path = _CFG_FILE) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


CFG = load_config()
_BASE = _CFG_FILE.parent

SHILLER_IES_XLS = (_BASE / CFG["paths"]["shiller_ies_xls"]).resolve()
SHILLER_IE_XLS = SHILLER_IES_XLS
SHILLER_XLSX = (_BASE / CFG["paths"]["shiller_xlsx"]).resolve()
DGS1_XLSX = (_BASE / CFG["paths"]["dgs1_xlsx"]).resolve()
CHARTS_DIR = _BASE / CFG["paths"]["charts_dir"]
EXPORTS_DIR = _BASE / CFG["paths"]["exports_dir"]

EXPERIMENT_START = CFG["experiment"]["start_date"]
MONTHLY_CONTRIBUTION = float(CFG["experiment"]["monthly_contribution"])
PERIOD_YEARS = int(CFG["experiment"].get("period_years", 10))

CHARTS_DIR.mkdir(exist_ok=True)
EXPORTS_DIR.mkdir(exist_ok=True)


class GodBuy(NamedTuple):
    date: pd.Timestamp
    price: float
    cash_deployed: float
    period_label: str


def _parse_shiller_month(value: object) -> pd.Timestamp | None:
    try:
        raw = float(value)
    except (TypeError, ValueError):
        return None

    year = int(raw)
    month = int(round((raw - year) * 100))
    if not 1 <= month <= 12:
        return None
    return pd.Timestamp(year=year, month=month, day=1).to_period("M").to_timestamp("M")


@lru_cache(maxsize=1)
def _load_shiller_history() -> pd.DataFrame:
    """Read Shiller ie_data.xls directly so old binary .xls support is explicit."""
    book = xlrd.open_workbook(str(SHILLER_IES_XLS))
    sheet = book.sheet_by_name("Data")
    rows: list[tuple[pd.Timestamp, float, float, float, float]] = []

    for row_idx in range(8, sheet.nrows):
        date = _parse_shiller_month(sheet.cell_value(row_idx, 0))
        if date is None:
            continue
        try:
            nominal_price = float(sheet.cell_value(row_idx, 1))
            cpi = float(sheet.cell_value(row_idx, 4))
            real_price = float(sheet.cell_value(row_idx, 7))
            real_tr = float(sheet.cell_value(row_idx, 9))
        except (TypeError, ValueError):
            continue
        rows.append((date, nominal_price, cpi, real_price, real_tr))

    if not rows:
        raise ValueError(f"No Shiller monthly rows found in {SHILLER_IES_XLS}")

    df = pd.DataFrame(
        rows,
        columns=["date", "nominal_price", "cpi", "real_price", "real_tr"],
    ).set_index("date")
    df = df.sort_index()
    df = df[~df.index.duplicated(keep="last")]
    return df


def load_shiller_real_tr(start: str = EXPERIMENT_START) -> pd.Series:
    """Load Shiller real total-return S&P 500, ie_data.xls column J."""
    prices = _load_shiller_history()["real_tr"]
    return prices[prices.index >= pd.Timestamp(start)].rename("shiller_real_tr")


def load_cpi_series() -> pd.Series:
    """Load Shiller CPI from ie_data.xls column E for the full available history."""
    return _load_shiller_history()["cpi"].rename("cpi")


def load_bond_yields(prices: pd.Series) -> pd.Series:
    """
    Load nominal one-year cash yields aligned to Shiller monthly dates.

    Shiller's pre-1962 one-year rate is used as an annual rate. FRED DGS1 is a
    bond-equivalent yield, so it is converted to annual effective after monthly
    averaging.
    """
    shiller = pd.read_excel(SHILLER_XLSX, header=None, skiprows=8, usecols=[0, 4])
    shiller.columns = ["year", "rate"]
    shiller["year"] = pd.to_numeric(shiller["year"], errors="coerce")
    shiller["rate"] = pd.to_numeric(shiller["rate"], errors="coerce")
    shiller = shiller.dropna(subset=["year", "rate"])

    annual_rows: list[tuple[pd.Timestamp, float]] = []
    for row in shiller.itertuples(index=False):
        for month in range(1, 13):
            date = pd.Timestamp(int(row.year), month, 1).to_period("M").to_timestamp("M")
            annual_rows.append((date, float(row.rate) / 100.0))
    shiller_monthly = pd.Series(dict(annual_rows), name="nominal_tbill")

    dgs1 = pd.read_excel(DGS1_XLSX, sheet_name="Daily")
    dgs1["observation_date"] = pd.to_datetime(dgs1["observation_date"])
    fred = pd.to_numeric(dgs1.set_index("observation_date")["DGS1"], errors="coerce")
    fred_monthly = fred.resample("ME").mean() / 100.0
    fred_monthly.index = fred_monthly.index.to_period("M").to_timestamp("M")
    fred_effective = ((1.0 + fred_monthly / 2.0) ** 2 - 1.0).rename("nominal_tbill")

    cutoff = pd.Timestamp("1962-01-31")
    combined = pd.concat([shiller_monthly[shiller_monthly.index < cutoff], fred_effective])
    combined = combined.sort_index()
    combined = combined[~combined.index.duplicated(keep="last")]
    return combined.reindex(prices.index, method="ffill").bfill().rename("nominal_tbill")


def load_real_tbill_yields(
    prices: pd.Series,
    cpi: pd.Series,
    nominal_yields: pd.Series | None = None,
) -> pd.Series:
    """Convert nominal one-year yields to real annual yields with trailing 12m CPI."""
    nominal = nominal_yields if nominal_yields is not None else load_bond_yields(prices)
    nominal = nominal.reindex(prices.index, method="ffill").bfill()
    trailing_inflation = cpi.sort_index() / cpi.sort_index().shift(12) - 1.0
    trailing_inflation = trailing_inflation.reindex(prices.index, method="ffill").bfill()
    real = (1.0 + nominal) / (1.0 + trailing_inflation) - 1.0
    return real.rename("real_tbill")


def maggiulli_global_bottoms(prices: pd.Series) -> dict[pd.Timestamp, str]:
    """
    Port of Maggiulli's two-pass drawdown bottom detection.

    The schedule is meant to be computed once on the full series. Rolling
    windows then filter this global schedule to dates inside each window.
    """
    drawdowns: list[float] = []
    running_max = 0.0
    for i, price in enumerate(prices.values):
        if price < running_max and i != 0:
            drawdowns.append(price / running_max - 1.0)
        else:
            drawdowns.append(0.0)
            running_max = price

    pct = np.array(drawdowns)
    min_dd = np.zeros(len(pct))
    local_min = 0.0
    for i, value in enumerate(pct):
        local_min = 0.0 if value == 0.0 else min(local_min, value)
        min_dd[i] = local_min

    local_min = 0.0
    for i in range(len(pct) - 1, -1, -1):
        if pct[i] == 0.0:
            local_min = 0.0
        else:
            local_min = min(local_min, min_dd[i])
            min_dd[i] = local_min

    segments = pd.Series(pct == 0.0, index=prices.index).cumsum()
    frame = pd.DataFrame({"pct": pct, "min_dd": min_dd, "segment": segments}, index=prices.index)

    schedule: dict[pd.Timestamp, str] = {}
    for _, chunk in frame.groupby("segment"):
        hits = chunk[(chunk["min_dd"] < 0.0) & (chunk["pct"] == chunk["min_dd"])]
        if hits.empty:
            continue
        date = hits.index[0]
        schedule[date] = date.strftime("%Y-%m")
    return schedule


def period_low_schedule(prices: pd.Series, period_years: int = PERIOD_YEARS) -> dict[pd.Timestamp, str]:
    """
    Buy once at the low of each period anchored to this series' start year.

    This is window-relative for rolling windows: a window starting in 1947 uses
    1947-1951, 1952-1956, and so on. It is not snapped to global Gregorian
    decades unless the series itself starts on that boundary.
    """
    schedule: dict[pd.Timestamp, str] = {}
    period_start = prices.index[0].year
    end_year = prices.index[-1].year

    while period_start <= end_year:
        period_end = period_start + period_years - 1
        chunk = prices[(prices.index.year >= period_start) & (prices.index.year <= period_end)]
        if not chunk.empty:
            date = chunk.idxmin()
            schedule[date] = f"{period_start}-{period_end}"
        period_start += period_years

    return schedule


def run_dca(
    prices: pd.Series,
    monthly: float = MONTHLY_CONTRIBUTION,
) -> pd.Series:
    shares = 0.0
    values: list[float] = []
    for price in prices.values:
        shares += monthly / price
        values.append(shares * price)
    return pd.Series(values, index=prices.index, name="DCA")


def run_god(
    prices: pd.Series,
    cash_yields: pd.Series | None = None,
    monthly: float = MONTHLY_CONTRIBUTION,
    track_cash: bool = False,
    buy_schedule: dict[pd.Timestamp, str] | None = None,
    period_years: int = PERIOD_YEARS,
) -> tuple[pd.Series, list[GodBuy]] | tuple[pd.Series, list[GodBuy], pd.Series]:
    """Run God with an explicit buy schedule and explicit cash-yield series."""
    schedule = buy_schedule if buy_schedule is not None else period_low_schedule(prices, period_years)
    yields = None if cash_yields is None else cash_yields.reindex(prices.index, method="ffill").bfill()

    cash = 0.0
    shares = 0.0
    values: list[float] = []
    cash_values: list[float] = []
    buys: list[GodBuy] = []

    for i, (date, price) in enumerate(prices.items()):
        if yields is not None:
            cash *= (1.0 + yields.iloc[i]) ** (1.0 / 12.0)
        cash += monthly

        if date in schedule:
            buys.append(GodBuy(date, float(price), float(cash), schedule[date]))
            shares += cash / price
            cash = 0.0

        values.append(shares * price + cash)
        cash_values.append(cash)

    portfolio = pd.Series(values, index=prices.index, name="God")
    cash_series = pd.Series(cash_values, index=prices.index, name="God_Cash")
    return (portfolio, buys, cash_series) if track_cash else (portfolio, buys)


def decade_breakdown(
    prices: pd.Series,
    dca: pd.Series,
    god: pd.Series,
    buys: list[GodBuy],
    period_years: int = PERIOD_YEARS,
) -> pd.DataFrame:
    buy_map = {b.period_label: b for b in buys}
    rows: list[dict[str, object]] = []

    period_start = prices.index[0].year
    end_year = prices.index[-1].year
    while period_start <= end_year:
        period_end = period_start + period_years - 1
        label = f"{period_start}-{period_end}"
        period_prices = prices[
            (prices.index.year >= period_start) & (prices.index.year <= period_end)
        ]
        if period_prices.empty:
            period_start += period_years
            continue

        last_date = period_prices.index[-1]
        buy = buy_map.get(label)
        rows.append({
            "Period": label,
            "God buys on": buy.date.strftime("%b %Y") if buy else "never",
            "Buy price": f"${buy.price:,.2f}" if buy else "-",
            "Cash deployed": f"${buy.cash_deployed:,.0f}" if buy else "-",
            "DCA value": f"${dca.loc[last_date]:,.0f}",
            "God value": f"${god.loc[last_date]:,.0f}",
            "Leader": "God" if god.loc[last_date] > dca.loc[last_date] else "DCA",
        })
        period_start += period_years

    return pd.DataFrame(rows)


def run_all_strategies(
    prices: pd.Series,
    bond_yields: pd.Series,
    cpi: pd.Series,
    label: str = "Shiller Real Total Return",
) -> dict:
    real_cash_yields = load_real_tbill_yields(prices, cpi, bond_yields)
    dca = run_dca(prices)
    schedule_mag = maggiulli_global_bottoms(prices)

    god_mag_base, buys_mag_base, cash_mag_base = run_god(
        prices, buy_schedule=schedule_mag, track_cash=True
    )
    god_mag, buys_mag, cash_mag = run_god(
        prices, cash_yields=real_cash_yields, buy_schedule=schedule_mag, track_cash=True
    )
    god_5yr, buys_5yr, cash_5yr = run_god(
        prices, cash_yields=real_cash_yields, period_years=5, track_cash=True
    )
    god_10yr, buys_10yr, cash_10yr = run_god(
        prices, cash_yields=real_cash_yields, period_years=10, track_cash=True
    )

    total = MONTHLY_CONTRIBUTION * len(prices)

    def adv(series: pd.Series) -> float:
        return (series.iloc[-1] / dca.iloc[-1] - 1.0) * 100.0

    print(f"\n{'=' * 72}")
    print(f"  {label.upper()}  ({prices.index[0].strftime('%b %Y')} - {prices.index[-1].strftime('%b %Y')})")
    print(f"{'=' * 72}")
    print(f"  Total contributed (each):      ${total:>14,.0f}")
    print(f"  DCA final:                     ${dca.iloc[-1]:>14,.0f}")
    print(
        f"  God Mag (0% cash) final:       ${god_mag_base.iloc[-1]:>14,.0f}"
        f"   ({adv(god_mag_base):>+.1f}% vs DCA)  {len(buys_mag_base)} buys"
    )
    print(
        f"  God Mag (real T-bill) final:   ${god_mag.iloc[-1]:>14,.0f}"
        f"   ({adv(god_mag):>+.1f}% vs DCA)  {len(buys_mag)} buys"
    )
    print(
        f"  God 5-Year final:              ${god_5yr.iloc[-1]:>14,.0f}"
        f"   ({adv(god_5yr):>+.1f}% vs DCA)  {len(buys_5yr)} buys"
    )
    print(
        f"  God 10-Year final:             ${god_10yr.iloc[-1]:>14,.0f}"
        f"   ({adv(god_10yr):>+.1f}% vs DCA)  {len(buys_10yr)} buys"
    )

    return {
        "label": label,
        "prices": prices,
        "bond_yields": bond_yields,
        "real_cash_yields": real_cash_yields,
        "dca": dca,
        "god_mag_base": god_mag_base,
        "god_mag": god_mag,
        "god_5yr": god_5yr,
        "god_10yr": god_10yr,
        "cash_mag_base": cash_mag_base,
        "cash_mag": cash_mag,
        "cash_5yr": cash_5yr,
        "cash_10yr": cash_10yr,
        "buys_mag_base": buys_mag_base,
        "buys_mag": buys_mag,
        "buys_5yr": buys_5yr,
        "buys_10yr": buys_10yr,
        "final_dca": dca.iloc[-1],
        "final_mag_base": god_mag_base.iloc[-1],
        "final_mag": god_mag.iloc[-1],
        "final_5yr": god_5yr.iloc[-1],
        "final_10yr": god_10yr.iloc[-1],
        "adv_mag_base": adv(god_mag_base),
        "adv_mag": adv(god_mag),
        "adv_5yr": adv(god_5yr),
        "adv_10yr": adv(god_10yr),
        "total_contributed": total,
        "breakdown": decade_breakdown(prices, dca, god_10yr, buys_10yr),
    }


if __name__ == "__main__":
    prices = load_shiller_real_tr()
    bond_yields = load_bond_yields(prices)
    cpi = load_cpi_series()
    result = run_all_strategies(prices, bond_yields, cpi)

    from charts import plot_all_multi

    plot_all_multi(result)
    print(f"\nCharts -> {CHARTS_DIR}")
