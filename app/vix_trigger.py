"""
Shared VIX Term Trigger reconstruction logic.
Used by both analysis/compare_regime_vix.py (historical backtest) and
daily_update.py (today's live reading for the dashboard).

NOTE: Neutral band confirmed by James as -0.5 to +0.5.
"""
import pandas as pd
import yfinance as yf

ZSCORE_WINDOW = 63
NEUTRAL_BAND = 0.5
VIX_TERM_WEIGHT = 0.70
MOMENTUM_WEIGHT = 0.30


def fetch_vix_trigger_inputs(years_back: float = 1.0) -> pd.DataFrame:
    """
    Only needs enough trailing history to fill the 63-day rolling z-score
    window (plus buffer) — unlike regime-trend's 10-year fit, this is cheap
    to pull daily.
    """
    start = (pd.Timestamp.today() - pd.DateOffset(years=years_back)).strftime("%Y-%m-%d")

    def pull(ticker):
        df = yf.download(ticker, start=start, progress=False, auto_adjust=True)
        s = df["Close"]
        if isinstance(s, pd.DataFrame):
            s = s.iloc[:, 0]
        return s

    spy = pull("SPY")
    vix = pull("^VIX")
    vix9d = pull("^VIX9D")

    merged = pd.concat([spy, vix, vix9d], axis=1, join="inner").dropna()
    merged.columns = ["spy", "vix", "vix9d"]
    return merged.sort_index()


def compute_vix_trigger(merged: pd.DataFrame) -> pd.DataFrame:
    df = merged.copy()

    ratio = df["vix9d"] / df["vix"]
    inverted_ratio = -ratio
    df["vix_term_z"] = (
        (inverted_ratio - inverted_ratio.rolling(ZSCORE_WINDOW).mean())
        / inverted_ratio.rolling(ZSCORE_WINDOW).std()
    )

    spy_roc = df["spy"].pct_change(5)
    df["spy_mom_z"] = (
        (spy_roc - spy_roc.rolling(ZSCORE_WINDOW).mean())
        / spy_roc.rolling(ZSCORE_WINDOW).std()
    )

    df["composite_z"] = VIX_TERM_WEIGHT * df["vix_term_z"] + MOMENTUM_WEIGHT * df["spy_mom_z"]

    def classify(z):
        if pd.isna(z):
            return None
        if z < -1:
            return "Risk Off"
        if z < -NEUTRAL_BAND:
            return "Lean Off"
        if z <= NEUTRAL_BAND:
            return "Neutral"
        if z <= 1:
            return "Lean On"
        return "Risk On"

    df["classification"] = df["composite_z"].apply(classify)
    return df.dropna(subset=["composite_z"])


def get_current_reading() -> dict:
    """Returns today's VIX Term Trigger reading as a JSON-serializable dict."""
    raw = fetch_vix_trigger_inputs()
    result = compute_vix_trigger(raw)
    last = result.iloc[-1]
    return {
        "date": result.index[-1].strftime("%Y-%m-%d"),
        "composite_z": round(float(last["composite_z"]), 3),
        "classification": last["classification"],
        "vix_term_z": round(float(last["vix_term_z"]), 3),
        "spy_mom_z": round(float(last["spy_mom_z"]), 3),
        "vix": round(float(last["vix"]), 2),
        "vix9d": round(float(last["vix9d"]), 2),
    }
