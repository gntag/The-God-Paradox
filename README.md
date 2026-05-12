# The God Paradox

**Does perfect market-timing beat dollar-cost averaging — even when God's idle cash earns real T-bill interest?**

A quantitative re-examination of Nick Maggiulli's 2019 result _"Even God Couldn't Beat Dollar-Cost Averaging"_, with five strategies across the full 1920–2026 inflation-adjusted S&P 500 history.

---

## Background

Maggiulli's original experiment showed that a God-like investor who buys at _every_ market bottom (every inter-all-time-high trough) still **loses to DCA ~70% of the time** over rolling 40-year windows. A key assumption: idle cash earns 0%.

This experiment replicates that baseline exactly, then extends it by letting God's idle cash earn the **real (inflation-adjusted) 1-year T-bill rate** while waiting to deploy. The real rate is computed via the Fisher equation applied to a 12-month trailing CPI window — internally consistent with the real total return index used for equity prices.

---

## Data

- **Price series**: Shiller Real Total Return S&P 500 (`ie_data.xls`, column J — the `real_tr` index with dividends already reinvested and returns inflation-adjusted)
- **Dividends**: Embedded in the real total return index — no separate DRIP is applied
- **Nominal T-bill rate**: 1-year short rate (Shiller `chapt26.xlsx` pre-1962, FRED `DGS1.xlsx` 1962–2026)
- **CPI**: Shiller `ie_data.xls` column E — single consistent source, full history 1871–2026
- **Real T-bill rate**: Fisher equation — `(1 + nominal_effective) / (1 + trailing_12m_CPI) − 1`
- **Date range**: Jan 1920 – May 2026 (1,277 monthly observations)

---

## Strategies

| Strategy | Cash yield | Buy rule |
|----------|-----------|----------|
| **DCA** | — | $100/month, fully invested, no timing |
| **God Maggiulli (0% cash)** | 0% | Every inter-ATH trough on the full series — exact Maggiulli 2019 replication |
| **God Maggiulli (real T-bill)** | Real T-bill | Same buy schedule; idle cash earns Fisher real rate |
| **God 5-Year** | Real T-bill | Once per 5-year block anchored to the experiment/window start year |
| **God 10-Year** | Real T-bill | Once per 10-year block anchored to the experiment/window start year |

Every strategy contributes the same **$100/month**. God accumulates that cash (plus real interest) and deploys everything at once at the buy moment; DCA invests immediately every month.

---

## Bottom Detection — Maggiulli's Two-Pass Algorithm

`maggiulli_global_bottoms()` is a faithful Python port of Maggiulli's `create_full_dd()` R function:

1. Forward pass: track the running all-time-high and the minimum drawdown within each inter-ATH segment.
2. Backward pass: propagate that minimum back through each segment.
3. Select the first row per segment where the current drawdown equals the segment minimum — these are the troughs God buys.

The schedule is computed **once** on the full 1920–2026 series. Each rolling window filters it to dates within its range, exactly as Maggiulli's original `filter(date >= start, date <= end)`.

---

## Real Rate Methodology

God's idle cash earns the **Fisher-equation real T-bill rate**, keeping the cash yield in the same unit (real purchasing power) as the equity index:

```
r_real = (1 + nominal_effective) / (1 + π_trailing_12m) − 1
```

where `π_trailing_12m = CPI[t] / CPI[t−12] − 1`. FRED `DGS1` is a bond-equivalent yield, so from 1962 onward `nominal_effective = (1 + DGS1/2)² − 1`. Shiller's pre-1962 one-year rate is already annual and is passed through as `nominal_effective`.

CPI is sourced entirely from `ie_data.xls` — the same file as the price series. **Negative real rates are allowed**: during high-inflation periods God's idle cash genuinely loses real purchasing power, consistent with the historical experience of holding T-bills during the 1970s.

---

## Experiments

| # | Experiment | Scope |
|---|------------|-------|
| **A** | Full run | Jan 1920 – May 2026 |
| **B** | Exhaustive rolling windows | All 798 valid 40-year monthly-start windows |

---

## Results

### Scenario A — Full Run (Jan 1920 – May 2026)

*Total contributed by each strategy: $127,700. All values inflation-adjusted (real).*

| Strategy | Final Value | vs DCA | # Buys | Cash yield |
|----------|-------------|--------|--------|-----------|
| **DCA** | $35,426,472 | — | every month | — |
| **God Mag (0% cash)** | $37,980,987 | **+7.2%** | 104 | 0% |
| **God Mag (real T-bill)** | $39,989,271 | **+12.9%** | 104 | Real T-bill |
| **God 5-Year** | $46,194,126 | **+30.4%** | 22 | Real T-bill |
| **God 10-Year** | $52,052,778 | **+46.9%** | 11 | Real T-bill |

---

### Scenario B — Exhaustive Rolling Windows (798 windows × 40 years)

> **God Win Rate** = % of windows where God's final portfolio > DCA's final portfolio.

| Strategy | God Win Rate | Median Adv | Mean Adv | Std Dev | Best | Worst |
|----------|-------------|-----------|---------|---------|------|-------|
| **Baseline (0% cash)** | **31%** (247/798) | −1.7% | −0.4% | 8.3% | +22.2% | −17.3% |
| **Maggiulli (real T-bill)** | **62%** (498/798) | +2.7% | +3.2% | 9.2% | +31.0% | −11.4% |
| **5-Year (real T-bill)** | **70%** (558/798) | +6.1% | +9.9% | 16.9% | +64.1% | −13.2% |
| **10-Year (real T-bill)** | **47%** (374/798) | −1.9% | +3.8% | 20.8% | +53.6% | −32.3% |

---

## Key Findings

**Baseline validates the replication:** God wins 31% of 40-year windows with 0% cash yield on real total returns — matching Maggiulli's published ~30% figure.

**Real rates keep cash and equities in the same unit:** God's idle cash earns the Fisher-equation real T-bill rate, keeping the cash yield in the same unit of account as the Shiller Real Total Return index. During high-inflation periods God's war chest loses real purchasing power; during deflation it grows. The cash yield assumption directly affects how much God deploys at each bottom.

**Full-run (Scenario A): Great Depression deflation creates a compounding bonus:** Strongly positive real rates in 1929–1933 (deflation made every dollar grow in real terms) built a large war chest deployed at the 1932 bottom. This deflation windfall outweighs the stagflation penalty over the 106-year full run: God Mag finishes +12.9% ahead of DCA; God 10-Year +46.9%.

**Rolling windows tell the more nuanced story:** Windows starting in the 1940s–1960s capture the full stagflation era (where real rates were often negative) but miss the Depression deflation bonus. In those windows, God's cash shrinks in real terms while waiting, reducing the deployed war chest and cutting the win rate significantly.

**God 10-Year (47%) loses to DCA in the majority of rolling windows:** Window-relative 10-year blocks can expose the strategy to a full 10-year block of weak or negative real cash returns before deployment, which is devastatingly punishing. The worst 10-Year window loses −32.3% to DCA; the median outcome is −1.9% (DCA wins on the median). The 5-Year strategy (70%) is far more robust because a 5-year wait through negative real rates is less damaging — the worst 5-Year window is only −13.2%.

---

## Prerequisites

```bash
pip install pandas numpy matplotlib openpyxl pyyaml "xlrd>=2.0.1"
```

> `xlrd >= 2.0.1` reads Shiller's old binary `.xls` file. `.xlsx` files are handled by `openpyxl`.

---

## Data Files Required

Place these files relative to the repo (see `config.yaml` for exact paths):

| File | Default location | Source |
|------|-----------------|--------|
| `ie_data.xls` | `../shiller_data/` | [Robert Shiller — Irrational Exuberance data](http://www.econ.yale.edu/~shiller/data.htm) |
| `DGS1.xlsx` | `../Treasury_Yields/` | [FRED — 1-Year Treasury Constant Maturity](https://fred.stlouisfed.org/series/DGS1) |
| `chapt26.xlsx` | `../shiller_data/` | Robert Shiller — _Irrational Exuberance_ appendix |

---

## How to Run

**Option 1 — Jupyter notebook** (recommended):
```bash
jupyter notebook god_paradox.ipynb
```

**Option 2 — Scripts**:
```bash
# Scenario A: full run (Jan 1920 – May 2026)
python god_paradox.py

# Scenario B: all 798 rolling windows (runtime depends on machine)
python rolling_windows.py

# Export results to Excel
python export.py
```

---

## File Structure

```
The_God_Paradox/
├── config.yaml             # all tunable parameters
├── god_paradox.py          # data loading, strategy simulation, Scenario A
├── rolling_windows.py      # exhaustive rolling-window analysis, Scenario B
├── charts.py               # chart builders
├── export.py               # Excel export — full_run.xlsx + rolling_windows.xlsx
├── god_paradox.ipynb       # end-to-end notebook (recommended entry point)
├── charts/                 # generated PNG charts (not in repo)
└── exports/                # generated Excel files (not in repo)

../shiller_data/
├── ie_data.xls             # Shiller Real Total Return S&P 500 + CPI (primary data)
└── chapt26.xlsx            # Shiller short-term rate, pre-1962

../Treasury_Yields/
└── DGS1.xlsx               # FRED 1-yr T-bill daily rates, 1962–2026
```

---

## Configuration (`config.yaml`)

```yaml
paths:
  shiller_ies_xls: "../shiller_data/ie_data.xls"   # Shiller real total return + CPI
  dgs1_xlsx:       "../Treasury_Yields/DGS1.xlsx"   # FRED 1-yr nominal T-bill
  shiller_xlsx:    "../shiller_data/chapt26.xlsx"   # pre-1962 short rate
  charts_dir:      "charts"
  exports_dir:     "exports"

experiment:
  start_date:           "1920-01-01"
  monthly_contribution: 100.0
  period_years:         10          # default God period (overridden for 5yr runs)

rolling_windows:
  window_years: 40
```

---

## Data Sources

- **Primary price series + CPI**: Robert Shiller, _Irrational Exuberance_ — [ie_data.xls](http://www.econ.yale.edu/~shiller/data.htm) (Real Total Return column J; CPI column E)
- **1-year T-bill rate (1962–2026)**: [FRED DGS1](https://fred.stlouisfed.org/series/DGS1)
- **Short-term rate (pre-1962)**: Robert Shiller, _Irrational Exuberance_ appendix (`chapt26.xlsx`)
- **Original experiment**: Nick Maggiulli, [Of Dollars and Data](https://ofdollarsanddata.com/even-god-couldnt-beat-dollar-cost-averaging/) (2019)
- **Original R code**: [nmaggiulli/of-dollars-and-data](https://github.com/nmaggiulli/of-dollars-and-data) — `0110_buy_dips.R`

---

## License

MIT
