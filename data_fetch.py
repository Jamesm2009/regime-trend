"""
Pulls SPY, VIX, and TNX daily history from Yahoo Finance and returns
an aligned feature DataFrame: spy_ret (log return), tnx_chg (daily change),
vix (level). Only requires network access to Yahoo Finance, which the
droplet already has (used by your other dashboards).
"""
import numpy as np
import pandas as pd
import yfinance as yf

TICKERS = {"spy": "SPY", "vix": "^VIX", "tnx": "^TNX"}


def fetch_features(years_back: int = 11) -> pd.DataFrame:
    """
    Pulls slightly more than the target window (years_back) so that after
    computing returns/diffs and doing an inner join across all three series
    (they don't all trade/report on identical days), we still have the full
    target window of usable rows. Trim to the exact rolling window at the
    call site, not here.
    """
    start = (pd.Timestamp.today() - pd.DateOffset(years=years_back)).strftime("%Y-%m-%d")

    raw = {}
    for name, ticker in TICKERS.items():
        df = yf.download(ticker, start=start, progress=False, auto_adjust=True)
        if df.empty:
            raise RuntimeError(f"No data returned for {ticker}")
        s = df["Close"]
        if isinstance(s, pd.DataFrame):  # yfinance sometimes returns a 1-col DataFrame
            s = s.iloc[:, 0]
        s.name = name
        raw[name] = s

    merged = pd.concat(raw.values(), axis=1, join="inner").dropna()
    merged.columns = list(raw.keys())
    merged = merged.sort_index()

    features = pd.DataFrame(index=merged.index)
    features["spy_ret"] = np.log(merged["spy"] / merged["spy"].shift(1))
    features["tnx_chg"] = merged["tnx"].diff()
    features["vix"] = merged["vix"]
    features["spy_close"] = merged["spy"]  # kept for chart display, not used in model
    features = features.dropna()

    return features


def trim_to_window(features: pd.DataFrame, years: int = 10) -> pd.DataFrame:
    cutoff = features.index.max() - pd.DateOffset(years=years)
    return features[features.index >= cutoff].copy()
