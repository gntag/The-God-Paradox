"""
Charts for The God Paradox experiment.
Output directory is read from config.yaml (paths.charts_dir).
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
from god_paradox import CHARTS_DIR, PERIOD_YEARS

OUT_DIR = CHARTS_DIR

# ── Colour palette ─────────────────────────────────────────────────────────────
_GOD   = "#C0392B"   # vermilion  — God / Maggiulli strategy
_DCA   = "#2980B9"   # steel-blue — DCA strategy
_5YR   = "#E67E22"   # orange     — God 5-year strategy
_10YR  = "#8E44AD"   # purple     — God 10-year strategy
_AHEAD = "#27AE60"   # emerald    — shading: God ahead of DCA
_TRAIL = "#E74C3C"   # light-red  — shading: DCA ahead of God
_GREY  = "#7F8C8D"   # neutral annotations

# ── Crash / event name for each calendar decade ────────────────────────────────
_EVENTS: dict[int, str] = {
    1920: "Great Depression",
    1930: "Great Depression",
    1940: "WWII Trough",
    1950: "Korean War",
    1960: "1960s Bear Market",
    1970: "Oil Crisis",
    1980: "Black Monday",
    1990: "Early-90s Slump",
    2000: "Dot-com / GFC",
    2010: "Post-GFC Era",
    2020: "COVID Crash",
}


def _decade_event(label: str) -> str:
    """'1930-1939'  →  'Great Depression'."""
    return _EVENTS.get((int(label[:4]) // 10) * 10, "")


def _fmt_M(val: float) -> str:
    """Human-readable dollar amount: $1.2M / $450K / $920."""
    if abs(val) >= 1_000_000:
        return f"${val / 1_000_000:.1f}M"
    if abs(val) >= 1_000:
        return f"${val / 1_000:.0f}K"
    return f"${val:.0f}"


_TICK_FMT = mticker.FuncFormatter(lambda x, _: _fmt_M(x))
_PCT_FMT  = mticker.FuncFormatter(lambda x, _: f"{x:+.0f}%")


# ── Chart builders ─────────────────────────────────────────────────────────────

def plot_portfolio_growth(
    result: dict,
    ax_portfolio: plt.Axes,
    ax_advantage: plt.Axes,
) -> None:
    """
    Left panel  — portfolio value over time (DCA vs God), shaded and annotated.
    Right panel — God's % lead over DCA; 0 % = dead heat.
    """
    dca:   pd.Series = result["dca"]
    god:   pd.Series = result["god"]
    buys:  list      = result["buys"]
    label: str       = result["label"]

    dca_a = dca.values
    god_a = god.values

    # ── Portfolio lines ───────────────────────────────────────────────────────
    ax = ax_portfolio
    ax.plot(dca.index, dca_a, color=_DCA, lw=1.8,
            label="DCA — $100/month, every month")
    ax.plot(god.index, god_a, color=_GOD, lw=1.8, ls="--",
            label=f"God — waits for each {PERIOD_YEARS}-year period's lowest point")

    ax.fill_between(dca.index, dca_a, god_a, where=(god_a >= dca_a),
                    alpha=0.12, color=_AHEAD, label="God ahead")
    ax.fill_between(dca.index, dca_a, god_a, where=(god_a <  dca_a),
                    alpha=0.12, color=_TRAIL, label="DCA ahead")

    # Annotate each God buy with decade + crash name
    for buy in buys:
        event = _decade_event(buy.decade_label)
        ann   = f"{buy.decade_label[:4]}s\n{event}" if event else buy.decade_label
        ax.axvline(buy.date, color=_GOD, lw=0.7, alpha=0.40, zorder=1)
        y_ann = god.loc[buy.date] if buy.date in god.index else god.iloc[0]
        ax.annotate(
            ann,
            xy=(buy.date, y_ann),
            xytext=(0, 22),
            textcoords="offset points",
            ha="center", va="bottom",
            fontsize=6.5, color=_GOD, alpha=0.85,
            rotation=40,
        )

    # Final-value callouts
    ax.annotate(
        f"DCA: {_fmt_M(dca.iloc[-1])}",
        xy=(dca.index[-1], dca.iloc[-1]),
        xytext=(-8, 10), textcoords="offset points",
        ha="right", fontsize=9, color=_DCA, fontweight="bold",
    )
    ax.annotate(
        f"God: {_fmt_M(god.iloc[-1])}",
        xy=(god.index[-1], god.iloc[-1]),
        xytext=(-8, -14), textcoords="offset points",
        ha="right", fontsize=9, color=_GOD, fontweight="bold",
    )

    ax.set_title(f"Portfolio Growth — {label}", fontsize=11, fontweight="bold")
    ax.set_ylabel("Portfolio Value")
    ax.yaxis.set_major_formatter(_TICK_FMT)
    ax.legend(fontsize=8, loc="upper left")
    ax.grid(True, alpha=0.25)

    # ── God's % lead / lag over time ──────────────────────────────────────────
    adv = (god / dca - 1) * 100
    ax2 = ax_advantage
    ax2.plot(adv.index, adv.values, color=_GOD, lw=1.3)
    ax2.axhline(0, color="black", lw=0.9, ls=":")
    ax2.fill_between(adv.index, adv.values, 0, where=(adv.values >= 0),
                     alpha=0.18, color=_AHEAD, label="God ahead")
    ax2.fill_between(adv.index, adv.values, 0, where=(adv.values <  0),
                     alpha=0.18, color=_TRAIL, label="DCA ahead")
    ax2.text(
        adv.index[max(1, len(adv) // 30)], 0.5,
        "← Dead Heat",
        fontsize=7.5, color="black", va="bottom", alpha=0.75,
    )
    ax2.set_title(f"God's Lead over DCA — {label}", fontsize=10)
    ax2.set_ylabel("God's lead over DCA (%)")
    ax2.yaxis.set_major_formatter(_PCT_FMT)
    ax2.legend(fontsize=8)
    ax2.grid(True, alpha=0.25)


def plot_final_bar(result: dict, ax: plt.Axes) -> None:
    """Bar chart: DCA vs God final portfolio values, with total-invested baseline."""
    finals    = [result["final_dca"], result["final_god"]]
    colors    = [_DCA, _GOD]
    labels    = ["DCA", "God"]
    total_inv = result["total_contributed"]

    x     = np.arange(len(labels))
    width = 0.45
    bars  = ax.bar(x, finals, width, color=colors, alpha=0.85, label=labels)

    # Total-invested baseline
    ax.axhline(total_inv, color=_GREY, lw=1.3, ls="--", alpha=0.75)
    ax.text(
        x[0] - width / 2 - 0.05, total_inv,
        f"Total invested: {_fmt_M(total_inv)}",
        fontsize=7.5, color=_GREY, va="bottom", ha="right",
    )

    # Value label at top of each bar
    for bar in bars:
        h = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2, h * 1.005,
            _fmt_M(h), ha="center", va="bottom", fontsize=8, fontweight="bold",
        )

    # God % advantage — centred inside the God bar (white text)
    pct  = (result["final_god"] / result["final_dca"] - 1) * 100
    sign = "+" if pct >= 0 else ""
    ax.text(
        x[1], result["final_god"] * 0.40,
        f"{sign}{pct:.0f}%\nahead",
        ha="center", va="center",
        fontsize=9, fontweight="bold", color="white",
    )

    ax.set_title("Final Portfolio Value in 2026", fontsize=11, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=10)
    ax.set_ylabel("Final Portfolio Value")
    ax.yaxis.set_major_formatter(_TICK_FMT)
    ax.grid(True, alpha=0.25, axis="y")


def plot_decade_bars(result: dict, ax: plt.Axes) -> None:
    """Horizontal bars: cash God deploys at each decade's crash trough, with crash name."""
    buys = result["buys"]
    if not buys:
        return

    labels = []
    for b in buys:
        event = _decade_event(b.decade_label)
        labels.append(f"{b.decade_label[:4]}s — {event}" if event else b.decade_label)
    cash   = [b.cash_deployed for b in buys]
    prices = [b.price         for b in buys]

    y    = np.arange(len(labels))
    bars = ax.barh(y, cash, color=_GOD, alpha=0.78)

    for bar, price in zip(bars, prices):
        w = bar.get_width()
        # Buy price inside bar (white text)
        ax.text(
            min(w * 0.04, 200),
            bar.get_y() + bar.get_height() / 2,
            f"S&P: ${price:,.0f}",
            va="center", fontsize=7.5, color="white", fontweight="bold",
        )
        # Cash amount outside bar
        ax.text(
            w + max(w * 0.02, 80),
            bar.get_y() + bar.get_height() / 2,
            _fmt_M(w),
            va="center", fontsize=8,
        )

    ax.set_title(
        f"Cash God Deploys at Each {PERIOD_YEARS}-Year Period Low\n{result['label']}",
        fontsize=10, fontweight="bold",
    )
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=8.5)
    ax.set_xlabel("Cash Deployed at Crash Low")
    ax.xaxis.set_major_formatter(_TICK_FMT)
    ax.invert_yaxis()   # earliest decade at top
    ax.grid(True, alpha=0.25, axis="x")


def plot_all(nominal: dict) -> None:
    """Compose and save all charts to OUT_DIR."""

    # ── Figure 1: 1×2 — portfolio growth + lead/lag ───────────────────────────
    fig1, axes = plt.subplots(1, 2, figsize=(16, 5))
    fig1.suptitle(
        f"The God Paradox: Perfect {PERIOD_YEARS}-Year Timing vs. Dollar-Cost Averaging (1928–2026)\n"
        "Both invest $100/month  ·  God earns T-bill yield on idle cash  ·  Dividends reinvested",
        fontsize=12, fontweight="bold",
    )
    plot_portfolio_growth(nominal, axes[0], axes[1])
    fig1.tight_layout()
    fig1.savefig(OUT_DIR / "portfolio_growth.png", dpi=150, bbox_inches="tight")
    plt.close(fig1)
    print(f"  Chart saved: {OUT_DIR / 'portfolio_growth.png'}")

    # ── Figure 2: 1×2 — final bar + decade deployment bars ───────────────────
    fig2, axes2 = plt.subplots(1, 2, figsize=(14, 6))
    fig2.suptitle(
        "Final Values & God's Decade Deployment Schedule",
        fontsize=12, fontweight="bold",
    )
    plot_final_bar(nominal, axes2[0])
    plot_decade_bars(nominal, axes2[1])
    fig2.tight_layout()
    fig2.savefig(OUT_DIR / "final_comparison.png", dpi=150, bbox_inches="tight")
    plt.close(fig2)
    print(f"  Chart saved: {OUT_DIR / 'final_comparison.png'}")


# ── Multi-strategy chart builders ─────────────────────────────────────────────

def plot_buy_timeline(result: dict) -> None:
    """
    3-panel stacked chart (shared x-axis) showing when each God strategy buys.
    Each panel: S&P 500 price (log, gray line) + vertical cash-deployed stems (red).
    Labels shown for strategies with ≤ 25 buys.
    """
    prices     = result["prices"]
    strategies = [
        ("Maggiulli: Every Inter-ATH Trough", result["buys_mag"]),
        ("God 5-Year: Once per 5-Year Period", result["buys_5yr"]),
        ("God 10-Year: Once per Decade",       result["buys_10yr"]),
    ]

    fig, axes = plt.subplots(3, 1, figsize=(16, 13), sharex=True)
    fig.suptitle(
        "When Does God Buy?  —  Buy Schedule Across All Three Strategies\n"
        "Red stems = cash deployed at each buy  ·  Gray line = S&P 500 (log scale)",
        fontsize=12, fontweight="bold",
    )

    for ax, (title, buys) in zip(axes, strategies):
        # S&P 500 price background (log scale, left y-axis)
        ax.plot(prices.index, prices.values, color="#BBBBBB", lw=1.4, zorder=1)
        ax.set_yscale("log")
        ax.set_ylabel("S&P 500 (log)", fontsize=8, color="#888888")
        ax.tick_params(axis="y", labelcolor="#888888", labelsize=7)
        ax.yaxis.set_major_formatter(
            mticker.FuncFormatter(lambda x, _: f"${x:,.0f}")
        )

        # Cash deployed stems on right y-axis
        ax2 = ax.twinx()
        cash_vals = [b.cash_deployed for b in buys]

        for b in buys:
            ax2.vlines(b.date, 0, b.cash_deployed, color=_GOD, linewidth=1.8,
                       alpha=0.60, zorder=2)
            ax2.plot(b.date, b.cash_deployed, "o", color=_GOD,
                     markersize=3.5, zorder=3)

        # Labels only when the chart won't be too crowded
        if len(buys) <= 25:
            for b in buys:
                ax2.annotate(
                    _fmt_M(b.cash_deployed),
                    xy=(b.date, b.cash_deployed),
                    xytext=(0, 6), textcoords="offset points",
                    ha="center", va="bottom", fontsize=6.5, color=_GOD,
                    rotation=45,
                )

        ax2.set_ylabel("Cash Deployed", fontsize=8, color=_GOD)
        ax2.tick_params(axis="y", labelcolor=_GOD, labelsize=7)
        ax2.yaxis.set_major_formatter(_TICK_FMT)
        ax2.set_ylim(0, max(cash_vals) * 1.40 if cash_vals else 1)

        total_deployed = sum(cash_vals)
        ax.set_title(
            f"{title}  ·  {len(buys)} buys  ·  Total cash deployed: {_fmt_M(total_deployed)}",
            fontsize=10, fontweight="bold", pad=5,
        )
        ax.grid(True, alpha=0.15, zorder=0)

    axes[-1].set_xlabel("Year")
    fig.tight_layout()
    out = OUT_DIR / "buy_timeline.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Chart saved: {out}")


def plot_comparison_growth(result: dict) -> None:
    """
    Single-panel portfolio growth comparison: DCA vs all three God strategies.
    """
    dca      = result["dca"]
    god_mag  = result["god_mag"]
    god_5yr  = result["god_5yr"]
    god_10yr = result["god_10yr"]

    fig, ax = plt.subplots(figsize=(14, 6))
    fig.suptitle(
        "Portfolio Growth: DCA vs All Three God Strategies  (1928–2026)\n"
        "$100/month  ·  Dividends reinvested  ·  God earns T-bill yield on idle cash",
        fontsize=12, fontweight="bold",
    )

    ax.plot(dca.index,      dca.values,      color=_DCA,  lw=2.2,
            label="DCA — $100/month, every month")
    ax.plot(god_mag.index,  god_mag.values,  color=_GOD,  lw=1.6, ls=":",
            label=f"God Maggiulli — every inter-ATH trough  ({len(result['buys_mag'])} buys)")
    ax.plot(god_5yr.index,  god_5yr.values,  color=_5YR,  lw=1.6, ls="--",
            label=f"God 5-Year — once per 5-yr period  ({len(result['buys_5yr'])} buys)")
    ax.plot(god_10yr.index, god_10yr.values, color=_10YR, lw=1.6, ls="-.",
            label=f"God 10-Year — once per decade  ({len(result['buys_10yr'])} buys)")

    # Final-value callouts (right edge, staggered)
    callouts = [
        (dca,      _DCA,  f"DCA: {_fmt_M(dca.iloc[-1])}",         8),
        (god_5yr,  _5YR,  f"5yr: {_fmt_M(god_5yr.iloc[-1])}",    -6),
        (god_10yr, _10YR, f"10yr: {_fmt_M(god_10yr.iloc[-1])}",  -20),
        (god_mag,  _GOD,  f"Mag: {_fmt_M(god_mag.iloc[-1])}",    -34),
    ]
    for series, color, label, y_off in callouts:
        ax.annotate(
            label,
            xy=(series.index[-1], series.iloc[-1]),
            xytext=(6, y_off), textcoords="offset points",
            ha="left", fontsize=8.5, color=color, fontweight="bold",
        )

    ax.yaxis.set_major_formatter(_TICK_FMT)
    ax.legend(fontsize=8.5, loc="upper left")
    ax.grid(True, alpha=0.25)
    ax.set_ylabel("Portfolio Value")

    fig.tight_layout()
    out = OUT_DIR / "comparison_growth.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Chart saved: {out}")


def plot_final_bars(result: dict) -> None:
    """4-bar final-value comparison: DCA + all three God strategies."""
    labels = ["DCA", "God\nMaggiulli", "God\n5-Year", "God\n10-Year"]
    finals = [
        result["final_dca"], result["final_mag"],
        result["final_5yr"], result["final_10yr"],
    ]
    colors = [_DCA, _GOD, _5YR, _10YR]
    total  = result["total_contributed"]
    dca_v  = result["final_dca"]

    fig, ax = plt.subplots(figsize=(10, 6))
    x    = np.arange(len(labels))
    bars = ax.bar(x, finals, 0.50, color=colors, alpha=0.87)

    # Total-invested baseline
    ax.axhline(total, color=_GREY, lw=1.3, ls="--", alpha=0.75)
    ax.text(x[0] - 0.40, total,
            f"Total invested: {_fmt_M(total)}",
            fontsize=7.5, color=_GREY, va="bottom", ha="right")

    # Value labels above each bar
    for bar, val in zip(bars, finals):
        ax.text(bar.get_x() + bar.get_width() / 2, val * 1.008,
                _fmt_M(val), ha="center", va="bottom",
                fontsize=8.5, fontweight="bold")

    # % vs DCA inside God bars
    for bar, val in zip(bars[1:], finals[1:]):
        pct  = (val / dca_v - 1) * 100
        sign = "+" if pct >= 0 else ""
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            val * 0.42,
            f"{sign}{pct:.0f}%\nvs DCA",
            ha="center", va="center",
            fontsize=8.5, fontweight="bold", color="white",
        )

    ax.set_title(
        "Final Portfolio Value — 1928–2026\n"
        "$100/month  ·  Dividends reinvested  ·  T-bill yield on idle cash",
        fontsize=11, fontweight="bold",
    )
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=10)
    ax.set_ylabel("Final Portfolio Value")
    ax.yaxis.set_major_formatter(_TICK_FMT)
    ax.grid(True, alpha=0.25, axis="y")

    fig.tight_layout()
    out = OUT_DIR / "final_bars.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Chart saved: {out}")


def plot_all_multi(result: dict) -> None:
    """Save all three multi-strategy charts to OUT_DIR."""
    plot_buy_timeline(result)
    plot_comparison_growth(result)
    plot_final_bars(result)
