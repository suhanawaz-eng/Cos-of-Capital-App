# Cost of Capital — Streamlit (Version 6)

Compare project cost of equity, pretax and after-tax debt, and WACC in USD and a selected country's currency using the same formulas and assumptions as previous versions.

## Deploy

1. Upload `app.py`, `requirements.txt`, and this `README.md` to the root of a GitHub repository.
2. In Streamlit Community Cloud, deploy `app.py` from the repository.
3. Allow outbound HTTPS connections. No API key is required for the public pages used.

## Data retrieval (Version 6)

- **Industry unlevered beta:** Damodaran industry XLS with HTML fallback.
- **Baa2/BBB spread:** Damodaran large nonfinancial firm ratings table.
- **10-year government yields:** Trading Economics public country table; if unavailable, CountryEconomy 10-year table; FRED series `DGS10` and `COLIRLTLT01STM` for US and Colombia; saved last successful observations where writable. A **dated November 2026 reference snapshot** (US 5.13%, Colombia 12.70%) is the final built-in fallback for these two countries, **not a live quote**. The interface labels snapshots and cached observations explicitly. Other countries without a source observation retain editable manual assumptions.
- **Corporate tax:** OECD statutory corporate income tax API (SDMX), with Colombia 2026 rate of 35% from the published OECD report as a fallback. When an OECD rate is not reliably retrieved, the app uses an editable manual assumption, not a fabricated source observation.

Web sources can restrict automated requests, change markup, or time out. Successful retrieval is not guaranteed. The local last-successful cache is best effort and may not persist on Streamlit Community Cloud restarts. The app shows data provenance and observation/reference dates when known, and keeps calculations visible as illustrative when inputs are unverified. Retrieval timestamps are **not** observation dates.

## Model

- Perpetual constant debt, fully usable interest tax shield, zero debt and tax-shield beta.
- Debt/equity `D/E = d/(1-d)`; relevered equity beta `βE = βU × [1+(1−τ)D/E]`.
- USD cost of equity `Re = Rf_US + βE × ERP_US`; USD pretax debt `Rd = Rf_US + spread`.
- `WACC_US = (1−d)Re + d Rd(1−τ)`.
- Gross currency factor `F = (1+Rf_local)/(1+Rf_US)`; local `Re = (1+Re_US)F−1`; local `Rd = (1+Rd_US)F−1`; local WACC recomputed from local nominal equity/debt rates.
- No separate country equity premium; U.S. market risk benchmark; equal real rates / relative PPP approximation. Sovereign, term, and liquidity premia can affect government yields.

## Notes

The app is a research and education tool. Verify tax applicability, observation dates, yield currency/tenor, and source licensing before financial decisions. A country bond yield is not always a pure default-free risk-free rate. Changing a sidebar input is a manual override.

## Source links

- https://pages.stern.nyu.edu/~adamodar/pc/datasets/betas.xls
- https://pages.stern.nyu.edu/adamodar/New_Home_Page/datafile/ratings.html
- https://tradingeconomics.com/country-list/government-bond-10y
- https://countryeconomy.com/bonds
- https://fred.stlouisfed.org/series/DGS10
- https://fred.stlouisfed.org/series/COLIRLTLT01STM
- https://www.oecd.org/en/publications/corporate-tax-statistics-2026_73af6222-en/full-report/statutory-corporate-income-tax-rates_ce84abb9.html
