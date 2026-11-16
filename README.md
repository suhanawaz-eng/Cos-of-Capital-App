# Cost of Capital — USD vs Local Currency

A Streamlit dashboard for comparing a project's nominal cost of equity, pretax debt cost, after-tax debt cost, and WACC in USD and a selected country's currency. It implements a U.S.-market CAPM benchmark, perpetual-debt tax shield assumptions, and a gross-rate currency conversion based on equal real rates / relative PPP.

## Deploy with GitHub and Streamlit Community Cloud

1. Create a new GitHub repository (e.g. `cost-of-capital-app`).
2. Upload **`app.py`**, **`requirements.txt`**, and **`README.md`** to the repository root.
3. Visit https://share.streamlit.io/ and select **Create app** → **Deploy a public app from GitHub**.
4. Select your repository, branch `main`, and entry point `app.py`, then deploy.
5. Wait for dependency installation; the app will attempt to load source data. Enter missing values manually if a source is blocked or changes its table layout.

## Run locally

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Sources

- [Damodaran U.S. industry betas (XLS)](https://pages.stern.nyu.edu/~adamodar/pc/datasets/betas.xls) — **Unlevered beta** (not the cash-adjusted version); HTML fallback is attempted.
- [OECD Corporate Tax Statistics 2024](https://www.oecd.org/en/publications/corporate-tax-statistics-2024_9c27d6e8-en/full-report/statutory-corporate-income-tax-rates_440f9286.html) — **manual reference only**. The app does **not** automatically retrieve jurisdiction-specific tax rates. Default 25% is a placeholder, not a claim about any country's tax rate.
- [Damodaran ratings and spreads](https://pages.stern.nyu.edu/adamodar/New_Home_Page/datafile/ratings.html) — Baa2/BBB spread for **large non-financial service firms**; automated parsing is attempted only when the column is unambiguous. Otherwise 2% is a manual placeholder.
- [Trading Economics 10-year yields](https://tradingeconomics.com/bonds) — public country table, no API key; HTML retrieval is best-effort. If unavailable, yield fields use editable 4% placeholders.

**Important:** The Streamlit app requires network access to fetch public data. Public HTML may be rate-limited or restructured. Verify all inputs before using results. Retrieval timestamps are not the underlying observations' publication dates.

## Model

Let `d = D/(D+E)` be target debt share, `τ` tax rate, `βU` industry unlevered beta, `ERP` the U.S. equity risk premium (default 6.5%), `s` the Baa2/BBB credit spread, and `Rf` a 10-year government yield. Rates are annual decimals.

### Tax shield and capital structure

- Annual deduction = `Rd × D`.
- Annual tax saving = `τ × Rd × D`.
- `PV(tax shield) = (τ × Rd × D)/Rd = τD`.
- `E + D = VU + τD`.
- `EβE + DβD = VUβU + τDβTS`.
- With `βD = βTS = 0`, `βU = βE / [1 + (1−τ)D/E]`.
- `D/E = d/(1−d)`.
- `βE = βU × [1 + (1−τ)D/E]`.

### USD

- `Re,USD = Rf,USD + βE × ERP`.
- `Rd,USD = Rf,USD + s`.
- `WACC,USD = (1−d)Re,USD + d Rd,USD(1−τ)`.

### Local currency

- `F = (1 + Rf,local)/(1 + Rf,USD)`.
- `Re,local = (1 + Re,USD)F − 1`.
- `Rd,local = (1 + Rd,USD)F − 1`.
- `WACC,local = (1−d)Re,local + d Rd,local(1−τ)`.

**Why local WACC is recomputed:** The same F is applied to gross equity and **pretax** borrowing rates. Because tax deductions apply to nominal local-currency interest, converting the USD WACC directly by F is not generally equivalent when debt and taxes are nonzero.

## Assumptions and caveats

- Risk is benchmarked to the **U.S. market**, not a global market or the investor's personal portfolio.
- U.S. industry betas proxy for project operating risk; no separate country equity risk premium is added.
- Debt and the tax shield have zero beta; the perpetual-debt tax shield is discounted at the borrowing rate.
- The tax rate is constant, deductions are fully and immediately usable, and leverage uses a target debt share (default 30%).
- Relative PPP/equal real rates are assumed to translate nominal required returns. This is a **modeling assumption**, not a guaranteed exchange-rate forecast.
- Government yields can reflect sovereign credit risk, liquidity and term premia. Especially for euro-area countries, a sovereign yield is not necessarily a euro risk-free yield.
- Credit spread is based on a large-firm BBB benchmark and may not describe the specific project or borrower.
- Inputs and source freshness must be checked; results are educational estimates, not investment advice.

## Troubleshooting

If source retrieval fails, enter verified rates and beta manually in the sidebar. If GitHub deployment fails, inspect the Streamlit logs for missing packages or upstream HTTP errors. The app uses no API keys or Streamlit secrets.
