# Real Exchange Rate Explorer

Python 3.12 Streamlit application for an International Finance assignment.

## Deploy on Streamlit Community Cloud (from scratch)

1. Create a new **public GitHub repository**, e.g. `real-exchange-rate-app`.
2. Upload **all three files** (`app.py`, `requirements.txt`, `README.md`) to the **root** of the repository. Do not upload only the ZIP file.
3. In Streamlit Community Cloud choose **Create app**, select your GitHub repository and branch, and set **Main file path** to `app.py`.
4. Under advanced settings, select **Python 3.12** if offered, then deploy.
5. If you see `ModuleNotFoundError`, check that `requirements.txt` is in the root of the deployed branch and that build logs show packages installed. Reboot or clear cache/redeploy after editing dependencies.

## Run locally

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

## Economic definitions

- `S(t)` = units of Country 2 currency per unit of Country 1 currency.
- IMF FX observations are local currency per US dollar. Hence `S(t) = FX2(t) / FX1(t)`.
- `RER(t) = S(t) * CPI1(t) / CPI2(t)`.
- `RER*` is the arithmetic average of positive, finite monthly RER values **within the selected sample**.
- `Real Index(t) = 100 * RER(t) / RER*`.
- The nominal chart shows `S(t)` in actual currency units, not rebased.
- A dual-axis view is available, as is a CSV containing every selected month (including missing data).

## IMF data and limitations

The application requests the IMF SDMX 3.0 CPI and ER flows, starting in January 1976. IMF data coverage varies; some countries, series, and periods may not be available. Data may be revised or API responses may change. The app does not invent missing observations or interpolate gaps. CPI indices may use different reference bases; interpret cross-country levels carefully. A sample mean of 100 is **not** a PPP fair-value estimate.

If IMF changes its SDMX endpoints or schema, the API request/CSV parsing in `fetch_series` may need adjustment. Check Streamlit deployment logs for request errors.
