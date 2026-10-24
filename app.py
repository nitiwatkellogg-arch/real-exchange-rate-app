"""IMF monthly real exchange-rate explorer (Python 3.12)."""
from __future__ import annotations

from datetime import date
from io import StringIO
import re
import time

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pycountry
import requests
import streamlit as st

BASE = "https://api.imf.org/external/sdmx/3.0"
FIRST = pd.Period("1976-01", freq="M")
# ISO-3166 countries that are not IMF members, plus dependent territories that
# appear in pycountry. The IMF's current membership list can change.
NON_MEMBERS = {
    "CUB", "PRK", "TWN", "VAT", "PSE", "ESH", "ATA", "ATF", "BES", "BLM",
    "BMU", "BVT", "CCK", "COK", "CUW", "CXR", "CYM", "FLK", "FRO", "GIB",
    "GLP", "GRL", "GUF", "GUM", "HKG", "HMD", "IMN", "IOT", "JEY", "GGY",
    "MAC", "MAF", "MNP", "MSR", "MTQ", "MYT", "NCL", "NFK", "NIU", "PCN",
    "PRI", "PYF", "REU", "SGS", "SHN", "SJM", "SPM", "SXM", "TCA", "TKL",
    "UMI", "VGB", "VIR", "WLF", "ASM", "AIA", "ABW", "NRU", "TUV",
}
# Nauru and Tuvalu ARE IMF members; keep them available.
NON_MEMBERS -= {"NRU", "TUV"}
COUNTRIES = {c.alpha_3: c.name for c in pycountry.countries if c.alpha_3 not in NON_MEMBERS}
COUNTRIES["G163"] = "Euro area"
COUNTRIES["XKX"] = "Kosovo"
COUNTRIES = dict(sorted(COUNTRIES.items(), key=lambda x: x[1]))

st.set_page_config(page_title="IMF Real Exchange Rate Explorer", page_icon="🌐", layout="wide")
st.title("🌐 Real Exchange Rate Explorer")
st.caption("Monthly IMF data · January 1976 onward, where available · Python 3.12")


def parse_month(series: pd.Series) -> pd.Series:
    clean = series.astype(str).str.strip().str.replace(r"-M(\d\d)$", r"-\1", regex=True)
    return pd.to_datetime(clean, format="%Y-%m", errors="coerce")


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_series(country: str, indicator: str) -> pd.Series:
    """Fetch one country/indicator monthly series using the IMF SDMX 3.0 CSV API."""
    if indicator == "CPI":
        flow = "CPI"
        key = f"{country}.CPI._T.IX.M"
    else:
        flow = "ER"
        key = f"{country}.XDC_USD.PA_RT.M"

    url = f"{BASE}/data/dataflow/IMF.STA/{flow}/~/{key}"
    params = {"c[TIME_PERIOD]": "ge:1976-M01"}
    last_error = None
    for attempt in range(3):
        try:
            resp = requests.get(url, params=params, headers={"Accept": "text/csv"}, timeout=35)
            if resp.status_code in (204, 404):
                raise ValueError(f"No IMF {indicator} observations returned for {country} (HTTP {resp.status_code}).")
            resp.raise_for_status()
            if not resp.text.strip():
                raise ValueError(f"IMF returned an empty {indicator} response for {country}.")
            data = pd.read_csv(StringIO(resp.text), low_memory=False)
            data.columns = [str(c).strip().upper() for c in data.columns]
            if not {"TIME_PERIOD", "OBS_VALUE"}.issubset(data.columns):
                raise ValueError(f"Unexpected IMF {indicator} CSV columns: {list(data.columns)[:12]}")
            if "COUNTRY" in data.columns:
                data = data[data["COUNTRY"].astype(str).str.upper() == country]
            data = data.assign(month=parse_month(data["TIME_PERIOD"]))
            data["OBS_VALUE"] = pd.to_numeric(data["OBS_VALUE"], errors="coerce")
            data = data.dropna(subset=["month", "OBS_VALUE"])
            data = data[data["OBS_VALUE"] > 0]
            if data.empty:
                raise ValueError(f"No usable monthly {indicator} data for {country}.")
            # If revised observations appear twice, retain the last reported value.
            result = data.drop_duplicates("month", keep="last").set_index("month")["OBS_VALUE"].sort_index()
            result = result[result.index >= FIRST.to_timestamp()]
            if result.empty:
                raise ValueError(f"No usable {indicator} data since January 1976 for {country}.")
            result.name = f"{country}_{indicator}"
            return result
        except (requests.RequestException, pd.errors.ParserError) as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(1.5 * (attempt + 1))
        except ValueError:
            raise
    raise RuntimeError(f"IMF request failed for {country} {indicator}: {last_error}")


def build_frame(c1: str, c2: str) -> pd.DataFrame:
    p1 = fetch_series(c1, "CPI")
    p2 = fetch_series(c2, "CPI")
    # IMF series are units of local currency per USD; therefore:
    # (country2/USD) / (country1/USD) = country2/country1.
    # Same-currency pairs use S = 1 and need no FX series.
    if c1 == c2:
        df = pd.concat([p1.rename("P1_CPI"), p2.rename("P2_CPI")], axis=1)
        df["FX1_per_USD"] = np.nan
        df["FX2_per_USD"] = np.nan
        df["S_country2_per_country1"] = 1.0
    else:
        e1 = fetch_series(c1, "ER")
        e2 = fetch_series(c2, "ER")
        df = pd.concat([
            p1.rename("P1_CPI"), p2.rename("P2_CPI"),
            e1.rename("FX1_per_USD"), e2.rename("FX2_per_USD")
        ], axis=1)
        df["S_country2_per_country1"] = df["FX2_per_USD"] / df["FX1_per_USD"]
    df["RER"] = df["S_country2_per_country1"] * df["P1_CPI"] / df["P2_CPI"]
    df = df.replace([np.inf, -np.inf], np.nan)
    return df.sort_index()


def make_chart(data: pd.DataFrame, view: str, c1: str, c2: str) -> go.Figure:
    both = view == "Both"
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    if view in ("Real", "Both"):
        fig.add_trace(go.Scatter(x=data.index, y=data["Real_Index"], name="Real index (sample mean = 100)",
                                 mode="lines", line=dict(color="#2563eb", width=2.5),
                                 hovertemplate="%{x|%b %Y}<br>Real index: %{y:.2f}<extra></extra>"), secondary_y=False)
        fig.add_hline(y=100, line_dash="dash", line_color="#94a3b8", annotation_text="Sample average = 100")
    if view in ("Nominal", "Both"):
        fig.add_trace(go.Scatter(x=data.index, y=data["S_country2_per_country1"],
                                 name=f"Nominal: {c2} per {c1}", mode="lines",
                                 line=dict(color="#e8793e", width=2),
                                 hovertemplate="%{x|%b %Y}<br>Nominal S: %{y:,.6g}<extra></extra>"),
                      secondary_y=both)
    fig.update_yaxes(title_text="Real exchange rate index (mean = 100)" if view != "Nominal" else f"{c2} per {c1}",
                     secondary_y=False)
    if both:
        fig.update_yaxes(title_text=f"Nominal: {c2} per {c1}", secondary_y=True)
    fig.update_layout(height=490, hovermode="x unified", margin=dict(l=20, r=20, t=25, b=20),
                      legend=dict(orientation="h", y=1.12), xaxis_title="Month")
    return fig


with st.sidebar:
    st.header("Comparison settings")
    codes = list(COUNTRIES)
    c1 = st.selectbox("Country 1 (base currency)", codes,
                      index=codes.index("USA"), format_func=lambda x: f"{COUNTRIES[x]} ({x})")
    c2 = st.selectbox("Country 2 (quote currency)", codes,
                      index=codes.index("THA"), format_func=lambda x: f"{COUNTRIES[x]} ({x})")
    view = st.radio("Chart view", ["Both", "Real", "Nominal"], horizontal=True)
    st.caption("Nominal S is Country 2 currency units per one Country 1 currency unit.")

with st.spinner("Fetching monthly CPI and exchange-rate series from IMF…"):
    try:
        full = build_frame(c1, c2)
    except (ValueError, RuntimeError, requests.RequestException) as exc:
        st.error(str(exc))
        st.info("Try a different country pair. IMF coverage and the Euro-area series may be limited; the service can also be temporarily unavailable.")
        st.stop()

last_month = min(pd.Period(date.today(), freq="M"), pd.Period(full.index.max(), freq="M"))
with st.sidebar:
    st.divider()
    st.subheader("Sample period")
    min_date = FIRST.to_timestamp().date()
    max_date = last_month.to_timestamp().date()
    default_start = max(FIRST, last_month - 119).to_timestamp().date()
    start_date = st.date_input("Start month", value=default_start, min_value=min_date, max_value=max_date, format="YYYY/MM/DD")
    end_date = st.date_input("End month", value=max_date, min_value=min_date, max_value=max_date, format="YYYY/MM/DD")

start = pd.Period(start_date, freq="M")
end = pd.Period(end_date, freq="M")
if start > end:
    st.error("Start month must be on or before end month.")
    st.stop()

# Reindex to all months so missing observations remain visible in the CSV.
months = pd.period_range(start, end, freq="M").to_timestamp()
sample = full.reindex(months)
sample.index.name = "Month"
valid = sample["RER"].notna() & np.isfinite(sample["RER"]) & (sample["RER"] > 0)
if not valid.any():
    st.warning("There are no months with both CPI observations and both exchange-rate observations in this period. Choose another sample or pair.")
    st.stop()

rer_star = sample.loc[valid, "RER"].mean()
sample["RER_sample_average"] = rer_star
sample["Real_Index"] = 100 * sample["RER"] / rer_star
n_valid = int(valid.sum())

st.markdown(f"### {COUNTRIES[c1]} → {COUNTRIES[c2]}")
st.caption(f"S(t): units of {COUNTRIES[c2]} currency per 1 unit of {COUNTRIES[c1]} currency")
a, b, c, d = st.columns(4)
a.metric("Valid monthly observations", f"{n_valid:,}")
b.metric("Average real exchange rate (RER*)", f"{rer_star:,.5g}")
c.metric("Latest valid real index", f"{sample.loc[valid, 'Real_Index'].iloc[-1]:,.2f}")
d.metric("Months in selected window", f"{len(sample):,}")

st.plotly_chart(make_chart(sample, view, c1, c2), use_container_width=True)
with st.expander("How to interpret the chart", expanded=True):
    st.markdown(
        "**Nominal S(t)** is the amount of Country 2 currency for one Country 1 currency. "
        "**RER(t) = S(t) × P1(t) / P2(t)** adjusts for relative consumer prices. "
        "**RER*** is the arithmetic mean of valid RER observations **inside your selected dates**, "
        "and **Real Index(t) = 100 × RER(t) / RER***. "
        "An index above 100 means Country 1's currency is more expensive in real terms "
        "relative to its selected-period average (under this quote convention). "
        "The sample average is **not** an estimate of fundamental PPP equilibrium."
    )

if n_valid < len(sample):
    st.warning(f"{len(sample) - n_valid:,} of {len(sample):,} selected months lack at least one required positive observation. Gaps are not interpolated.")

st.subheader("Monthly observations and calculations")
output = sample.copy()
output.insert(0, "Country_1", c1)
output.insert(1, "Country_2", c2)
output.insert(2, "Valid_RER_month", valid)
output.index = output.index.strftime("%Y-%m")
st.dataframe(output, use_container_width=True)
st.download_button(
    "⬇ Download selected-period CSV",
    data=output.to_csv(index_label="Month").encode("utf-8-sig"),
    file_name=f"IMF_RER_{c1}_{c2}_{start}_{end}.csv",
    mime="text/csv",
)
st.caption("Source: IMF SDMX 3.0 API, CPI and ER dataflows. Series: COUNTRY.CPI._T.IX.M and COUNTRY.XDC_USD.PA_RT.M. "
           "The IMF may revise observations; availability varies by economy and indicator.")
