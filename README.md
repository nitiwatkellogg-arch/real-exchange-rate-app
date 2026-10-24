# IMF Real Exchange Rate Explorer

A Streamlit application for an International Finance class, built for **Python 3.12**.

## Run locally

```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS / Linux:
# source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

The browser normally opens at `http://localhost:8501`.

## How to use

1. Select **Country 1** and **Country 2** in the sidebar (Euro area is `G163`).
2. Select **Real**, **Nominal**, or **Both**. In Both mode, real and nominal series use separate axes.
3. Choose a start and end month. The selected sample's RER mean and real index automatically update.
4. Download the CSV containing **every month in the selected window**, including missing observations and calculated columns.

## Economic definitions

- `P1_CPI` and `P2_CPI`: monthly IMF consumer price indices.
- `FX1_per_USD`, `FX2_per_USD`: local currency units per USD (IMF quote convention).
- `S_country2_per_country1 = FX2_per_USD / FX1_per_USD`.
- `RER = S_country2_per_country1 * P1_CPI / P2_CPI`.
- `RER_sample_average = arithmetic mean(RER)` over months where all inputs are valid, **within the selected period**.
- `Real_Index = 100 * RER / RER_sample_average`.

Nominal S is **never normalized**. For example, with USA as Country 1 and Thailand as Country 2, S is THB per USD. A higher RER corresponds to a real appreciation of Country 1's currency relative to Country 2's currency under the specified quote direction. The 100 benchmark is the **selected-period average**, not an independently established PPP equilibrium.

## IMF data

Endpoint: `https://api.imf.org/external/sdmx/3.0`

- CPI flow: `data/dataflow/IMF.STA/CPI/~/ISO3.CPI._T.IX.M`
- Exchange-rate flow: `data/dataflow/IMF.STA/ER/~/ISO3.XDC_USD.PA_RT.M`
- Requested observation window: January 1976 onward.
- Data is requested as CSV with `Accept: text/csv`; the app parses IMF's `YYYY-MMM`-style monthly labels (`YYYY-M01`, etc.).
- Data is cached for 24 hours. The app does not interpolate missing values, invent observations, or silently substitute alternative indicators.

**Important limitations:** Some IMF member economies and Euro-area observations may not be available for the precise supplied keys. The country menu uses ISO-3166 country names with a curated non-member/territory exclusion list plus `G163` and `XKX`; it is a practical menu, **not a live verified IMF membership roster**. Some economies may have limited coverage, redenominations, CPI rebasing, or no reported ER series. The API may rate-limit or change flow identifiers. Errors are displayed in the app rather than fabricating data. Same-country comparisons are defined with S=1. Currency unions and historical euro introduction dates require particular care when interpreting long-run series.

## CSV columns

`Month`, `Country_1`, `Country_2`, `Valid_RER_month`, `P1_CPI`, `P2_CPI`, `FX1_per_USD`, `FX2_per_USD`, `S_country2_per_country1`, `RER`, `RER_sample_average`, `Real_Index`.

## Troubleshooting

- **No data:** Try USA vs THA or another country pair; IMF's actual series availability is not guaranteed.
- **HTTP error / timeout:** Retry later. The public IMF service can be intermittently unavailable.
- **Missing months:** Normal. Only valid, positive, matched observations contribute to the RER average.
- **Unexpected changes:** IMF revisions or differences in CPI base periods can change levels. Confirm the CPI series have compatible base-index conventions before making economic claims about levels.

## Sources

- [IMF Data API](https://data.imf.org/en/Resource-Pages/IMF-API)
- [IMF SDMX 3.0 endpoint](https://api.imf.org/external/sdmx/3.0)
