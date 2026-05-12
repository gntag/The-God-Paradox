"""
Rolling 40-year windows for the canonical Shiller real-total-return experiment.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

from god_paradox import (
    CFG,
    CHARTS_DIR,
    PERIOD_YEARS,
    load_bond_yields,
    load_cpi_series,
    load_real_tbill_yields,
    load_shiller_real_tr,
    maggiulli_global_bottoms,
    run_dca,
    run_god,
)


WINDOW_YEARS = int(CFG["rolling_windows"]["window_years"])
WINDOW_MONTHS = WINDOW_YEARS * 12

_DCA = "#2980B9"
_BASE = "#7F8C8D"
_MAG = "#C0392B"
_5YR = "#E67E22"
_10YR = "#8E44AD"


@dataclass
class WindowResult:
    start_date: pd.Timestamp
    end_date: pd.Timestamp
    final_dca: float
    final_god: float
    god_advantage: float
    god_wins: bool


def _filter_schedule(
    schedule: dict[pd.Timestamp, str],
    prices: pd.Series,
) -> dict[pd.Timestamp, str]:
    return {
        date: label
        for date, label in schedule.items()
        if prices.index[0] <= date <= prices.index[-1]
    }


def run_single_window(
    prices: pd.Series,
    start_idx: int,
    cash_yields: pd.Series | None = None,
    buy_schedule: dict[pd.Timestamp, str] | None = None,
    period_years: int = PERIOD_YEARS,
) -> WindowResult:
    window_prices = prices.iloc[start_idx : start_idx + WINDOW_MONTHS]
    window_yields = None
    if cash_yields is not None:
        window_yields = cash_yields.iloc[start_idx : start_idx + WINDOW_MONTHS]

    schedule = None
    if buy_schedule is not None:
        schedule = _filter_schedule(buy_schedule, window_prices)

    dca = run_dca(window_prices)
    god, _ = run_god(
        window_prices,
        cash_yields=window_yields,
        buy_schedule=schedule,
        period_years=period_years,
    )

    final_dca = float(dca.iloc[-1])
    final_god = float(god.iloc[-1])
    advantage = (final_god / final_dca - 1.0) * 100.0
    return WindowResult(
        start_date=window_prices.index[0],
        end_date=window_prices.index[-1],
        final_dca=final_dca,
        final_god=final_god,
        god_advantage=advantage,
        god_wins=final_god > final_dca,
    )


def run_all_windows(
    prices: pd.Series,
    cash_yields: pd.Series | None = None,
    buy_schedule: dict[pd.Timestamp, str] | None = None,
    period_years: int = PERIOD_YEARS,
) -> list[WindowResult]:
    n_windows = len(prices) - WINDOW_MONTHS + 1
    if n_windows <= 0:
        raise ValueError(f"Need at least {WINDOW_MONTHS} months; got {len(prices)}")
    return [
        run_single_window(
            prices,
            i,
            cash_yields=cash_yields,
            buy_schedule=buy_schedule,
            period_years=period_years,
        )
        for i in range(n_windows)
    ]


def run_all_windows_all_strategies(
    prices: pd.Series,
    bond_yields: pd.Series,
    cpi: pd.Series,
) -> tuple[list[WindowResult], list[WindowResult], list[WindowResult], list[WindowResult]]:
    real_cash_yields = load_real_tbill_yields(prices, cpi, bond_yields)
    maggiulli_schedule = maggiulli_global_bottoms(prices)
    n_windows = len(prices) - WINDOW_MONTHS + 1

    print(f"  Running baseline 0% cash windows ({n_windows} windows)...")
    baseline = run_all_windows(prices, buy_schedule=maggiulli_schedule)
    print("  Running Maggiulli real T-bill windows...")
    maggiulli = run_all_windows(prices, cash_yields=real_cash_yields, buy_schedule=maggiulli_schedule)
    print("  Running 5-year real T-bill windows...")
    five_year = run_all_windows(prices, cash_yields=real_cash_yields, period_years=5)
    print("  Running 10-year real T-bill windows...")
    ten_year = run_all_windows(prices, cash_yields=real_cash_yields, period_years=10)
    return baseline, maggiulli, five_year, ten_year


def print_summary(results: list[WindowResult], title: str = "RESULTS") -> None:
    wins = sum(r.god_wins for r in results)
    advantages = np.array([r.god_advantage for r in results])

    print(f"\n{'=' * 64}")
    print(f"  {title}  ({len(results)} windows)")
    print(f"{'=' * 64}")
    print(f"  God wins:  {wins:>3} / {len(results)}  ({wins / len(results) * 100:.0f}%)")
    print(f"  DCA wins:  {len(results) - wins:>3} / {len(results)}  ({(len(results) - wins) / len(results) * 100:.0f}%)")
    print()
    print("  God advantage  (God/DCA - 1) x 100:")
    print(f"    Mean:     {np.mean(advantages):>+.1f}%")
    print(f"    Median:   {np.median(advantages):>+.1f}%")
    print(f"    Std dev:  {np.std(advantages, ddof=1):>.1f}%")
    print(f"    Min:      {np.min(advantages):>+.1f}%")
    print(f"    Max:      {np.max(advantages):>+.1f}%")

    sorted_results = sorted(results, key=lambda r: r.god_advantage, reverse=True)
    print("\n  Top 3 windows for God:")
    for r in sorted_results[:3]:
        print(
            f"    {r.start_date.strftime('%b %Y')} - {r.end_date.strftime('%b %Y')}"
            f"  DCA ${r.final_dca:>10,.0f}  God ${r.final_god:>10,.0f}  {r.god_advantage:>+.1f}%"
        )
    print("\n  Bottom 3 windows:")
    for r in sorted_results[-3:]:
        print(
            f"    {r.start_date.strftime('%b %Y')} - {r.end_date.strftime('%b %Y')}"
            f"  DCA ${r.final_dca:>10,.0f}  God ${r.final_god:>10,.0f}  {r.god_advantage:>+.1f}%"
        )
    print(f"{'=' * 64}")


def _summary_rows(groups: list[tuple[str, list[WindowResult], str]]) -> list[tuple[str, str, str, str, str, str, str]]:
    rows: list[tuple[str, str, str, str, str, str, str]] = []
    for name, results, _ in groups:
        advantages = np.array([r.god_advantage for r in results])
        wins = sum(r.god_wins for r in results)
        rows.append((
            name,
            f"{wins / len(results) * 100:.0f}% ({wins}/{len(results)})",
            f"{np.median(advantages):+.1f}%",
            f"{np.mean(advantages):+.1f}%",
            f"{np.std(advantages, ddof=1):.1f}%",
            f"{np.max(advantages):+.1f}%",
            f"{np.min(advantages):+.1f}%",
        ))
    return rows


def plot_windows_comparison(
    w_base: list[WindowResult],
    w_mag: list[WindowResult],
    w_5yr: list[WindowResult],
    w_10yr: list[WindowResult],
) -> None:
    groups = [
        ("Baseline 0% cash", w_base, _BASE),
        ("Maggiulli real T-bill", w_mag, _MAG),
        ("5-Year real T-bill", w_5yr, _5YR),
        ("10-Year real T-bill", w_10yr, _10YR),
    ]

    fig, axes = plt.subplots(2, 2, figsize=(16, 11))
    fig.suptitle(
        f"Rolling {WINDOW_YEARS}-Year Windows vs DCA ({len(w_base)} windows)\n"
        "Shiller real total return; 5/10-year periods are window-relative",
        fontsize=12,
        fontweight="bold",
    )

    ax = axes[0, 0]
    for name, results, color in groups:
        xs = [r.start_date.year + (r.start_date.month - 1) / 12.0 for r in results]
        ys = [r.god_advantage for r in results]
        ax.scatter(xs, ys, s=22, alpha=0.45, color=color, label=name)
    ax.axhline(0, color="black", lw=1, ls=":")
    ax.set_title("God Advantage by Window Start", fontsize=10, fontweight="bold")
    ax.set_xlabel("Window start year")
    ax.set_ylabel("God advantage")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:+.0f}%"))
    ax.legend(fontsize=8)
    ax.grid(alpha=0.25)

    ax = axes[0, 1]
    all_advantages = [r.god_advantage for _, results, _ in groups for r in results]
    bins = np.linspace(min(all_advantages) - 5, max(all_advantages) + 5, 32)
    for name, results, color in groups:
        advantages = [r.god_advantage for r in results]
        ax.hist(advantages, bins=bins, alpha=0.40, color=color, label=name)
        ax.axvline(np.median(advantages), color=color, lw=1.4, ls="--")
    ax.axvline(0, color="black", lw=1, ls=":")
    ax.set_title("Advantage Distribution", fontsize=10, fontweight="bold")
    ax.set_xlabel("God advantage")
    ax.set_ylabel("Window count")
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:+.0f}%"))
    ax.legend(fontsize=8)
    ax.grid(alpha=0.25)

    ax = axes[1, 0]
    decade_totals: dict[int, int] = defaultdict(int)
    decade_wins: dict[str, dict[int, int]] = {name: defaultdict(int) for name, _, _ in groups}
    for name, results, _ in groups:
        for result in results:
            decade = (result.start_date.year // 10) * 10
            decade_totals[decade] += 1
            if result.god_wins:
                decade_wins[name][decade] += 1

    decades = sorted(decade_totals)
    x = np.arange(len(decades))
    width = 0.18
    for i, (name, _, color) in enumerate(groups):
        rates = [
            decade_wins[name][decade] / (decade_totals[decade] / len(groups)) * 100.0
            for decade in decades
        ]
        ax.bar(x + (i - 1.5) * width, rates, width, color=color, alpha=0.85, label=name)
    ax.axhline(50, color="black", lw=0.9, ls=":")
    ax.set_title("God Win Rate by Starting Decade", fontsize=10, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels([f"{decade}s" for decade in decades], rotation=30, ha="right")
    ax.set_ylabel("God win rate")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:.0f}%"))
    ax.set_ylim(0, 115)
    ax.legend(fontsize=8)
    ax.grid(alpha=0.25, axis="y")

    ax = axes[1, 1]
    ax.axis("off")
    headers = ("Strategy", "Win Rate", "Median", "Mean", "Std", "Best", "Worst")
    rows = _summary_rows(groups)
    col_x = [0.02, 0.32, 0.50, 0.62, 0.73, 0.83, 0.93]
    y = 0.92
    for x_pos, header in zip(col_x, headers):
        ax.text(x_pos, y, header, transform=ax.transAxes, fontsize=8.5, fontweight="bold", va="top")
    y -= 0.08
    ax.plot([0.02, 0.98], [y + 0.02, y + 0.02], transform=ax.transAxes, color="black", lw=0.8)
    for row, (_, _, color) in zip(rows, groups):
        for i, value in enumerate(row):
            ax.text(
                col_x[i],
                y,
                value,
                transform=ax.transAxes,
                fontsize=8,
                color=color if i == 0 else "black",
                fontweight="bold" if i == 0 else "normal",
                va="top",
            )
        y -= 0.10
    ax.set_title("Summary Scorecard", fontsize=10, fontweight="bold")

    fig.tight_layout()
    out = CHARTS_DIR / "rolling_comparison.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Chart saved: {out}")


if __name__ == "__main__":
    print("Loading data...")
    prices = load_shiller_real_tr()
    bond_yields = load_bond_yields(prices)
    cpi = load_cpi_series()

    print("\nRunning all strategies across all valid 40-year windows...")
    w_base, w_mag, w_5yr, w_10yr = run_all_windows_all_strategies(prices, bond_yields, cpi)

    print_summary(w_base, "BASELINE 0% CASH - ALL WINDOWS")
    print_summary(w_mag, "MAGGIULLI REAL T-BILL - ALL WINDOWS")
    print_summary(w_5yr, "GOD 5-YEAR REAL T-BILL - ALL WINDOWS")
    print_summary(w_10yr, "GOD 10-YEAR REAL T-BILL - ALL WINDOWS")

    plot_windows_comparison(w_base, w_mag, w_5yr, w_10yr)
    print("\nAll done.")
