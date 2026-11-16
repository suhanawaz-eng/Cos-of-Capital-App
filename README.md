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

## Data retrieval and verification safeguards (updated)

The app attempts both Trading Economics public bond-table URLs and parses multiple common table layouts. It attempts the Damodaran ratings table and accepts the BBB spread only if the large-firm column can be identified unambiguously. Websites may change or block automated access; **no API key is required, but access is not guaranteed**.

When a beta, government yield, or credit spread is unavailable, the sidebar shows an editable example value with a **required verification checkbox**. The app **does not display cost-of-capital results until every missing-source input is confirmed**. Corporate tax rates are **always manually verified** against the linked OECD reference because the report is not a live country-rate API. Check the applicable jurisdiction and year. Source diagnostics are displayed if the app cannot calculate.

Source retrieval timestamps record when a page was fetched, not necessarily when the underlying observation was published. A confirmed manual entry is not independently verified by the application. For real financial decisions, independently check all inputs, including any edits to automatically populated fields.


## Revised fallback behavior (November 2026)

The app does not block calculations when public websites fail to return machine-readable data. It displays a prominent **Illustrative results only** warning and labels each manually supplied rate. Default 4% government yields, 2% spread, and 25% tax are **starting assumptions, not verified market data**. Replace them with verified values for a decision. Source diagnostics remain available.

Trading Economics' public HTML layout can change or block automated requests; no-API-key access is not a guarantee of machine-readable data. Damodaran's ratings table can also change. The app intentionally avoids guessing a credit spread from an unlabeled column.

## November 2026 data-retrieval revision

- Trading Economics: the app first parses the public 10-year bond **country list** by its actual `Country`/`Last` columns, then tries an `lxml` table parser. No API key is required. An inaccessible or changed page triggers an explicitly marked manual input; it does **not** silently substitute a live value.
- Damodaran credit spread: the Baa2/BBB spread is read from the **left-hand, large non-financial firms** rating block. The two rating tables share an HTML table; a `large` label is not repeated in each column. The source analysis date (e.g. January 2026) is distinct from the page fetch date.
- OECD: the app attempts to extract a country-specific statutory tax rate only from a table that explicitly contains **country, year and statutory rate**. The OECD publications are not guaranteed to provide such a table in HTML; if not, the tax rate remains manual. The displayed fetch time is not the underlying tax year. For a production-grade automatic OECD rate for every country, a validated OECD SDMX dataset mapping is still required.
- All retrieved values remain editable. Results stay visible; manual assumptions/overrides are flagged, not blocked. Data status and diagnostics are collapsed by default.
- Public websites may change layouts, deny automated requests, or impose usage restrictions. Check observation dates and source details before making decisions.

### Verification

The Python source was syntax-checked. Live network calls could not be exercised in the build environment, so automatic retrieval in the deployed Streamlit environment still requires validation. No source-derived rates have been hard-coded as live values.
