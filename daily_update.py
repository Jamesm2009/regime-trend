"""
regime-trend: daily filtered-probability update.

Run this every trading day (e.g. after market close via cron) on the droplet.
Does NOT refit the model — it reuses whatever model weekly_refit.py last
wrote to Redis, and takes a single incremental forward-algorithm step using
yesterday's filtered probabilities + today's new observation. This is what
gives near-real-time regime detection between weekly refits.

Requires weekly_refit.py to have run at least once already (needs
rt_model_params and rt_history in Redis).
"""
import numpy as np
import pandas as pd
from types import SimpleNamespace

from data_fetch import fetch_features
from regime_model import filter_step
from redis_client import get_json, set_json
from vix_trigger import get_current_reading


def update_vtt_reading():
    """
    Fetches and stores today's VIX Term Trigger reading, shown alongside
    regime-trend on the dashboard for cross-reference. Wrapped separately
    so a VTT-specific failure (e.g. a Yahoo hiccup on ^VIX9D) never blocks
    the main regime update above.
    """
    try:
        reading = get_current_reading()
        set_json("vtt_current", reading)
        print(f"VIX Term Trigger: {reading['classification']} (z={reading['composite_z']}) "
              f"as of {reading['date']}")
    except Exception as e:
        print(f"VIX Term Trigger update failed (non-fatal): {e}")


def main():
    model_params = get_json("model_params")
    history = get_json("history")
    if model_params is None or history is None:
        raise RuntimeError(
            "No existing model found in Redis. Run weekly_refit.py first."
        )

    last_date = pd.Timestamp(model_params["last_date"])

    # Pull a small recent window — only need enough to compute today's
    # log-return/diff features, not the full 10-year history.
    features = fetch_features(years_back=1)
    new_rows = features[features.index > last_date]

    if new_rows.empty:
        print(f"No new trading days since {last_date.date()}. Nothing to do.")
        update_vtt_reading()
        return

    # Reconstruct a minimal model-like object with just what filter_step needs
    model = SimpleNamespace(
        n_components=model_params["n_states"],
        means_=np.array(model_params["means"]),
        covars_=np.array(model_params["covars"]),
        transmat_=np.array(model_params["transmat"]),
    )

    alpha = np.array(model_params["last_alpha"])
    new_dates, new_filtered, new_closes = [], [], []

    for date, row in new_rows.iterrows():
        x_t = row[["spy_ret", "tnx_chg", "vix"]].values.astype(float)
        alpha = filter_step(model, alpha, x_t)
        new_dates.append(date.strftime("%Y-%m-%d"))
        new_filtered.append(alpha.tolist())
        new_closes.append(float(row["spy_close"]))
        print(f"{date.date()}: crisis={alpha[0]:.1%}  transitional={alpha[1]:.1%}  calm={alpha[2]:.1%}")

    # Append to history and update the rolling alpha for tomorrow
    history["dates"].extend(new_dates)
    history["filtered_probs"].extend(new_filtered)
    history["spy_close"].extend(new_closes)

    model_params["last_alpha"] = alpha.tolist()
    model_params["last_date"] = new_dates[-1]

    set_json("model_params", model_params)
    set_json("history", history)
    print(f"Updated through {new_dates[-1]}.")

    update_vtt_reading()


if __name__ == "__main__":
    main()
