"""Chart builders for the canonical Shiller real-total-return experiment."""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

from god_paradox import CHARTS_DIR


_DCA = "#2980B9"
_BASE = "#7F8C8D"
_MAG = "#C0392B"
_5YR = "#E67E22"
_10YR = "#8E44AD"
_GREY = "#7F8C8D"


def _fmt_money(value: float) -> str:
    if abs(value) >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    if abs(value) >= 1_000:
        return f"${value / 1_000:.0f}K"
    return f"${value:.0f}"


_MONEY_FMT = mticker.FuncFormatter(lambda value, _: _fmt_money(value))


def plot_buy_timeline(result: dict) -> None:
    prices = result["prices"]
    strategies = [
        ("God Mag 0% cash", result["buys_mag_base"], _BASE),
        ("God Mag real T-bill", result["buys_mag"], _MAG),
        ("God 5-Year real T-bill", result["buys_5yr"], _5YR),
        ("God 10-Year real T-bill", result["buys_10yr"], _10YR),
    ]

    fig, axes = plt.subplots(4, 1, figsize=(16, 14), sharex=True)
    fig.suptitle(
        "God Buy Schedules on Shiller Real Total Return S&P 500\n"
        "Vertical stems show cash deployed at each buy date",
        fontsize=12,
        fontweight="bold",
    )

    for ax, (title, buys, color) in zip(axes, strategies):
        ax.plot(prices.index, prices.values, color="#BBBBBB", lw=1.3)
        ax.set_yscale("log")
        ax.yaxis.set_major_formatter(_MONEY_FMT)
        ax.set_ylabel("Real TR index", fontsize=8)
        ax.grid(alpha=0.18)

        ax_cash = ax.twinx()
        max_cash = max((buy.cash_deployed for buy in buys), default=1.0)
        for buy in buys:
            ax_cash.vlines(buy.date, 0, buy.cash_deployed, color=color, linewidth=1.5, alpha=0.65)
            ax_cash.plot(buy.date, buy.cash_deployed, "o", color=color, markersize=3)
        if len(buys) <= 25:
            for buy in buys:
                ax_cash.annotate(
                    _fmt_money(buy.cash_deployed),
                    xy=(buy.date, buy.cash_deployed),
                    xytext=(0, 6),
                    textcoords="offset points",
                    ha="center",
                    va="bottom",
                    fontsize=6.5,
                    color=color,
                    rotation=45,
                )
        ax_cash.set_ylim(0, max_cash * 1.35)
        ax_cash.yaxis.set_major_formatter(_MONEY_FMT)
        ax_cash.tick_params(axis="y", labelsize=7, colors=color)
        ax_cash.set_ylabel("Cash deployed", fontsize=8, color=color)
        ax.set_title(f"{title} - {len(buys)} buys", fontsize=10, fontweight="bold")

    axes[-1].set_xlabel("Year")
    fig.tight_layout()
    out = CHARTS_DIR / "buy_timeline.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Chart saved: {out}")


def plot_comparison_growth(result: dict) -> None:
    series = [
        ("DCA", result["dca"], _DCA, "-"),
        ("God Mag 0% cash", result["god_mag_base"], _BASE, "--"),
        ("God Mag real T-bill", result["god_mag"], _MAG, ":"),
        ("God 5-Year real T-bill", result["god_5yr"], _5YR, "-."),
        ("God 10-Year real T-bill", result["god_10yr"], _10YR, (0, (5, 2))),
    ]

    fig, ax = plt.subplots(figsize=(14, 6))
    fig.suptitle(
        "Portfolio Growth: DCA vs God Strategies (Jan 1920 - May 2026)\n"
        "Shiller real total return; no separate dividend yield applied",
        fontsize=12,
        fontweight="bold",
    )

    for label, values, color, style in series:
        ax.plot(values.index, values.values, color=color, lw=1.8, ls=style, label=label)

    offsets = [8, -8, -24, -40, -56]
    for (label, values, color, _), offset in zip(series, offsets):
        ax.annotate(
            f"{label}: {_fmt_money(values.iloc[-1])}",
            xy=(values.index[-1], values.iloc[-1]),
            xytext=(6, offset),
            textcoords="offset points",
            ha="left",
            fontsize=8,
            color=color,
            fontweight="bold",
        )

    ax.yaxis.set_major_formatter(_MONEY_FMT)
    ax.set_ylabel("Real portfolio value")
    ax.legend(fontsize=8.5, loc="upper left")
    ax.grid(alpha=0.25)

    fig.tight_layout()
    out = CHARTS_DIR / "comparison_growth.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Chart saved: {out}")


def plot_final_bars(result: dict) -> None:
    labels = ["DCA", "Mag\n0% cash", "Mag\nreal T-bill", "5-Year\nreal T-bill", "10-Year\nreal T-bill"]
    finals = [
        result["final_dca"],
        result["final_mag_base"],
        result["final_mag"],
        result["final_5yr"],
        result["final_10yr"],
    ]
    colors = [_DCA, _BASE, _MAG, _5YR, _10YR]
    total = result["total_contributed"]
    dca_final = result["final_dca"]

    fig, ax = plt.subplots(figsize=(11, 6))
    x = np.arange(len(labels))
    bars = ax.bar(x, finals, 0.55, color=colors, alpha=0.88)
    ax.axhline(total, color=_GREY, lw=1.2, ls="--", alpha=0.7)
    ax.text(x[0] - 0.45, total, f"Total contributed: {_fmt_money(total)}", ha="right", va="bottom", fontsize=7.5)

    for bar, final in zip(bars, finals):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            final * 1.007,
            _fmt_money(final),
            ha="center",
            va="bottom",
            fontsize=8,
            fontweight="bold",
        )

    for bar, final in zip(bars[1:], finals[1:]):
        edge = (final / dca_final - 1.0) * 100.0
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            final * 0.42,
            f"{edge:+.1f}%\nvs DCA",
            ha="center",
            va="center",
            fontsize=8,
            fontweight="bold",
            color="white",
        )

    ax.set_title("Final Real Portfolio Value", fontsize=11, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel("Real portfolio value")
    ax.yaxis.set_major_formatter(_MONEY_FMT)
    ax.grid(alpha=0.25, axis="y")

    fig.tight_layout()
    out = CHARTS_DIR / "final_bars.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Chart saved: {out}")


def plot_all_multi(result: dict) -> None:
    plot_buy_timeline(result)
    plot_comparison_growth(result)
    plot_final_bars(result)
