"""
Rolling Windows Analysis
========================
Exhaustive rolling-window test: every valid 40-year monthly-start window
in the dataset is simulated (Maggiulli-style coverage, ~700 windows).

Both nominal and real (inflation-adjusted) prices are tested.

Usage:
    python rolling_windows.py
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from collections import defaultdict
from dataclasses import dataclass

# ── Colour palette (mirrors charts.py) ─────────────────────────────────────────
_GOD  = "#C0392B"   # vermilion  — God / Maggiulli strategy
_DCA  = "#2980B9"   # steel-blue — DCA strategy
_5YR  = "#E67E22"   # orange     — God 5-year strategy
_10YR = "#8E44AD"   # purple     — God 10-year strategy

from god_paradox import (
    load_prices, load_dividends, load_bond_yields,
    run_dca, run_god, inter_ath_troughs,
    NOMINAL_CSV, CHARTS_DIR, CFG, PERIOD_YEARS,
)

_RW = CFG["rolling_windows"]
WINDOW_YEARS  = int(_RW["window_years"])
WINDOW_MONTHS = WINDOW_YEARS * 12


# ---------------------------------------------------------------------------
# Window simulation
# ---------------------------------------------------------------------------
@dataclass
class WindowResult:
    start_date:    pd.Timestamp
    end_date:      pd.Timestamp
    final_dca:     float
    final_god:     float
    god_advantage: float        # (god/dca - 1) * 100  percent
    god_wins:      bool


def run_single_window(
    prices: pd.Series,
    div_yields: pd.Series,
    bond_yields: pd.Series,
    start_idx: int,
    maggiulli: bool = False,
    period_years: int = PERIOD_YEARS,
) -> WindowResult:
    win_p = prices.iloc[start_idx : start_idx + WINDOW_MONTHS]
    win_b = bond_yields.iloc[start_idx : start_idx + WINDOW_MONTHS]

    sched      = inter_ath_troughs(win_p) if maggiulli else None
    dca        = run_dca(win_p, div_yields)
    god, _buys = run_god(win_p, div_yields, win_b,
                         _buy_schedule=sched, period_years=period_years)

    fd = dca.iloc[-1]
    fg = god.iloc[-1]

    return WindowResult(
        start_date    = win_p.index[0],
        end_date      = win_p.index[-1],
        final_dca     = fd,
        final_god     = fg,
        god_advantage = (fg / fd - 1) * 100,
        god_wins      = fg > fd,
    )


# ---------------------------------------------------------------------------
# Exhaustive window runners
# ---------------------------------------------------------------------------
def run_all_windows(
    prices: pd.Series,
    div_yields: pd.Series,
    bond_yields: pd.Series,
    maggiulli: bool = False,
    period_years: int = PERIOD_YEARS,
) -> list[WindowResult]:
    """
    Every valid monthly-start 40-year window — exhaustive, no sampling bias.
    ~702 windows for 1928-2026 data.
    """
    max_start = len(prices) - WINDOW_MONTHS
    return [
        run_single_window(prices, div_yields, bond_yields, i,
                          maggiulli=maggiulli, period_years=period_years)
        for i in range(max_start + 1)
    ]


def run_all_windows_three_strategies(
    prices: pd.Series,
    div_yields: pd.Series,
    bond_yields: pd.Series,
) -> tuple[list[WindowResult], list[WindowResult], list[WindowResult]]:
    """
    Run all 702 windows for all three God strategies simultaneously.
    Returns (maggiulli_results, 5yr_results, 10yr_results).
    """
    print(f"  Running Maggiulli rolling windows ({len(prices) - WINDOW_MONTHS + 1} windows)…")
    w_mag  = run_all_windows(prices, div_yields, bond_yields, maggiulli=True)
    print(f"  Running 5-year rolling windows…")
    w_5yr  = run_all_windows(prices, div_yields, bond_yields, period_years=5)
    print(f"  Running 10-year rolling windows…")
    w_10yr = run_all_windows(prices, div_yields, bond_yields, period_years=10)
    return w_mag, w_5yr, w_10yr


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------
def print_summary(results: list[WindowResult], title: str = "RESULTS") -> None:
    god_wins   = sum(r.god_wins for r in results)
    advantages = [r.god_advantage for r in results]

    print(f"\n{'='*64}")
    print(f"  {title}  ({len(results)} windows)")
    print(f"{'='*64}")
    print(f"  God wins:  {god_wins:>3} / {len(results)}  ({god_wins/len(results)*100:.0f}%)")
    print(f"  DCA wins:  {len(results)-god_wins:>3} / {len(results)}  ({(len(results)-god_wins)/len(results)*100:.0f}%)")
    print()
    print(f"  God advantage  (God/DCA - 1) x 100:")
    print(f"    Mean:     {np.mean(advantages):>+.1f}%")
    print(f"    Median:   {np.median(advantages):>+.1f}%")
    print(f"    Std dev:  {np.std(advantages):>.1f}%")
    print(f"    Min:      {np.min(advantages):>+.1f}%")
    print(f"    Max:      {np.max(advantages):>+.1f}%")

    sorted_r = sorted(results, key=lambda r: r.god_advantage, reverse=True)
    print(f"\n  Top 3 windows for God:")
    for r in sorted_r[:3]:
        print(f"    {r.start_date.strftime('%b %Y')} - {r.end_date.strftime('%b %Y')}"
              f"  DCA ${r.final_dca:>10,.0f}  God ${r.final_god:>10,.0f}  {r.god_advantage:>+.1f}%")
    print(f"\n  Bottom 3 windows (DCA wins most):")
    for r in sorted_r[-3:]:
        print(f"    {r.start_date.strftime('%b %Y')} - {r.end_date.strftime('%b %Y')}"
              f"  DCA ${r.final_dca:>10,.0f}  God ${r.final_god:>10,.0f}  {r.god_advantage:>+.1f}%")
    print(f"{'='*64}")


# ---------------------------------------------------------------------------
# Visualisation
# ---------------------------------------------------------------------------
def plot_windows(results: list[WindowResult], title: str, filename: str) -> None:
    from matplotlib.lines import Line2D

    advantages  = [r.god_advantage for r in results]
    start_years = [r.start_date.year + r.start_date.month / 12 for r in results]
    n           = len(results)
    god_wins_n  = sum(r.god_wins for r in results)
    god_pct     = god_wins_n / n * 100

    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    fig.suptitle(title, fontsize=12, fontweight="bold")

    # ── Panel 1: Who wins each window? (scatter by start year) ───────────────
    ax = axes[0, 0]
    colors = [_GOD if r.god_wins else _DCA for r in results]
    ax.scatter(start_years, advantages, c=colors, s=45, alpha=0.75, zorder=3)
    ax.axhline(0, color="black", lw=1, ls=":")
    ax.text(min(start_years) + 0.5,  1.5, "↑ God finishes ahead",
            fontsize=8, color=_GOD, va="bottom")
    ax.text(min(start_years) + 0.5, -1.5, "↓ DCA finishes ahead",
            fontsize=8, color=_DCA, va="top")
    ax.legend(handles=[
        Line2D([0], [0], marker="o", color="w", markerfacecolor=_GOD, ms=9, label="God wins"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor=_DCA, ms=9, label="DCA wins"),
    ], fontsize=8)
    ax.set_title("Who Wins Each 40-Year Window?", fontsize=10, fontweight="bold")
    ax.set_xlabel("Window starts in...")
    ax.set_ylabel("God's edge at end of 40 years")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:+.0f}%"))
    ax.grid(alpha=0.25)

    # ── Panel 2: Distribution of outcomes (histogram) ─────────────────────────
    ax = axes[0, 1]
    god_adv = [a for a in advantages if a >= 0]
    dca_adv = [a for a in advantages if a <  0]
    bins = np.linspace(min(advantages) - 5, max(advantages) + 5, 26)
    ax.hist(god_adv, bins=bins, color=_GOD, alpha=0.75,
            label=f"God wins ({len(god_adv)} windows)")
    ax.hist(dca_adv, bins=bins, color=_DCA, alpha=0.75,
            label=f"DCA wins ({len(dca_adv)} windows)")
    ax.axvline(0, color="black", lw=1.2, ls=":")
    ax.axvline(np.median(advantages), color="orange", lw=1.5, ls="--",
               label=f"Median {np.median(advantages):+.1f}%")
    ax.axvline(np.mean(advantages), color="purple", lw=1.5, ls="--",
               label=f"Mean {np.mean(advantages):+.1f}%")
    # Bold win-% headline
    ax.text(0.97, 0.97,
            f"God wins\n{god_pct:.0f}%\nof windows",
            transform=ax.transAxes, ha="right", va="top",
            fontsize=11, fontweight="bold", color=_GOD,
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                      edgecolor=_GOD, alpha=0.9))
    ax.set_title("Who Wins — and by How Much?", fontsize=10, fontweight="bold")
    ax.set_xlabel("God's advantage at end of the 40-year window (%)")
    ax.set_ylabel("Number of windows")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.25)

    # ── Panel 3: Win rate by starting decade (stacked bar) ────────────────────
    ax = axes[1, 0]
    decade_god: dict[int, int] = defaultdict(int)
    decade_dca: dict[int, int] = defaultdict(int)
    for r in results:
        d = (r.start_date.year // 10) * 10
        if r.god_wins:
            decade_god[d] += 1
        else:
            decade_dca[d] += 1

    decades_sorted = sorted(set(decade_god) | set(decade_dca))
    g_counts = [decade_god[d] for d in decades_sorted]
    d_counts = [decade_dca[d] for d in decades_sorted]
    x_dec    = np.arange(len(decades_sorted))

    ax.bar(x_dec, g_counts, color=_GOD, alpha=0.85, label="God wins")
    ax.bar(x_dec, d_counts, bottom=g_counts, color=_DCA, alpha=0.85, label="DCA wins")

    # Label sits inside the God (red) segment — skipped when God wins 0 in that decade
    for i, (gc, dc) in enumerate(zip(g_counts, d_counts)):
        total = gc + dc
        if total > 0 and gc > 0:
            ax.text(i, gc / 2, f"{gc / total * 100:.0f}%",
                    ha="center", va="center", fontsize=7.5,
                    fontweight="bold", color="white")

    ax.set_title(
        "God vs DCA by Starting Decade\n(% label = God's win rate in that era)",
        fontsize=10, fontweight="bold",
    )
    ax.set_xticks(x_dec)
    ax.set_xticklabels([f"{d}s" for d in decades_sorted], rotation=30, ha="right")
    ax.set_ylabel("Number of 40-year windows")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.25, axis="y")

    # ── Panel 4: The verdict (text scorecard) ─────────────────────────────────
    ax = axes[1, 1]
    ax.axis("off")

    lines = [
        ("The Verdict", None, 14, "bold", "sans-serif"),
        ("", None, 10, "normal", "sans-serif"),
        (
            f"God wins  {god_pct:.0f}%  ({god_wins_n} / {n} windows)",
            _GOD, 12, "bold", "monospace",
        ),
        (
            f"DCA wins  {100 - god_pct:.0f}%  ({n - god_wins_n} / {n} windows)",
            _DCA, 12, "bold", "monospace",
        ),
        ("", None, 8, "normal", "sans-serif"),
        (f"Median God edge :  {np.median(advantages):+.1f}%", "black", 10, "normal", "monospace"),
        (f"Mean God edge   :  {np.mean(advantages):+.1f}%   ← skewed by big wins",
         "black", 10, "normal", "monospace"),
        (f"Std deviation   :  {np.std(advantages):.1f}%", "black", 10, "normal", "monospace"),
        ("", None, 8, "normal", "sans-serif"),
        (f"Biggest God win  :  {max(advantages):+.1f}%", _GOD, 10, "normal", "monospace"),
        (f"Biggest DCA win  :  {abs(min(advantages)):.1f}%", _DCA, 10, "normal", "monospace"),
    ]

    y_pos = 0.95
    for text, color, size, weight, family in lines:
        ax.text(
            0.08, y_pos, text,
            transform=ax.transAxes,
            ha="left", va="top",
            fontsize=size, fontweight=weight,
            color=color or "black",
            fontfamily=family,
        )
        y_pos -= 0.10 if size >= 12 else 0.09

    plt.tight_layout()
    out = CHARTS_DIR / filename
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Chart saved: {out}")


def plot_windows_comparison(
    w_mag:  list[WindowResult],
    w_5yr:  list[WindowResult],
    w_10yr: list[WindowResult],
) -> None:
    """
    2×2 comparison chart across all three God strategies.
      (0,0) Overlaid scatter  — God advantage vs window start year
      (0,1) Overlaid histogram — advantage distribution
      (1,0) Win rate by starting decade — grouped bars
      (1,1) Summary scorecard text
    """
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch

    groups = [
        ("Maggiulli",  w_mag,  _GOD,  "o"),
        ("God 5-Year", w_5yr,  _5YR,  "s"),
        ("God 10-Year",w_10yr, _10YR, "^"),
    ]

    fig, axes = plt.subplots(2, 2, figsize=(16, 11))
    fig.suptitle(
        f"Rolling 40-Year Windows: All Three God Strategies vs DCA  "
        f"({len(w_mag)} windows)\n"
        "All strategies: $100/month  ·  Dividends reinvested  ·  T-bill yield on idle cash",
        fontsize=12, fontweight="bold",
    )

    # ── (0,0) Scatter: advantage vs start year ────────────────────────────────
    ax = axes[0, 0]
    for name, results, color, marker in groups:
        xs  = [r.start_date.year + r.start_date.month / 12 for r in results]
        ys  = [r.god_advantage for r in results]
        ax.scatter(xs, ys, c=color, s=28, alpha=0.50, marker=marker,
                   label=name, zorder=3)
    ax.axhline(0, color="black", lw=1, ls=":")
    ax.set_title("God's Edge at End of Each 40-Year Window", fontsize=10, fontweight="bold")
    ax.set_xlabel("Window starts in…")
    ax.set_ylabel("God advantage (%)")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:+.0f}%"))
    ax.legend(fontsize=8)
    ax.grid(alpha=0.25)

    # ── (0,1) Overlaid histograms ─────────────────────────────────────────────
    ax = axes[0, 1]
    all_adv = [r.god_advantage for results in [w_mag, w_5yr, w_10yr]
               for r in results]
    bins = np.linspace(min(all_adv) - 5, max(all_adv) + 5, 30)
    for name, results, color, _ in groups:
        adv = [r.god_advantage for r in results]
        ax.hist(adv, bins=bins, color=color, alpha=0.48, label=name)
        ax.axvline(np.median(adv), color=color, lw=1.6, ls="--", alpha=0.85)
    ax.axvline(0, color="black", lw=1.2, ls=":")
    ax.set_title("Advantage Distribution  (dashed = median)", fontsize=10, fontweight="bold")
    ax.set_xlabel("God advantage at end of 40-year window (%)")
    ax.set_ylabel("Number of windows")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.25)

    # ── (1,0) Win rate by starting decade — grouped bars ─────────────────────
    ax = axes[1, 0]
    decade_wins   = {name: defaultdict(int) for name, *_ in groups}
    decade_totals: dict[int, int] = defaultdict(int)
    for name, results, *_ in groups:
        for r in results:
            d = (r.start_date.year // 10) * 10
            if r.god_wins:
                decade_wins[name][d] += 1
            decade_totals[d] += 1

    decades_sorted = sorted(decade_totals)
    n_groups = len(groups)
    x_dec    = np.arange(len(decades_sorted))
    width    = 0.25

    for i, (name, results, color, _) in enumerate(groups):
        win_rates = [
            decade_wins[name][d] / (decade_totals[d] / n_groups) * 100
            if decade_totals[d] else 0
            for d in decades_sorted
        ]
        bars = ax.bar(x_dec + (i - 1) * width, win_rates, width,
                      color=color, alpha=0.82, label=name)
        for bar, rate in zip(bars, win_rates):
            if rate > 5:
                ax.text(bar.get_x() + bar.get_width() / 2,
                        bar.get_height() + 1.5,
                        f"{rate:.0f}%",
                        ha="center", va="bottom", fontsize=6.5,
                        fontweight="bold", color=color)

    ax.axhline(50, color="black", lw=0.9, ls=":", alpha=0.6)
    ax.set_title("God Win Rate by Starting Decade", fontsize=10, fontweight="bold")
    ax.set_xticks(x_dec)
    ax.set_xticklabels([f"{d}s" for d in decades_sorted], rotation=30, ha="right")
    ax.set_ylabel("God win rate (%)")
    ax.set_ylim(0, 115)
    ax.legend(fontsize=8)
    ax.grid(alpha=0.25, axis="y")

    # ── (1,1) Scorecard text ──────────────────────────────────────────────────
    ax = axes[1, 1]
    ax.axis("off")

    rows = [("Strategy", "Win%", "Median", "Mean", "Std", "Best", "Worst")]
    for name, results, color, _ in groups:
        adv  = [r.god_advantage for r in results]
        gw   = sum(r.god_wins for r in results)
        rows.append((
            name,
            f"{gw / len(results) * 100:.0f}%",
            f"{np.median(adv):+.1f}%",
            f"{np.mean(adv):+.1f}%",
            f"{np.std(adv):.1f}%",
            f"{max(adv):+.1f}%",
            f"{min(adv):+.1f}%",
        ))

    col_labels = rows[0]
    col_x = [0.02, 0.32, 0.46, 0.59, 0.70, 0.80, 0.91]
    y_pos  = 0.93

    for j, label in enumerate(col_labels):
        ax.text(col_x[j], y_pos, label, transform=ax.transAxes,
                fontsize=8.5, fontweight="bold", color="black", va="top")
    y_pos -= 0.08
    ax.plot([0.02, 0.98], [y_pos + 0.02, y_pos + 0.02],
            color="black", lw=0.8, transform=ax.transAxes)

    for ri, (name, *vals) in enumerate(rows[1:], 0):
        color = groups[ri][2]
        ax.text(col_x[0], y_pos, name, transform=ax.transAxes,
                fontsize=8, color=color, fontweight="bold", va="top")
        for j, v in enumerate(vals, 1):
            ax.text(col_x[j], y_pos, v, transform=ax.transAxes,
                    fontsize=8, color="black", va="top")
        y_pos -= 0.10

    ax.set_title("Summary Scorecard", fontsize=10, fontweight="bold")

    plt.tight_layout()
    out = CHARTS_DIR / "rolling_comparison.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Chart saved: {out}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("Loading data...")
    prices      = load_prices(NOMINAL_CSV)
    div_yields  = load_dividends()
    bond_yields = load_bond_yields(prices)

    print("\nRunning all three God strategies across all valid 40-year windows…")
    w_mag, w_5yr, w_10yr = run_all_windows_three_strategies(prices, div_yields, bond_yields)

    print_summary(w_mag,  "GOD MAGGIULLI — ALL WINDOWS")
    print_summary(w_5yr,  "GOD 5-YEAR   — ALL WINDOWS")
    print_summary(w_10yr, "GOD 10-YEAR  — ALL WINDOWS")

    plot_windows_comparison(w_mag, w_5yr, w_10yr)
    print("\nAll done.")
