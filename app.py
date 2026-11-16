"""Cost of Capital — USD vs selected local currency (Streamlit)."""
from datetime import datetime, timezone
from io import BytesIO
import re
import unicodedata

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

st.set_page_config(page_title="Cost of Capital | USD vs Local", page_icon="📈", layout="wide")

BETA_XLS = "https://pages.stern.nyu.edu/~adamodar/pc/datasets/betas.xls"
BETA_HTML = "https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/Betas.html"
RATINGS = "https://pages.stern.nyu.edu/adamodar/New_Home_Page/datafile/ratings.html"
BONDS = "https://tradingeconomics.com/country-list/government-bond-10y"
BONDS_ALT = "https://tradingeconomics.com/bonds"
OECD = "https://www.oecd.org/en/publications/corporate-tax-statistics-2024_9c27d6e8-en/full-report/statutory-corporate-income-tax-rates_440f9286.html"

# Currency is the primary circulating currency; countries with multiple legal currencies
# or unusual bond denominations require manual verification.
CURRENCIES = {
    "Australia": "AUD", "Austria": "EUR", "Belgium": "EUR", "Brazil": "BRL",
    "Bulgaria": "EUR", "Canada": "CAD", "Chile": "CLP", "China": "CNY",
    "Colombia": "COP", "Croatia": "EUR", "Czech Republic": "CZK",
    "Denmark": "DKK", "Egypt": "EGP", "Euro area": "EUR", "Finland": "EUR",
    "France": "EUR", "Germany": "EUR", "Greece": "EUR", "Hungary": "HUF",
    "India": "INR", "Indonesia": "IDR", "Ireland": "EUR", "Israel": "ILS",
    "Italy": "EUR", "Japan": "JPY", "Malaysia": "MYR", "Mexico": "MXN",
    "Netherlands": "EUR", "New Zealand": "NZD", "Norway": "NOK",
    "Pakistan": "PKR", "Peru": "PEN", "Philippines": "PHP", "Poland": "PLN",
    "Portugal": "EUR", "Romania": "RON", "Saudi Arabia": "SAR",
    "Singapore": "SGD", "South Africa": "ZAR", "South Korea": "KRW",
    "Spain": "EUR", "Sweden": "SEK", "Switzerland": "CHF",
    "Thailand": "THB", "Turkey": "TRY", "Türkiye": "TRY",
    "United Kingdom": "GBP", "United States": "USD", "Vietnam": "VND",
}


def norm(value):
    s = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def get(url):
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (compatible; CostOfCapitalResearch/1.0)"}, timeout=18)
    response.raise_for_status()
    return response


def numeric(x):
    if isinstance(x, (float, int)):
        return float(x)
    t = str(x).strip().replace(",", "").replace("%", "")
    return float(t) if t and t.lower() not in {"nan", "na", "none", "-"} else float("nan")


def find_beta_table(tables):
    for raw in tables:
        for frame in (raw, raw.copy()):
            frame.columns = [str(c).strip() for c in frame.columns]
            cols = list(frame.columns)
            matches = [c for c in cols if norm(c) == "unlevered beta"]
            if not matches:
                # Excel sheets frequently include several preamble rows.
                for idx in range(min(20, len(frame))):
                    vals = [norm(x) for x in frame.iloc[idx].tolist()]
                    if "unlevered beta" in vals:
                        frame = frame.iloc[idx + 1:].copy()
                        frame.columns = [str(x).strip() for x in raw.iloc[idx].tolist()]
                        break
                matches = [c for c in frame.columns if norm(c) == "unlevered beta"]
            if matches:
                industry_col = next((c for c in frame.columns if norm(c) == "industry name"), frame.columns[0])
                out = pd.DataFrame({"Industry": frame[industry_col].astype(str).str.strip(),
                                    "Unlevered beta": pd.to_numeric(frame[matches[0]], errors="coerce")})
                out = out[(out["Unlevered beta"] > 0) & (out["Unlevered beta"] < 10)]
                out = out[~out["Industry"].str.contains("total market|total firms|average", case=False, na=False)]
                out = out.drop_duplicates("Industry").sort_values("Industry")
                if len(out) > 10:
                    return out.reset_index(drop=True)
    raise ValueError("Unlevered beta column could not be identified in source")


@st.cache_data(ttl=86400, show_spinner=False)
def load_betas():
    errors = []
    try:
        raw = get(BETA_XLS).content
        # Read as raw rows so metadata/preamble rows are handled consistently.
        frame = pd.read_excel(BytesIO(raw), header=None, engine="xlrd")
        return find_beta_table([frame]), "Damodaran XLS", datetime.now(timezone.utc).isoformat(timespec="minutes")
    except Exception as e:
        errors.append(f"XLS: {e}")
    try:
        tables = pd.read_html(BytesIO(get(BETA_HTML).content))
        return find_beta_table(tables), "Damodaran HTML fallback", datetime.now(timezone.utc).isoformat(timespec="minutes")
    except Exception as e:
        errors.append(f"HTML: {e}")
    return pd.DataFrame(columns=["Industry", "Unlevered beta"]), "; ".join(errors), None


def flatten_table(raw):
    """Flatten multi-level HTML headings and promote embedded header rows."""
    t = raw.copy()
    if isinstance(t.columns, pd.MultiIndex):
        t.columns = [" ".join(str(x) for x in col if not str(x).startswith("Unnamed")) for col in t.columns]
    else:
        t.columns = [str(c) for c in t.columns]
    return t


def table_variants(raw):
    t = flatten_table(raw)
    yield t
    for i in range(min(7, len(t))):
        row = [str(v) for v in t.iloc[i].tolist()]
        if any("country" in norm(v) or "rating" in norm(v) or "spread" in norm(v) for v in row):
            promoted = t.iloc[i + 1:].copy()
            promoted.columns = row
            yield promoted


def parse_yield_tables(tables):
    result = {}
    for raw in tables:
        for t in table_variants(raw):
            headers = [norm(c) for c in t.columns]
            ci = next((i for i, h in enumerate(headers) if h in {"country", "country name", "name"} or h.startswith("country ")), None)
            yi = next((i for i, h in enumerate(headers) if h in {"last", "yield", "yield percent", "last percent", "10y", "10 year", "10 year yield"} or h.startswith("last ")), None)
            if ci is None or yi is None:
                continue
            for row in t.itertuples(index=False, name=None):
                name = str(row[ci]).strip()
                try:
                    val = numeric(row[yi])
                except (ValueError, TypeError):
                    continue
                if name and pd.notna(val) and -10 < val < 100:
                    result[name] = val
    return result


@st.cache_data(ttl=3600, show_spinner=False)
def load_yields():
    errors = []
    for url in (BONDS, BONDS_ALT):
        try:
            tables = pd.read_html(BytesIO(get(url).content))
            output = parse_yield_tables(tables)
            if len(output) >= 5:
                return output, url, datetime.now(timezone.utc).isoformat(timespec="minutes"), None
            errors.append(f"{url}: recognized {len(output)} yields")
        except Exception as e:
            errors.append(f"{url}: {type(e).__name__}: {e}")
    return {}, None, None, "; ".join(errors)


def parse_credit_spread(tables):
    """Read only a clearly labeled large-firm Baa2/BBB spread, never a guessed column."""
    for raw in tables:
        for t in table_variants(raw):
            headers = [norm(c) for c in t.columns]
            # In Damodaran's ratings table, the large-firm spread is typically
            # the final 'Spread is' column, but positional inference is unsafe.
            large = [i for i, h in enumerate(headers) if "large" in h and ("spread" in h or "firm" in h)]
            explicit = [i for i, h in enumerate(headers) if "spread" in h and ("large" in h or "financial service" in h)]
            indices = list(dict.fromkeys(explicit or large))
            # Headers sometimes split across rows: use nearby header text to
            # establish which spread is large-firm, never an arbitrary number.
            if len(indices) != 1:
                continue
            idx = indices[0]
            for row in t.itertuples(index=False, name=None):
                if not any(re.search(r"\bBaa2\s*/\s*BBB\b", str(x), re.I) for x in row):
                    continue
                try:
                    value = numeric(row[idx])
                except (ValueError, TypeError):
                    continue
                if pd.notna(value) and 0 <= value <= 25:
                    return value
    raise ValueError("No unambiguous Baa2/BBB large-firm spread header/row found")


@st.cache_data(ttl=86400, show_spinner=False)
def load_credit_spread():
    try:
        tables = pd.read_html(BytesIO(get(RATINGS).content))
        value = parse_credit_spread(tables)
        return value, "Damodaran Baa2/BBB (large firms)", datetime.now(timezone.utc).isoformat(timespec="minutes")
    except Exception as e:
        return None, f"{type(e).__name__}: {e}", None


def calculate(beta_u, tax, debt_share, erp, rf_us, rf_local, spread):
    """Rates as decimals; currency conversion via gross-yield ratio."""
    de = debt_share / (1 - debt_share)
    beta_e = beta_u * (1 + (1 - tax) * de)
    re_us = rf_us + beta_e * erp
    rd_us = rf_us + spread
    wacc_us = (1 - debt_share) * re_us + debt_share * rd_us * (1 - tax)
    factor = (1 + rf_local) / (1 + rf_us)
    # Currency conversion of all nominal required returns on gross-rate basis.
    re_local = (1 + re_us) * factor - 1
    rd_local = (1 + rd_us) * factor - 1
    wacc_local = (1 - debt_share) * re_local + debt_share * rd_local * (1 - tax)
    # Direct gross conversion of USD WACC differs when debt tax shields are
    # converted: the tax shield is based on nominal LOCAL interest deductions.
    return dict(de=de, beta_e=beta_e, factor=factor, re_us=re_us, rd_us=rd_us,
                wacc_us=wacc_us, re_local=re_local, rd_local=rd_local,
                wacc_local=wacc_local, wacc_local_direct=(1 + wacc_us) * factor - 1)


st.title("Cost of Capital")
st.caption("U.S.-market CAPM benchmark • USD vs selected local currency • perpetual-debt tax shield")
with st.spinner("Checking public sources…"):
    betas, beta_source, beta_time = load_betas()
    yields, yield_source, yield_time, yield_error = load_yields()
    spread_auto, spread_source, spread_time = load_credit_spread()

with st.sidebar:
    st.header("Project assumptions")
    countries = sorted(set(CURRENCIES) | set(yields))
    country = st.selectbox("Project country", countries, index=countries.index("Colombia") if "Colombia" in countries else 0)
    currency = CURRENCIES.get(country, "")
    if not currency:
        currency = st.text_input("Local currency ISO code", value="").strip().upper()
    st.caption(f"Project currency: {currency or 'Not specified'}")
    industry = st.selectbox("U.S. industry", betas["Industry"].tolist() if not betas.empty else ["Manual beta"], disabled=betas.empty)
    suggested_beta = float(betas.set_index("Industry").loc[industry, "Unlevered beta"]) if not betas.empty else 1.0
    beta_u = st.number_input("Unlevered industry beta", min_value=0.01, max_value=10.0, value=suggested_beta, step=0.05, format="%.3f")
    beta_confirm = True if not betas.empty else st.checkbox("I verified the manually entered unlevered beta")
    st.caption("Beta: " + ("Retrieved from Damodaran; editable" if not betas.empty else "Manual entry — confirmation required"))

    st.markdown("**Financing and taxes**")
    debt_pct = st.slider("Target debt share (D / [D + E])", 0, 95, 30)
    tax_pct = st.number_input("Corporate tax rate (%)", min_value=0.0, max_value=100.0, value=25.0, step=0.5)
    tax_confirm = st.checkbox("I verified the corporate tax rate for this country and tax year")
    st.caption("Manual OECD-based assumption; 25% is NOT a retrieved tax rate.")
    erp_pct = st.number_input("U.S. equity risk premium (%)", min_value=0.0, max_value=50.0, value=6.5, step=0.1)

    st.markdown("**10-year government yields (%)**")
    us_candidates = [v for k, v in yields.items() if norm(k) in {"united states", "usa", "united states 10y"}]
    local_candidates = [v for k, v in yields.items() if norm(k) == norm(country)]
    us_auto = us_candidates[0] if us_candidates else None
    local_auto = local_candidates[0] if local_candidates else (us_auto if country == "United States" else None)
    rf_us_pct = st.number_input("U.S. 10-year yield", min_value=-10.0, max_value=100.0, value=float(us_auto) if us_auto is not None else 4.0, step=0.05, format="%.3f")
    us_confirm = True if us_auto is not None else st.checkbox("I verified the manually entered U.S. yield")
    st.caption("U.S. yield: " + ("Retrieved; editable" if us_auto is not None else "4% placeholder — verify and confirm"))
    rf_local_pct = st.number_input(f"{country} 10-year yield", min_value=-10.0, max_value=100.0, value=float(local_auto) if local_auto is not None else 4.0, step=0.05, format="%.3f")
    local_confirm = True if local_auto is not None else st.checkbox(f"I verified the manually entered {country} yield")
    st.caption("Local yield: " + ("Retrieved; editable" if local_auto is not None else "4% placeholder — verify and confirm"))

    st.markdown("**Credit spread (%)**")
    spread_pct = st.number_input("Baa2/BBB large-firm USD spread", min_value=0.0, max_value=25.0, value=float(spread_auto) if spread_auto is not None else 2.0, step=0.05, format="%.3f")
    spread_confirm = True if spread_auto is not None else st.checkbox("I verified the manually entered BBB spread")
    st.caption("Spread: " + ("Retrieved from Damodaran; editable" if spread_auto is not None else "2% placeholder — verify and confirm"))

if not currency:
    st.error("Specify a local currency code to continue.")
    st.stop()
if rf_us_pct <= -100 or rf_local_pct <= -100:
    st.error("Gross government yields must be positive.")
    st.stop()

st.subheader("Input verification")
checks = {
    "Industry beta": (beta_confirm, "Damodaran" if not betas.empty else "Manual"),
    "Corporate tax rate": (tax_confirm, "Manual OECD reference"),
    "U.S. 10-year yield": (us_confirm, "Trading Economics" if us_auto is not None else "Manual"),
    f"{country} 10-year yield": (local_confirm, "Trading Economics" if local_auto is not None else "Manual"),
    "Baa2/BBB spread": (spread_confirm, "Damodaran" if spread_auto is not None else "Manual"),
}
status = pd.DataFrame([{"Input": k, "Source": source, "Status": "Confirmed" if confirmed else "Needs verification"} for k, (confirmed, source) in checks.items()])
st.dataframe(status, hide_index=True, use_container_width=True)
if not all(v[0] for v in checks.values()):
    st.warning("Results are paused: confirm every manually supplied rate in the sidebar. Placeholder values are not verified market data.")
    with st.expander("Source retrieval diagnostics"):
        st.write("Bond yields:", yield_error or "Source parsed successfully; verify that both selected countries appear in its table.")
        st.write("Credit spread:", spread_source)
        st.write("Industry beta:", beta_source)
    st.stop()

r = calculate(beta_u, tax_pct/100, debt_pct/100, erp_pct/100, rf_us_pct/100, rf_local_pct/100, spread_pct/100)
if country == "United States" and abs(rf_local_pct-rf_us_pct)>1e-8:
    st.warning("The local and U.S. currencies are both USD; use identical yields for a meaningful comparison.")
if currency == "EUR":
    st.info("For EUR projects, sovereign bond yields may differ across euro-area countries. Verify the appropriate EUR risk-free proxy.")

st.subheader("Results")
a, b, c = st.columns(3)
a.metric("Relevered equity beta", f"{r['beta_e']:.3f}")
b.metric("Debt / equity", f"{r['de']:.3f}")
c.metric("Gross currency conversion factor (F)", f"{r['factor']:.4f}")

result = pd.DataFrame({
    "Metric": ["Cost of equity", "Pretax cost of debt", "After-tax cost of debt", "WACC"],
    "USD (%)": [r["re_us"]*100, r["rd_us"]*100, r["rd_us"]*(1-tax_pct/100)*100, r["wacc_us"]*100],
    f"{currency} (%)": [r["re_local"]*100, r["rd_local"]*100, r["rd_local"]*(1-tax_pct/100)*100, r["wacc_local"]*100]
})
st.dataframe(result.style.format({"USD (%)": "{:.2f}%", f"{currency} (%)": "{:.2f}%"}), hide_index=True, use_container_width=True)

fig = go.Figure()
for col in ["USD (%)", f"{currency} (%)"]:
    fig.add_trace(go.Bar(name=col, x=result["Metric"], y=result[col], text=[f"{v:.2f}%" for v in result[col]], textposition="outside"))
fig.update_layout(barmode="group", title="Cost of capital comparison", yaxis_title="Annual nominal rate (%)", legend_title="Currency", height=420, margin=dict(t=60,b=40))
st.plotly_chart(fig, use_container_width=True)

st.info("**Interpretation:** These are nominal required returns expressed in different currencies, not FX-converted cash amounts. Compare each discount rate only with cash flows in its matching currency.")

with st.expander("Calculation details and formulas", expanded=True):
    st.markdown(r"""
**Tax shield and beta (perpetual constant debt):**

- Annual interest deduction: $R_dD$
- Annual tax saving: $\\tau R_dD$
- $PV(\\text{tax shield})=\\frac{\\tau R_dD}{R_d}=\\tau D$
- $E+D=V_U+\\tau D$
- $E\\beta_E+D\\beta_D=V_U\\beta_U+\\tau D\\beta_{TS}$
- Assuming $\\beta_D=\\beta_{TS}=0$: $\\beta_U=\\frac{\\beta_E}{1+(1-\\tau)D/E}$
- $D/E=d/(1-d)$
- $\\beta_E=\\beta_U[1+(1-\\tau)D/E]$

**USD rates:**

- $R_{e,USD}=R_{f,USD}+\\beta_E ERP_{US}$
- $R_{d,USD}=R_{f,USD}+s_{BBB}$
- $WACC_{USD}=(1-d)R_{e,USD}+dR_{d,USD}(1-\\tau)$

**Local currency:**

- $F=\\frac{1+R_{f,local}}{1+R_{f,USD}}$
- $1+R_{e,local}=(1+R_{e,USD})F$
- $1+R_{d,local}=(1+R_{d,USD})F$
- $WACC_{local}=(1-d)R_{e,local}+dR_{d,local}(1-\\tau)$

Under the specified equal-real-rate/relative-PPP assumption, the **same F** converts gross equity and pretax debt rates. The local WACC is then **recomputed from local nominal rates** because the interest tax deduction applies to local nominal interest. Consequently, directly converting USD WACC with F is generally not equivalent when $d\\tau\\ne0$.
""".replace("\\\\", "\\"))
    st.write(f"USD WACC: {r['wacc_us']:.4%}; local WACC recomputed: {r['wacc_local']:.4%}; direct gross conversion of USD WACC (not used): {r['wacc_local_direct']:.4%}.")

with st.expander("Data sources, timestamps, and limitations"):
    st.markdown(f"- [Damodaran U.S. industry beta XLS]({BETA_XLS}) — {beta_source}; retrieved: {beta_time or 'unavailable'}")
    st.markdown(f"- [Damodaran Baa2/BBB spread]({RATINGS}) — {spread_source}; retrieved: {spread_time or 'unavailable'}")
    st.markdown(f"- [Trading Economics 10-year bond yields]({BONDS_ALT}) — retrieval: {yield_time or "unavailable"}; source: {yield_source or "unavailable"}; no API key used; public HTML parsing may be blocked or change.")
    st.markdown(f"- [OECD Corporate Tax Statistics 2024]({OECD}) — reference for **manually entered** statutory tax rate; not live or automatically mapped.")
    st.markdown("**Model:** U.S. market beta and 6.5% default U.S. ERP; no additional country equity premium. Assumes debt and tax-shield beta are zero, perpetual debt and fully usable tax deductions, target debt share, and equal real interest rates/relative PPP. Sovereign yields may contain liquidity, term and default premia. 10-year yields are used as proxies and do not guarantee matching project duration. Credit spread is applied in USD before conversion. No claim of exact forward FX rates or no-arbitrage pricing.")
    st.markdown("**Verification:** The results are shown only after any missing-source inputs and the manually entered tax rate have been explicitly confirmed. Edits to retrieved inputs should also be verified.\n\n**Freshness:** The timestamps reflect when this app retrieved a web page, not necessarily when its underlying data was last updated. Confirm reference dates at each source. Manual overrides are not independently verified.")

csv = result.to_csv(index=False).encode("utf-8")
st.download_button("Download comparison (CSV)", data=csv, file_name="cost_of_capital_comparison.csv", mime="text/csv")
