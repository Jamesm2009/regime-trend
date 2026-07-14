"""
compare_regime_vix.py

One-off analysis: how does regime-trend's HMM-based regime detection compare
to VIX Term Trigger's faster z-score composite (VIX9D/VIX term structure +
SPY 5-day momentum)? Not a live dashboard — run manually whenever you want
an updated comparison.

Pulls fresh VIX9D/VIX/SPY data, reconstructs VIX Term Trigger's composite
z-score, and compares it against regime-trend's already-fitted output
(read directly from Redis, so it uses the exact same model currently live
on the dashboard rather than refitting).

Run this on the droplet (needs both Yahoo Finance and Redis access):
    cd ~/regime-trend
    source venv/bin/activate
    set -a && source .env && set +a
    python analysis/compare_regime_vix.py
"""
import numpy as np
import pandas as pd
import yfinance as yf

from redis_client import get_json

# --- VIX Term Trigger reconstruction ---
# NOTE: confirmed by James — VIX Term Trigger's "Neutral" band is -0.5 to +0.5.
ZSCORE_WINDOW = 63
NEUTRAL_BAND = 0.5
VIX_TERM_WEIGHT = 0.70
MOMENTUM_WEIGHT = 0.30


def fetch_vix_trigger_inputs(years_back: int = 11) -> pd.DataFrame:
    start = (pd.Timestamp.today() - pd.DateOffset(years=years_back)).strftime("%Y-%m-%d")

    def pull(ticker):
        df = yf.download(ticker, start=start, progress=False, auto_adjust=True)
        s = df["Close"]
        if isinstance(s, pd.DataFrame):
            s = s.iloc[:, 0]
        return s

    spy = pull("SPY")
    vix = pull("^VIX")
    vix9d = pull("^VIX9D")  # launched 2011, should cover the full 10yr window

    merged = pd.concat([spy, vix, vix9d], axis=1, join="inner").dropna()
    merged.columns = ["spy", "vix", "vix9d"]
    return merged.sort_index()


def compute_vix_trigger(merged: pd.DataFrame) -> pd.DataFrame:
    df = merged.copy()

    # VIX term structure: VIX9D/VIX ratio, inverted so +z = risk-on
    # (a ratio < 1, i.e. backwardation, signals near-term stress = risk-off,
    # so we invert the raw ratio before z-scoring to match the dashboard's
    # "+z = risk-on" convention)
    ratio = df["vix9d"] / df["vix"]
    inverted_ratio = -ratio
    df["vix_term_z"] = (
        (inverted_ratio - inverted_ratio.rolling(ZSCORE_WINDOW).mean())
        / inverted_ratio.rolling(ZSCORE_WINDOW).std()
    )

    # SPY 5-day rate of change, z-scored
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


def load_regime_trend_history() -> pd.DataFrame:
    history = get_json("history")
    if history is None:
        raise RuntimeError("No rt_history found in Redis — has weekly_refit.py run?")
    df = pd.DataFrame({
        "date": pd.to_datetime(history["dates"]),
        "regime": history["regime"],  # 0=crisis, 1=transitional, 2=calm (Viterbi path)
    })
    filtered = np.array(history["filtered_probs"])
    df["p_crisis"] = filtered[:, 0]
    df["p_transitional"] = filtered[:, 1]
    df["p_calm"] = filtered[:, 2]
    return df.set_index("date")


REGIME_NAME = {0: "Crisis", 1: "Transitional", 2: "Calm"}


def main():
    print("Fetching VIX Term Trigger inputs (SPY, VIX, VIX9D)...")
    raw = fetch_vix_trigger_inputs()
    print(f"  {len(raw)} days, {raw.index.min().date()} to {raw.index.max().date()}")

    vtt = compute_vix_trigger(raw)

    print("Loading regime-trend history from Redis...")
    rt = load_regime_trend_history()

    merged = vtt.join(rt, how="inner")
    merged["regime_name"] = merged["regime"].map(REGIME_NAME)
    print(f"Aligned overlap: {len(merged)} days, {merged.index.min().date()} to {merged.index.max().date()}\n")

    # --- Agreement matrix ---
    print("=" * 70)
    print("AGREEMENT MATRIX: regime-trend regime (rows) vs VIX Term Trigger (cols)")
    print("=" * 70)
    ct = pd.crosstab(merged["regime_name"], merged["classification"])
    # reorder for readability
    col_order = [c for c in ["Risk Off", "Lean Off", "Neutral", "Lean On", "Risk On"] if c in ct.columns]
    row_order = [r for r in ["Crisis", "Transitional", "Calm"] if r in ct.index]
    print(ct.reindex(index=row_order, columns=col_order, fill_value=0))
    print()

    # --- False positive rate: VTT flips Risk Off while regime-trend says Calm ---
    risk_off_during_calm = ((merged["classification"] == "Risk Off") & (merged["regime_name"] == "Calm")).sum()
    total_risk_off = (merged["classification"] == "Risk Off").sum()
    if total_risk_off > 0:
        print(f"VIX Term Trigger 'Risk Off' days that occurred during regime-trend 'Calm': "
              f"{risk_off_during_calm}/{total_risk_off} ({risk_off_during_calm/total_risk_off:.1%})")
    print()

    # --- Lead/lag around known stress events ---
    print("=" * 70)
    print("LEAD/LAG AROUND KNOWN STRESS EVENTS")
    print("=" * 70)
    events = [
        ("Volmageddon", "2018-02-05"),
        ("Covid crash onset", "2020-02-24"),
        ("Brexit vote", "2016-06-24"),
    ]
    for name, date_str in events:
        event_date = pd.Timestamp(date_str)
        if event_date not in merged.index:
            # nearest trading day on/after
            candidates = merged.index[merged.index >= event_date]
            if len(candidates) == 0:
                print(f"{name}: outside data range, skipping")
                continue
            event_date = candidates[0]

        window = merged.loc[event_date: event_date + pd.Timedelta(days=15)]

        vtt_off_days = window.index[window["classification"] == "Risk Off"]
        rt_crisis_days = window.index[window["p_crisis"] > 0.5]

        vtt_lag = (vtt_off_days[0] - event_date).days if len(vtt_off_days) > 0 else None
        rt_lag = (rt_crisis_days[0] - event_date).days if len(rt_crisis_days) > 0 else None

        print(f"\n{name} ({event_date.date()}):")
        print(f"  VIX Term Trigger reached 'Risk Off':  "
              f"{'day ' + str(vtt_lag) if vtt_lag is not None else 'not within 15 days'}")
        print(f"  regime-trend crossed >50% crisis:     "
              f"{'day ' + str(rt_lag) if rt_lag is not None else 'not within 15 days'}")
        if vtt_lag is not None and rt_lag is not None:
            diff = rt_lag - vtt_lag
            if diff > 0:
                print(f"  -> VIX Term Trigger led by {diff} day(s)")
            elif diff < 0:
                print(f"  -> regime-trend led by {-diff} day(s)")
            else:
                print(f"  -> Same day")

    print("\nDone.")


if __name__ == "__main__":
    main()
