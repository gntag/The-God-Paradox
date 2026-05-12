"""Excel exports for the canonical Shiller real-total-return experiment."""

from __future__ import annotations

import numpy as np
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from god_paradox import (
    EXPORTS_DIR,
    MONTHLY_CONTRIBUTION,
    load_bond_yields,
    load_cpi_series,
    load_shiller_real_tr,
    run_all_strategies,
)
from rolling_windows import WindowResult, run_all_windows_all_strategies


_HEADER_FILL = PatternFill("solid", fgColor="1F4E79")
_ALT_FILL = PatternFill("solid", fgColor="D6E4F0")
_HEADER_FONT = Font(bold=True, color="FFFFFF", size=10)
_BODY_FONT = Font(size=10)
_THIN = Side(style="thin", color="BBBBBB")
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)

_NUM_FMT_DATE = "YYYY-MM-DD"
_NUM_FMT_DOLLAR = "#,##0.00"
_NUM_FMT_INT = "#,##0"
_NUM_FMT_PCT = "0.00%"


def _style_header(cell) -> None:
    cell.font = _HEADER_FONT
    cell.fill = _HEADER_FILL
    cell.alignment = Alignment(horizontal="center", vertical="center")
    cell.border = _BORDER


def _style_body(cell, fill=None) -> None:
    cell.font = _BODY_FONT
    cell.fill = fill or PatternFill()
    cell.alignment = Alignment(horizontal="right")
    cell.border = _BORDER


def _set_col_widths(ws, widths: list[int]) -> None:
    for i, width in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = width


def _write_df(ws, df: pd.DataFrame) -> None:
    for col_idx, col_name in enumerate(df.columns, 1):
        _style_header(ws.cell(1, col_idx, col_name))

    for row_idx, row in enumerate(df.itertuples(index=False), 2):
        fill = _ALT_FILL if row_idx % 2 == 0 else None
        for col_idx, value in enumerate(row, 1):
            cell = ws.cell(row_idx, col_idx, value)
            _style_body(cell, fill)


def _prices_tab(wb: Workbook, result: dict) -> None:
    ws = wb.create_sheet("Prices")
    ws.freeze_panes = "B2"
    df = pd.DataFrame({
        "Date": [d.date() for d in result["prices"].index],
        "Shiller Real Total Return": result["prices"].round(6).values,
        "Nominal T-Bill Annual": result["bond_yields"].values,
        "Real T-Bill Annual": result["real_cash_yields"].values,
    })
    _write_df(ws, df)
    for row in ws.iter_rows(min_row=2):
        row[0].number_format = _NUM_FMT_DATE
        row[1].number_format = _NUM_FMT_DOLLAR
        row[2].number_format = _NUM_FMT_PCT
        row[3].number_format = _NUM_FMT_PCT
    _set_col_widths(ws, [14, 24, 20, 18])


def _portfolio_tab(wb: Workbook, result: dict) -> None:
    ws = wb.create_sheet("Portfolio_Values")
    ws.freeze_panes = "B2"
    df = pd.DataFrame({
        "Date": [d.date() for d in result["prices"].index],
        "DCA": result["dca"].values,
        "God Mag 0% Cash": result["god_mag_base"].values,
        "God Mag Real T-Bill": result["god_mag"].values,
        "God 5-Year Real T-Bill": result["god_5yr"].values,
        "God 10-Year Real T-Bill": result["god_10yr"].values,
    })
    _write_df(ws, df.round(2))
    for row in ws.iter_rows(min_row=2):
        row[0].number_format = _NUM_FMT_DATE
        for cell in row[1:]:
            cell.number_format = _NUM_FMT_INT
    _set_col_widths(ws, [14, 16, 18, 22, 22, 24])


def _cash_tab(wb: Workbook, result: dict) -> None:
    ws = wb.create_sheet("Cash_Balances")
    ws.freeze_panes = "B2"
    df = pd.DataFrame({
        "Date": [d.date() for d in result["prices"].index],
        "Mag 0% Cash": result["cash_mag_base"].values,
        "Mag Real T-Bill": result["cash_mag"].values,
        "5-Year Real T-Bill": result["cash_5yr"].values,
        "10-Year Real T-Bill": result["cash_10yr"].values,
    })
    _write_df(ws, df.round(2))
    for row in ws.iter_rows(min_row=2):
        row[0].number_format = _NUM_FMT_DATE
        for cell in row[1:]:
            cell.number_format = _NUM_FMT_INT
    _set_col_widths(ws, [14, 18, 20, 22, 24])


def _summary_tab(wb: Workbook, result: dict) -> None:
    ws = wb.create_sheet("Final_Summary")
    rows = [
        ("DCA", result["final_dca"], 0.0, len(result["prices"])),
        ("God Mag 0% Cash", result["final_mag_base"], result["adv_mag_base"], len(result["buys_mag_base"])),
        ("God Mag Real T-Bill", result["final_mag"], result["adv_mag"], len(result["buys_mag"])),
        ("God 5-Year Real T-Bill", result["final_5yr"], result["adv_5yr"], len(result["buys_5yr"])),
        ("God 10-Year Real T-Bill", result["final_10yr"], result["adv_10yr"], len(result["buys_10yr"])),
    ]
    df = pd.DataFrame(rows, columns=["Strategy", "Final Value", "Vs DCA (%)", "Buys"])
    _write_df(ws, df)
    for row in ws.iter_rows(min_row=2):
        row[1].number_format = _NUM_FMT_INT
        row[2].number_format = "0.0"
    _set_col_widths(ws, [24, 18, 14, 10])


def _buy_schedule_tab(wb: Workbook, result: dict) -> None:
    ws = wb.create_sheet("Buy_Schedules")
    rows = []
    for strategy, key in [
        ("God Mag 0% Cash", "buys_mag_base"),
        ("God Mag Real T-Bill", "buys_mag"),
        ("God 5-Year Real T-Bill", "buys_5yr"),
        ("God 10-Year Real T-Bill", "buys_10yr"),
    ]:
        for buy in result[key]:
            rows.append({
                "Strategy": strategy,
                "Date": buy.date.date(),
                "Period": buy.period_label,
                "Price": round(buy.price, 2),
                "Cash Deployed": round(buy.cash_deployed, 2),
                "Months of Contributions": round(buy.cash_deployed / MONTHLY_CONTRIBUTION, 2),
            })
    _write_df(ws, pd.DataFrame(rows))
    for row in ws.iter_rows(min_row=2):
        row[1].number_format = _NUM_FMT_DATE
        row[3].number_format = _NUM_FMT_DOLLAR
        row[4].number_format = _NUM_FMT_INT
    _set_col_widths(ws, [24, 14, 16, 14, 18, 24])


def export_full_run(result: dict) -> None:
    out_path = EXPORTS_DIR / "full_run.xlsx"
    wb = Workbook()
    wb.remove(wb.active)
    _prices_tab(wb, result)
    _portfolio_tab(wb, result)
    _cash_tab(wb, result)
    _summary_tab(wb, result)
    _buy_schedule_tab(wb, result)
    wb.save(out_path)
    print(f"  Saved: {out_path}")


def _window_rows(results: list[WindowResult]) -> pd.DataFrame:
    return pd.DataFrame([{
        "Start Date": r.start_date.date(),
        "End Date": r.end_date.date(),
        "DCA Final": round(r.final_dca, 2),
        "God Final": round(r.final_god, 2),
        "God Advantage (%)": round(r.god_advantage, 4),
        "God Wins": "Yes" if r.god_wins else "No",
    } for r in results])


def _rolling_summary_tab(wb: Workbook, groups: dict[str, list[WindowResult]]) -> None:
    ws = wb.create_sheet("Comparison_Summary")
    rows = []
    for name, results in groups.items():
        advantages = np.array([r.god_advantage for r in results])
        wins = sum(r.god_wins for r in results)
        rows.append({
            "Strategy": name,
            "Windows": len(results),
            "God Wins": wins,
            "DCA Wins": len(results) - wins,
            "God Win Rate": wins / len(results),
            "Median Adv (%)": round(float(np.median(advantages)), 2),
            "Mean Adv (%)": round(float(np.mean(advantages)), 2),
            "Std Dev (%)": round(float(np.std(advantages, ddof=1)), 2),
            "Best (%)": round(float(np.max(advantages)), 2),
            "Worst (%)": round(float(np.min(advantages)), 2),
        })
    _write_df(ws, pd.DataFrame(rows))
    for row in ws.iter_rows(min_row=2):
        row[4].number_format = _NUM_FMT_PCT
    _set_col_widths(ws, [28, 10, 10, 10, 14, 16, 14, 12, 12, 12])


def export_rolling_windows(groups: dict[str, list[WindowResult]]) -> None:
    out_path = EXPORTS_DIR / "rolling_windows.xlsx"
    wb = Workbook()
    wb.remove(wb.active)

    sheet_names = {
        "Baseline 0% Cash": "Baseline_0pct_Cash",
        "Maggiulli Real T-Bill": "Maggiulli_Real_Tbill",
        "5-Year Real T-Bill": "Five_Year_Real_Tbill",
        "10-Year Real T-Bill": "Ten_Year_Real_Tbill",
    }
    for name, results in groups.items():
        ws = wb.create_sheet(sheet_names[name])
        ws.freeze_panes = "B2"
        _write_df(ws, _window_rows(results))
        for row in ws.iter_rows(min_row=2):
            row[0].number_format = _NUM_FMT_DATE
            row[1].number_format = _NUM_FMT_DATE
            row[2].number_format = _NUM_FMT_INT
            row[3].number_format = _NUM_FMT_INT
        _set_col_widths(ws, [13, 13, 16, 16, 18, 10])

    _rolling_summary_tab(wb, groups)
    wb.save(out_path)
    print(f"  Saved: {out_path}")


if __name__ == "__main__":
    print("Loading data...")
    prices = load_shiller_real_tr()
    bond_yields = load_bond_yields(prices)
    cpi = load_cpi_series()

    print("\nRunning full-run scenario...")
    result = run_all_strategies(prices, bond_yields, cpi)

    print("\nExporting full_run.xlsx...")
    export_full_run(result)

    print("\nRunning exhaustive rolling windows...")
    w_base, w_mag, w_5yr, w_10yr = run_all_windows_all_strategies(prices, bond_yields, cpi)
    groups = {
        "Baseline 0% Cash": w_base,
        "Maggiulli Real T-Bill": w_mag,
        "5-Year Real T-Bill": w_5yr,
        "10-Year Real T-Bill": w_10yr,
    }

    print("\nExporting rolling_windows.xlsx...")
    export_rolling_windows(groups)
    print(f"\nAll exports written to {EXPORTS_DIR}")
