"""Cost of Capital — USD vs selected local currency (Streamlit)."""
from datetime import datetime, timezone, date
from urllib.parse import quote
from io import BytesIO, StringIO
import re
import html
import unicodedata
from bs4 import BeautifulSoup

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
OECD = "https://www.oecd.org/en/publications/corporate-tax-statistics-2025_6a915941-en/full-report/component-6.html"
OECD_2024 = "https://www.oecd.org/en/publications/corporate-tax-statistics-2024_9c27d6e8-en/full-report/statutory-corporate-income-tax-rates_440f9286.html"


OECD_DATA_API = "https://sdmx.oecd.org/public/rest/data/OECD.CTP.TPS,DSD_TAX_CIT@DF_CIT,2.0/.A..ST..S13...?startPeriod=2023&dimensionAtObservation=AllDimensions&format=csvfile"
OECD_2026_REPORT = "https://www.oecd.org/en/publications/corporate-tax-statistics-2026_73af6222-en/full-report/statutory-corporate-income-tax-rates_ce84abb9.html"
FRED_US = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10"
FRED_CO = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=COLIRLTLT01STM"
COUNTRY_ISO = {"Colombia":"COL","United States":"USA","Australia":"AUS","Austria":"AUT","Belgium":"BEL","Brazil":"BRA","Canada":"CAN","Chile":"CHL","China":"CHN","Czech Republic":"CZE","Denmark":"DNK","Finland":"FIN","France":"FRA","Germany":"DEU","Greece":"GRC","Hungary":"HUN","India":"IND","Indonesia":"IDN","Ireland":"IRL","Israel":"ISR","Italy":"ITA","Japan":"JPN","Mexico":"MEX","Netherlands":"NLD","New Zealand":"NZL","Norway":"NOR","Peru":"PER","Poland":"POL","Portugal":"PRT","South Korea":"KOR","Spain":"ESP","Sweden":"SWE","Switzerland":"CHE","Turkey":"TUR","Türkiye":"TUR","United Kingdom":"GBR","South Africa":"ZAF","Singapore":"SGP","Malaysia":"MYS","Thailand":"THA"}

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


def _as_tables(page):
    # StringIO avoids the optional html5lib parser dependency path used by some
    # pandas/BeautifulSoup versions when given a byte buffer.
    return pd.read_html(StringIO(page), flavor="lxml")


def parse_yield_tables(tables):
    """Only accept named country + 'Last' columns, never unrelated indicators."""
    output = {}
    for raw in tables:
        for t in table_variants(raw):
            heads = [norm(c) for c in t.columns]
            ci = next((i for i, h in enumerate(heads) if h in {"country", "country name"}), None)
            yi = next((i for i, h in enumerate(heads) if h in {"last", "yield", "yield percent", "10y", "10 year yield"}), None)
            if ci is None or yi is None:
                continue
            for row in t.itertuples(index=False, name=None):
                name = str(row[ci]).strip()
                if name not in CURRENCIES and name not in {"Hong Kong", "Taiwan", "Kenya", "Nigeria", "Russia", "Zambia"}:
                    continue
                try:
                    val = numeric(row[yi])
                except (ValueError, TypeError):
                    continue
                if pd.notna(val) and -5 < val < 75:
                    output[name] = float(val)
    return output


def parse_yield_html(page):
    """Extract only explicit country + 10-year yield rows from public tables.

    Avoid arbitrary page numbers, forecast values, and unrelated bond maturities.
    """
    soup = BeautifulSoup(page, "html.parser")
    out = {}
    for table in soup.select("table"):
        rows = table.select("tr")
        header = []
        for row in rows[:8]:
            cells = row.find_all(["th", "td"], recursive=False)
            vals = [norm(c.get_text(" ", strip=True)) for c in cells]
            if "country" in vals and "last" in vals:
                header = vals
                break
        if not header:
            continue
        ci, yi = header.index("country"), header.index("last")
        for row in rows:
            cells = row.find_all(["td", "th"], recursive=False)
            if len(cells) <= max(ci, yi):
                continue
            name = cells[ci].get_text(" ", strip=True)
            if name not in CURRENCIES:
                continue
            try:
                val = numeric(cells[yi].get_text(" ", strip=True))
                if -5 < val < 75:
                    out[name] = val
            except (TypeError, ValueError):
                continue
    return out


def parse_te_reference_dates(page):
    """Read the country table's Reference column, if provided."""
    soup = BeautifulSoup(page, "html.parser")
    dates = {}
    for table in soup.select("table"):
        for row in table.select("tr"):
            cells = row.find_all(["th", "td"], recursive=False)
            values = [c.get_text(" ", strip=True) for c in cells]
            if len(values) >= 4 and values[0] in CURRENCIES and re.fullmatch(r"[A-Za-z]{3}/\d{2,4}", values[3]):
                dates[values[0]] = values[3]
    return dates


def parse_fred_csv(content, series_id):
    frame = pd.read_csv(StringIO(content))
    if series_id not in frame.columns or frame.empty:
        raise ValueError(f"FRED series {series_id} missing")
    date_col = frame.columns[0]
    values = pd.to_numeric(frame[series_id], errors="coerce")
    dates = pd.to_datetime(frame[date_col], errors="coerce")
    good = pd.DataFrame({"date": dates, "yield": values}).dropna().sort_values("date")
    good = good[(good["yield"] > -5) & (good["yield"] < 75)]
    if good.empty:
        raise ValueError(f"FRED series {series_id} has no valid observations")
    latest = good.iloc[-1]
    return float(latest["yield"]), latest["date"].date().isoformat()


@st.cache_data(ttl=3600, show_spinner=False)
def load_yields():
    """Trading Economics public table first; independent FRED fallback for US/CO.

    Return observation date when known; never confuse retrieval time with it.
    """
    errors = []
    values, meta = {}, {}
    checked = datetime.now(timezone.utc).isoformat(timespec="minutes")
    for url in (BONDS, BONDS_ALT):
        try:
            page = get(url).text
            parsed = parse_yield_html(page)
            if len(parsed) < 5:
                parsed.update(parse_yield_tables(_as_tables(page)))
            if parsed:
                reference_dates = parse_te_reference_dates(page)
                for name, val in parsed.items():
                    values[name] = val
                    meta[name] = {"source":"Trading Economics", "observed":reference_dates.get(name, "See source reference column"), "url":url, "retrieved":checked}
                break
            errors.append(f"{url}: no country/yield table found")
        except Exception as e:
            errors.append(f"{url}: {type(e).__name__}: {e}")
    for name, series, url in (("United States", "DGS10", FRED_US), ("Colombia", "COLIRLTLT01STM", FRED_CO)):
        if name in values:
            continue
        try:
            value, observed = parse_fred_csv(get(url).text, series)
            values[name] = value
            meta[name] = {"source":f"FRED ({series}; US Treasury/OECD)", "observed":observed, "url":url, "retrieved":checked}
        except Exception as e:
            errors.append(f"FRED {series}: {type(e).__name__}: {e}")
    return values, meta, checked, "; ".join(errors) or None


def parse_credit_spread_html(page):
    """The left-hand four columns are the large nonfinancial firms table.

    The current source has two adjacent ratings tables; 'large' is a heading
    spanning columns, not a label on the actual spread column.
    """
    soup = BeautifulSoup(page, "html.parser")
    for table in soup.find_all("table"):
        content = norm(table.get_text(" ", strip=True))
        if "large non financial service firms" not in content or "financial service firms" not in content:
            continue
        for tr in table.find_all("tr"):
            cells = tr.find_all(["td", "th"], recursive=False)
            vals = [c.get_text(" ", strip=True) for c in cells]
            if len(vals) < 4:
                continue
            # Rating is the third column and spread the fourth in the left block.
            if norm(vals[2]) == "baa2 bbb":
                v = numeric(vals[3])
                if 0 <= v <= 25:
                    return v
    # Fallback: some HTML parsers separate the heading from the data table.
    for t in _as_tables(page):
        for row in t.itertuples(index=False, name=None):
            vals = [str(v) for v in row]
            for i, v in enumerate(vals):
                if norm(v) == "baa2 bbb" and i >= 2 and i + 1 < len(vals):
                    spread = numeric(vals[i + 1])
                    if 0 <= spread <= 25 and i == 2:
                        return spread
    raise ValueError("Baa2/BBB row in the large nonfinancial firm columns not found")


@st.cache_data(ttl=86400, show_spinner=False)
def load_credit_spread():
    try:
        value = parse_credit_spread_html(get(RATINGS).text)
        return value, "Damodaran Baa2/BBB (large nonfinancial firms)", datetime.now(timezone.utc).isoformat(timespec="minutes")
    except Exception as e:
        return None, f"{type(e).__name__}: {e}", None


def parse_oecd_csv(content):
    """OECD SDMX statutory combined general-government CIT rates only.

    Reject small-business, subcentral-only, effective, and other measures.
    """
    frame = pd.read_csv(StringIO(content), low_memory=False)
    if frame.empty:
        return {}
    cols = {norm(c).replace(" ", "_"): c for c in frame.columns}
    def col(*names):
        for name in names:
            if name in cols:
                return cols[name]
        return None
    area = col("ref_area", "reference_area")
    period = col("time_period")
    value = col("obs_value", "observation_value")
    targeting = col("targeting")
    sector = col("institutional_sector")
    freq = col("freq", "frequency_of_observation")
    measure = col("measure")
    if not all((area, period, value, targeting, sector, freq, measure)):
        raise ValueError("OECD CSV missing required SDMX dimensions")
    t = frame.copy()
    for c, allowed in ((targeting,{"ST","STATUTORY"}), (sector,{"S13","GENERAL GOVERNMENT"}), (freq,{"A","ANNUAL"})):
        t = t[t[c].astype(str).str.upper().isin(allowed)]
    # Dataset 2.0: measure code is blank for combined rates, as in the OECD
    # query .A..ST..S13... . Reject named measures not indicating combined CIT.
    t = t[t[measure].isna() | t[measure].astype(str).str.strip().isin(["", "CIT_C", "COMBINED", "Combined corporate income tax rate"])]
    if t.empty:
        return {}
    t["_year"] = pd.to_numeric(t[period], errors="coerce")
    t["_value"] = pd.to_numeric(t[value], errors="coerce")
    t = t[(t["_year"] >= 2020) & (t["_year"] <= datetime.now().year) & t["_value"].between(0,60)]
    reverse = {v:k for k,v in COUNTRY_ISO.items()}
    out = {}
    for code, group in t.groupby(area):
        name = reverse.get(str(code).upper())
        if not name:
            continue
        latest = group.sort_values("_year").iloc[-1]
        # A unique statutory combined rate must exist for this country/year.
        matches = group[group["_year"] == latest["_year"]]["_value"].unique()
        if len(matches) == 1:
            out[name] = (float(latest["_value"]), int(latest["_year"]))
    return out


@st.cache_data(ttl=86400, show_spinner=False)
def load_oecd_taxes():
    checked = datetime.now(timezone.utc).isoformat(timespec="minutes")
    errors = []
    try:
        records = parse_oecd_csv(get(OECD_DATA_API).text)
        if records:
            return records, "OECD SDMX statutory combined CIT API", checked, None
        errors.append("OECD API: no unambiguous statutory combined country rates")
    except Exception as e:
        errors.append(f"OECD API: {type(e).__name__}: {e}")
    # Verified 2026 OECD report country-specific fallback. Not a generic
    # inferred rate for other countries; other missing rates stay manual.
    return {"Colombia": (35.0, 2026)}, "OECD Corporate Tax Statistics 2026 (published report; Colombia only)", checked, "; ".join(errors)


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
    yields, yield_meta, yield_time, yield_error = load_yields()
    spread_auto, spread_source, spread_time = load_credit_spread()
    taxes, tax_source, tax_time, tax_error = load_oecd_taxes()

with st.sidebar:
    st.header("Project assumptions")
    countries = sorted(set(CURRENCIES) | set(yields))
    country = st.selectbox("Project country", countries, index=countries.index("Colombia") if "Colombia" in countries else 0)
    currency = CURRENCIES.get(country, "") or st.text_input("Local currency ISO code", value="").strip().upper()
    st.caption(f"Project currency: {currency or 'Not specified'}")
    industry = st.selectbox("U.S. industry", betas["Industry"].tolist() if not betas.empty else ["Manual beta"], disabled=betas.empty)
    suggested_beta = float(betas.set_index("Industry").loc[industry, "Unlevered beta"]) if not betas.empty else 1.0
    beta_u = st.number_input("Unlevered industry beta", min_value=0.01, max_value=10.0, value=suggested_beta, step=0.05, format="%.3f")
    st.caption("Damodaran industry beta" if not betas.empty else "Beta unavailable; using editable manual assumption")

    st.markdown("**Financing and taxes**")
    debt_pct = st.slider("Target debt share (D / [D + E])", 0, 95, 30)
    tax_entry = taxes.get(country)
    tax_default = float(tax_entry[0]) if tax_entry else 25.0
    tax_pct = st.number_input("Corporate tax rate (%)", min_value=0.0, max_value=100.0, value=tax_default, step=0.5, key=f"tax_{country}_{tax_default}")
    tax_edited = abs(tax_pct - tax_default) > 1e-9
    st.caption((f"OECD statutory rate for {tax_entry[1]}" if tax_entry else "Manual starting assumption — OECD country rate unavailable") + (" · overridden" if tax_edited else ""))
    erp_pct = st.number_input("U.S. equity risk premium (%)", min_value=0.0, max_value=50.0, value=6.5, step=0.1)

    st.markdown("**10-year government yields (%)**")
    us_candidates = [v for k, v in yields.items() if norm(k) in {"united states", "usa", "united states 10y"}]
    local_candidates = [v for k, v in yields.items() if norm(k) == norm(country)]
    us_auto = us_candidates[0] if us_candidates else None
    local_auto = local_candidates[0] if local_candidates else (us_auto if country == "United States" else None)
    rf_us_pct = st.number_input("U.S. 10-year yield", min_value=-10.0, max_value=100.0, value=float(us_auto) if us_auto is not None else 4.0, step=0.05, format="%.3f", key=f"us_yield_{us_auto}")
    st.caption((f"{yield_meta['United States']['source']} · observation: {yield_meta['United States']['observed']} · checked: {yield_time}" if us_auto is not None else "Manual starting assumption: 4.0% — NOT verified"))
    rf_local_pct = st.number_input(f"{country} 10-year yield", min_value=-10.0, max_value=100.0, value=float(local_auto) if local_auto is not None else 4.0, step=0.05, format="%.3f", key=f"local_yield_{country}_{local_auto}")
    st.caption((f"{yield_meta[country]['source']} · observation: {yield_meta[country]['observed']} · checked: {yield_time}" if country in yield_meta else "Manual starting assumption: 4.0% — NOT verified"))

    st.markdown("**Credit spread (%)**")
    spread_pct = st.number_input("Baa2/BBB large-firm USD spread", min_value=0.0, max_value=25.0, value=float(spread_auto) if spread_auto is not None else 2.0, step=0.05, format="%.3f", key=f"spread_{spread_auto}")
    st.caption("Damodaran · source checked " + str(spread_time) if spread_auto is not None else "Manual starting assumption: 2.0% — NOT verified")
    st.markdown("[Trading Economics bonds](https://tradingeconomics.com/bonds) · [Damodaran spread](https://pages.stern.nyu.edu/adamodar/New_Home_Page/datafile/ratings.html) · [OECD tax reference](https://www.oecd.org/en/publications/corporate-tax-statistics-2024_9c27d6e8-en/full-report/statutory-corporate-income-tax-rates_440f9286.html)")

if not currency:
    st.error("Specify a local currency code to continue.")
    st.stop()

st.subheader("Results")
with st.expander("Data status and retrieval diagnostics", expanded=False):
    def origin(value, auto, label):
        return label if auto is not None and abs(value-auto) < 1e-9 else ("Manual override" if auto is not None else "Manual assumption (unverified)")
    checks = {
        "Industry beta": origin(beta_u, suggested_beta if not betas.empty else None, "Damodaran"),
        "Corporate tax rate": origin(tax_pct, tax_default if tax_entry else None, f"OECD {tax_entry[1]}" if tax_entry else ""),
        "U.S. 10-year yield": origin(rf_us_pct, us_auto, yield_meta.get("United States",{}).get("source","Market data")),
        f"{country} 10-year yield": origin(rf_local_pct, local_auto, yield_meta.get(country,{}).get("source","Market data")),
        "Baa2/BBB spread": origin(spread_pct, spread_auto, "Damodaran"),
    }
    st.dataframe(pd.DataFrame([{"Input": k, "Data origin": v} for k,v in checks.items()]), hide_index=True, use_container_width=True)
    st.caption(f"Industry beta checked: {beta_time or 'unavailable'} · Bond yields checked: {yield_time or 'unavailable'} · Credit spread checked: {spread_time or 'unavailable'} · OECD checked: {tax_time or 'unavailable'} (UTC)")
    st.write("Bond yields:", yield_error or "Source data retrieved")
    for name in ("United States",country):
        if name in yield_meta:
            m = yield_meta[name]
            st.write(f"{name}: {m['source']} · observation {m['observed']} · retrieved {m['retrieved']} UTC · {m['url']}")
    st.write("Credit spread:", spread_source)
    st.write("OECD tax rates:", tax_error or tax_source)
    st.write("Industry beta:", beta_source)
missing = [k for k,v in checks.items() if "Manual" in v]
if missing:
    st.warning("**Illustrative results:** Manual inputs require independent verification: " + ", ".join(missing) + ".")

r = calculate(beta_u, tax_pct/100, debt_pct/100, erp_pct/100, rf_us_pct/100, rf_local_pct/100, spread_pct/100)
if country == "United States" and abs(rf_local_pct-rf_us_pct)>1e-8:
    st.warning("The local and U.S. currencies are both USD; use identical yields for a meaningful comparison.")
if currency == "EUR":
    st.info("For EUR projects, sovereign bond yields may differ across euro-area countries. Verify the appropriate EUR risk-free proxy.")

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
    st.markdown(f"- [Trading Economics 10-year bond yields]({BONDS_ALT}) (public table) and [FRED]({FRED_CO}) (fallback for US/Colombia); checked {yield_time or 'unavailable'}. Observation dates appear in the sidebar when available.")
    st.markdown(f"- [OECD statutory CIT dataset]({OECD_DATA_API}) / [OECD 2026 report]({OECD_2026_REPORT}) — {tax_source}; checked: {tax_time or 'unavailable'}. Other countries without validated rates use manual inputs.")
    st.markdown("**Model:** U.S. market beta and 6.5% default U.S. ERP; no additional country equity premium. Assumes debt and tax-shield beta are zero, perpetual debt and fully usable tax deductions, target debt share, and equal real interest rates/relative PPP. Sovereign yields may contain liquidity, term and default premia. 10-year yields are used as proxies and do not guarantee matching project duration. Credit spread is applied in USD before conversion. No claim of exact forward FX rates or no-arbitrage pricing.")
    st.markdown("**Verification:** Results remain visible as illustrative calculations when some inputs are manual. Manually entered values and edits to retrieved inputs are not independently verified; check them before use.\n\n**Freshness:** The timestamps reflect when this app retrieved a web page, not necessarily when its underlying data was last updated. Confirm reference dates at each source. Manual overrides are not independently verified.")

csv = result.to_csv(index=False).encode("utf-8")
st.download_button("Download comparison (CSV)", data=csv, file_name="cost_of_capital_comparison.csv", mime="text/csv")
