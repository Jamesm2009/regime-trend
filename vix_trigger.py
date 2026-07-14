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


MAX_STALE_DAYS = 3  # forward-fill VIX9D up to this many trading days before flagging as stale


def fetch_vix_trigger_inputs(years_back: float = 1.0) -> pd.DataFrame:
    """
    Only needs enough trailing history to fill the 63-day rolling z-score
    window (plus buffer) — unlike regime-trend's 10-year fit, this is cheap
    to pull daily.

    IMPORTANT: uses SPY's trading calendar as the master index rather than
    an inner join across all three tickers. VIX9D is thinly tracked and can
    lag SPY/VIX by a few days on Yahoo's feed — an inner join would silently
    truncate the ENTIRE dataset back to VIX9D's stale date, hiding several
    days of real SPY/VIX moves. Forward-filling VIX9D for short gaps keeps
    the rest of the data current instead.
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

    merged = pd.DataFrame(index=spy.index)
    merged["spy"] = spy
    merged["vix"] = vix.reindex(spy.index).ffill(limit=MAX_STALE_DAYS)
    merged["vix9d"] = vix9d.reindex(spy.index).ffill(limit=MAX_STALE_DAYS)
    merged = merged.dropna()
    merged.attrs["vix9d_last_actual_date"] = vix9d.index[-1]
    merged.attrs["vix_last_actual_date"] = vix.index[-1]
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
    vix9d_last_actual = raw.attrs.get("vix9d_last_actual_date")
    result = compute_vix_trigger(raw)
    last = result.iloc[-1]
    as_of_date = result.index[-1]

    stale = vix9d_last_actual is not None and vix9d_last_actual < as_of_date
    stale_days = (as_of_date - vix9d_last_actual).days if stale else 0

    return {
        "date": as_of_date.strftime("%Y-%m-%d"),
        "composite_z": round(float(last["composite_z"]), 3),
        "classification": last["classification"],
        "vix_term_z": round(float(last["vix_term_z"]), 3),
        "spy_mom_z": round(float(last["spy_mom_z"]), 3),
        "vix": round(float(last["vix"]), 2),
        "vix9d": round(float(last["vix9d"]), 2),
        "vix9d_stale": stale,
        "vix9d_last_actual_date": vix9d_last_actual.strftime("%Y-%m-%d") if vix9d_last_actual is not None else None,
    }
