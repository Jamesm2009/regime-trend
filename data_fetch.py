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
MAX_STALE_DAYS = 3  # forward-fill VIX/TNX up to this many trading days before dropping the row


def fetch_features(years_back: int = 11) -> pd.DataFrame:
    """
    Uses SPY's trading calendar as the master index rather than an inner
    join across all three tickers. TNX and VIX occasionally lag SPY by a
    day or more on Yahoo's feed (confirmed in practice — TNX specifically
    has lagged SPY by a day even when SPY/VIX were current). An inner join
    would silently truncate the ENTIRE dataset back to whichever ticker is
    most stale, which caused daily_update.py to report "no new trading
    days" even when SPY itself had a fresh close. Forward-filling short
    gaps keeps the rest of the data current instead of losing it.
    """
    start = (pd.Timestamp.today() - pd.DateOffset(years=years_back)).strftime("%Y-%m-%d")

    def pull(ticker):
        df = yf.download(ticker, start=start, progress=False, auto_adjust=True)
        if df.empty:
            raise RuntimeError(f"No data returned for {ticker}")
        s = df["Close"]
        if isinstance(s, pd.DataFrame):  # yfinance sometimes returns a 1-col DataFrame
            s = s.iloc[:, 0]
        return s

    spy = pull(TICKERS["spy"])
    vix = pull(TICKERS["vix"])
    tnx = pull(TICKERS["tnx"])

    merged = pd.DataFrame(index=spy.index)
    merged["spy"] = spy
    merged["vix"] = vix.reindex(spy.index).ffill(limit=MAX_STALE_DAYS)
    merged["tnx"] = tnx.reindex(spy.index).ffill(limit=MAX_STALE_DAYS)
    merged = merged.dropna().sort_index()

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
