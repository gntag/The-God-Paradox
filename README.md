# The God Paradox

**Does perfect market-timing beat dollar-cost averaging — even when God's idle cash earns T-bill interest?**

A quantitative re-examination of Nick Maggiulli's 2019 result _"Even God Couldn't Beat Dollar-Cost Averaging"_, with three God variants and one critical upgrade: **God's idle cash earns the 1-year T-bill rate** while waiting to deploy.

---

## Background

Maggiulli's original experiment showed that a God-like investor who buys at _every_ market bottom (every inter-all-time-high dip) still **loses to DCA ~70% of the time** over rolling 40-year windows. The key flaw: idle cash earns 0%.

This experiment tests three God variants with T-bill-earning cash over the full 1928–2026 S&P 500 history:

| Strategy | Buy Timing |
|----------|------------|
| **God (Maggiulli)** | Every inter-ATH trough — same as the original, but cash earns T-bill rate |
| **God 5-Year** | Once per 5-year calendar period, at the single lowest monthly price |
| **God 10-Year** | Once per decade, at the single lowest monthly price |

---

## Key Questions

| Scenario | Question |
|----------|----------|
| **A — Full Run** (1928–2026) | Which God strategy wins the entire 96-year nominal history? |
| **B — All Rolling Windows** (~702 windows) | Which strategies beat DCA most often over exhaustive 40-year periods? |

---

## Methodology

### Shared Setup
- **Monthly contribution**: $100 by both strategies every month
- **Dividends**: reinvested monthly (DRIP) on all invested shares
- **Bond yield**: 1-year T-bill rate (Shiller data pre-1962, FRED DGS1 1962–2026)

### DCA Strategy
Invest $100/month at the current S&P 500 price, every month, no exceptions.

### God Strategy (all variants)
1. Accumulate $100/month as cash, earning the **1-year T-bill rate**
2. At the buy moment, deploy **all accumulated cash** into the S&P 500
3. Reinvest dividends monthly on all invested shares

**Buy moment differs by variant:**
- **Maggiulli**: every trough between consecutive all-time-highs
- **5-Year**: the single cheapest month of each 5-year calendar block
- **10-Year**: the single cheapest month of each calendar decade

### Rolling Windows (Scenario B)
All **~702 valid** 40-year monthly-start windows from the 1928–2026 dataset, tested exhaustively — no sampling bias.

---

## Results

### Scenario A — Full Run (1928–2026)

| Strategy | Final Value | vs DCA | # Buys |
|----------|-------------|--------|--------|
| DCA | $351.9M | — | 1,176 |
| God (Maggiulli) | $267.1M | −24.1% | 98 |
| God 5-Year | $530.9M | **+50.8%** | 21 |
| God 10-Year | $506.8M | **+44.0%** | 11 |

### Scenario B — Rolling 40-Year Windows

| Strategy | Win Rate | Median Advantage | Worst Window |
|----------|----------|-----------------|--------------|
| God (Maggiulli) | 77% | +4.6% | −34% |
| God 5-Year | 70% | +4.5% | −18% |
| God 10-Year | 52% | +1.7% | −28% |

**Key finding**: Maggiulli God with T-bills wins 77% of windows but *loses* the full run — it fragments cash into ~98 small buys and forfeits decades of compounding. The calendar-period strategies concentrate firepower and win both the full run and most windows.

---

## How to Run

### Prerequisites

```bash
pip install pandas numpy matplotlib openpyxl pyyaml
```

### Data required (not included in repo)

Place data files **one level above the repo root** (see `config.yaml` for exact relative paths):

| File | Location | Source |
|------|----------|--------|
| `S&P500_normal_prices.csv` | `../S&P500/` | [multpl.com](https://www.multpl.com/s-p-500-historical-prices/table/by-month) |
| `sp500_dividend_yield_by_month_multpl.xlsx` | `../S&P500/` | [multpl.com](https://www.multpl.com/s-p-500-dividend-yield/table/by-month) |
| `DGS1.xlsx` | `../Treasury_Yields/` | [FRED](https://fred.stlouisfed.org/series/DGS1) |
| `chapt26.xlsx` | `../shiller_data/` | [Robert Shiller's website](http://www.econ.yale.edu/~shiller/data.htm) |

### Run the full experiment

**Option 1 — Jupyter notebook** (recommended):
```bash
jupyter notebook god_paradox.ipynb
```

**Option 2 — Scripts**:
```bash
# Scenario A: full run (1928-2026)
python god_paradox.py

# Scenario B: all rolling windows (~702 exhaustive)
python rolling_windows.py
```

---

## File Structure

```
./ (repo root)
├── config.yaml           # all tunable parameters
├── god_paradox.py        # core simulation: load_prices, run_dca, run_god, run_all_strategies
├── rolling_windows.py    # rolling window analysis and plots
├── charts.py             # Scenario A chart builders
├── export.py             # Excel export utilities
├── god_paradox.ipynb     # end-to-end notebook (recommended entry point)
├── charts/               # generated PNG charts (git-ignored)
└── exports/              # generated Excel files (git-ignored)

../S&P500/               # price and dividend data (not in repo)
../Treasury_Yields/      # FRED DGS1 1-yr T-bill data (not in repo)
../shiller_data/         # Shiller annual rate data (not in repo)
```

---

## Configuration

All parameters live in `config.yaml`:

```yaml
experiment:
  start_date:           "1928-01-01"
  monthly_contribution: 100.0
  period_years:         10    # default God period (10 = classic decade)

rolling_windows:
  window_years: 40
```

---

## Data Sources

- **S&P 500 prices** (nominal): [multpl.com](https://www.multpl.com)
- **S&P 500 dividend yield**: [multpl.com](https://www.multpl.com/s-p-500-dividend-yield)
- **1-year T-bill rate (1962–2026)**: [FRED DGS1](https://fred.stlouisfed.org/series/DGS1)
- **Short-term interest rate (pre-1962)**: Robert Shiller, _Irrational Exuberance_ data appendix
- **Original experiment**: Nick Maggiulli, [Of Dollars and Data](https://ofdollarsanddata.com/even-god-couldnt-beat-dollar-cost-averaging/) (2019)

---

## License

MIT
