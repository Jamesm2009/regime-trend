"""
regime-trend: multivariate Gaussian HMM market regime detection.

Fits on SPX log returns, TNX (10Y yield) daily change, and VIX level.
10-year rolling window, weekly refit, label-matched across refits.
Live use: filtered probabilities only. Viterbi path for historical display.
"""
import numpy as np
import pandas as pd
from hmmlearn.hmm import GaussianHMM
from scipy.stats import multivariate_normal


def fit_regime_model(X: np.ndarray, n_states: int, n_restarts: int = 10, seed: int = 42):
    """Fit a Gaussian HMM with multiple random restarts, keep best log-likelihood."""
    best_model, best_score = None, -np.inf
    for i in range(n_restarts):
        try:
            model = GaussianHMM(
                n_components=n_states,
                covariance_type="full",
                n_iter=1000,
                random_state=seed + i,
            )
            model.fit(X)
            score = model.score(X)
        except Exception:
            continue
        if score > best_score:
            best_score, best_model = score, model
    return best_model, best_score


def select_state_count(X: np.ndarray, state_range=(2, 3, 4), n_restarts: int = 10):
    """BIC-based state count selection. Returns results sorted by BIC (lower is better)."""
    n_obs = X.shape[0]
    n_features = X.shape[1]
    results = []
    for n_states in state_range:
        model, logL = fit_regime_model(X, n_states, n_restarts)
        if model is None:
            continue
        # params: transition matrix (n*(n-1)) + means (n*features) + covars (n*features*(features+1)/2) + initial (n-1)
        n_params = (
            n_states * (n_states - 1)
            + n_states * n_features
            + n_states * n_features * (n_features + 1) // 2
            + (n_states - 1)
        )
        bic = -2 * logL + n_params * np.log(n_obs)
        results.append({"n_states": n_states, "log_likelihood": logL, "bic": bic, "model": model})
    return sorted(results, key=lambda r: r["bic"])


def check_regime_stability(model, X: np.ndarray, min_avg_duration_days: float = 3.0):
    """Decode Viterbi path and check average regime duration."""
    states = model.predict(X)
    durations, current, dur = [], states[0], 1
    for s in states[1:]:
        if s == current:
            dur += 1
        else:
            durations.append(dur)
            current, dur = s, 1
    durations.append(dur)
    avg_duration = float(np.mean(durations))
    return {
        "avg_duration": avg_duration,
        "n_transitions": len(durations),
        "is_stable": avg_duration >= min_avg_duration_days,
        "durations": durations,
    }


def label_by_mean_return(model, return_feature_idx: int = 0):
    """
    Map arbitrary HMM state indices to a stable ordering by mean return
    (ascending: crisis=lowest return ... calm=highest return).
    Returns a dict {old_state_index: new_label_index}.
    """
    means = model.means_[:, return_feature_idx]
    order = np.argsort(means)  # ascending: worst return first
    return {old_idx: new_idx for new_idx, old_idx in enumerate(order)}


def relabel_states(states: np.ndarray, label_map: dict) -> np.ndarray:
    return np.array([label_map[s] for s in states])


def filtered_probabilities(model, X: np.ndarray, label_map: dict = None) -> pd.DataFrame:
    """
    Forward algorithm: P(state_t | observations up to t only).
    This is the ONLY probability appropriate for live/current-regime display.
    """
    n_obs, n_states = X.shape[0], model.n_components
    emission_probs = np.zeros((n_obs, n_states))
    for i in range(n_states):
        emission_probs[:, i] = multivariate_normal.pdf(
            X, mean=model.means_[i], cov=model.covars_[i]
        )

    filtered = np.zeros((n_obs, n_states))
    alpha = model.startprob_ * emission_probs[0]
    alpha = alpha / alpha.sum()
    filtered[0] = alpha
    for t in range(1, n_obs):
        alpha = (filtered[t - 1] @ model.transmat_) * emission_probs[t]
        alpha = alpha / alpha.sum()
        filtered[t] = alpha

    cols = list(range(n_states))
    if label_map:
        # reorder columns according to label_map (old_idx -> new_idx)
        reordered = np.zeros_like(filtered)
        for old_idx, new_idx in label_map.items():
            reordered[:, new_idx] = filtered[:, old_idx]
        filtered = reordered

    return pd.DataFrame(filtered, columns=[f"regime_{i}" for i in cols])


def filter_step(model, prev_alpha: np.ndarray, x_t: np.ndarray) -> np.ndarray:
    """
    Single incremental forward-algorithm step for daily live updates.
    Given yesterday's filtered probability vector (prev_alpha) and today's
    new observation (x_t), returns today's filtered probability vector.
    Avoids refitting or rescanning full history daily — only the weekly
    refit does that. This is what the daily cron job calls.
    """
    n_states = model.n_components
    emission_probs = np.array([
        multivariate_normal.pdf(x_t, mean=model.means_[i], cov=model.covars_[i])
        for i in range(n_states)
    ])
    alpha = (prev_alpha @ model.transmat_) * emission_probs
    alpha = alpha / alpha.sum()
    return alpha
