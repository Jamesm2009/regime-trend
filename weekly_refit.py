"""
regime-trend: weekly refit job.

Run this once a week (e.g. Sunday night via cron) on the droplet.
Pulls a fresh 10-year window, refits the 3-state Gaussian HMM,
runs the BIC/stability sanity checks, relabels states by mean return
(crisis=0, transitional=1, calm=2) for consistency across refits,
and writes model parameters + Viterbi-decoded history to Redis.

The daily_update.py job depends on the Redis keys this writes —
run this first before daily updates will work.
"""
import numpy as np
import pandas as pd

from data_fetch import fetch_features, trim_to_window
from regime_model import (
    fit_regime_model,
    check_regime_stability,
    label_by_mean_return,
    relabel_states,
    filtered_probabilities,
)
from redis_client import set_json

N_STATES = 3  # locked in from validation against real 10.5yr SPY/VIX/TNX data
N_RESTARTS = 10
MIN_AVG_DURATION_DAYS = 3.0


def main():
    print("Fetching data...")
    features = fetch_features(years_back=11)
    features = trim_to_window(features, years=10)
    X = features[["spy_ret", "tnx_chg", "vix"]].values
    print(f"Fitting on {len(features)} days, {features.index.min().date()} to {features.index.max().date()}")

    model, logL = fit_regime_model(X, n_states=N_STATES, n_restarts=N_RESTARTS)
    if model is None:
        raise RuntimeError("HMM fitting failed to converge on any restart")

    stability = check_regime_stability(model, X, min_avg_duration_days=MIN_AVG_DURATION_DAYS)
    print(f"Stability: avg_duration={stability['avg_duration']:.1f} days, "
          f"transitions={stability['n_transitions']}, stable={stability['is_stable']}")
    if not stability["is_stable"]:
        print("WARNING: regimes are flickering below the stability threshold. "
              "Writing results anyway, but this refit should be reviewed before trusting it.")

    label_map = label_by_mean_return(model, return_feature_idx=0)

    decoded = model.predict(X)
    relabeled = relabel_states(decoded, label_map)

    fp = filtered_probabilities(model, X, label_map)
    final_alpha = fp.iloc[-1].values  # last row = today's filtered probabilities, becomes tomorrow's prev_alpha

    # Reorder means/covars/transmat rows+cols to match the new label ordering,
    # so daily_update.py can use model params directly without re-deriving the map.
    order = [old for old, new in sorted(label_map.items(), key=lambda kv: kv[1])]
    means_relabeled = model.means_[order].tolist()
    covars_relabeled = model.covars_[order].tolist()
    transmat_relabeled = model.transmat_[np.ix_(order, order)].tolist()

    model_params = {
        "n_states": N_STATES,
        "means": means_relabeled,
        "covars": covars_relabeled,
        "transmat": transmat_relabeled,
        "last_alpha": final_alpha.tolist(),
        "last_date": features.index.max().strftime("%Y-%m-%d"),
        "refit_date": pd.Timestamp.today().strftime("%Y-%m-%d"),
        "log_likelihood": float(logL),
        "stability": {
            "avg_duration_days": stability["avg_duration"],
            "n_transitions": stability["n_transitions"],
            "is_stable": bool(stability["is_stable"]),
        },
        "regime_labels": {"0": "crisis", "1": "transitional", "2": "calm"},
    }

    history = {
        "dates": [d.strftime("%Y-%m-%d") for d in features.index],
        "regime": relabeled.tolist(),          # Viterbi path, for historical shading only
        "filtered_probs": fp.values.tolist(),  # [ [p_crisis, p_transitional, p_calm], ... ] per day
        "spy_close": features["spy_close"].tolist(),
    }

    set_json("model_params", model_params)
    set_json("history", history)
    print("Wrote rt_model_params and rt_history to Redis.")
    print(f"Current regime as of {model_params['last_date']}: "
          f"crisis={final_alpha[0]:.1%}  transitional={final_alpha[1]:.1%}  calm={final_alpha[2]:.1%}")


if __name__ == "__main__":
    main()
