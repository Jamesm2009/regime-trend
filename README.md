# regime-trend

Multivariate Gaussian HMM market regime detector (SPY returns, TNX change, VIX level).
10-year rolling window, 3 states (crisis / transitional / calm), weekly refit + daily
incremental filtered-probability updates. Deploys via Dokku on the droplet, shares the
existing Upstash Redis instance (key prefix `rt_`).

## Setup on the droplet

```bash
pip install -r requirements.txt
```

Environment variables needed (same Upstash instance as your other dashboards):
```
UPSTASH_REDIS_REST_URL=...
UPSTASH_REDIS_REST_TOKEN=...
```

## First run (required before daily updates will work)

```bash
python weekly_refit.py
```

This fits the model on the trailing 10 years and writes `rt_model_params` and
`rt_history` to Redis. `rt_history` is what the frontend chart reads for
regime-shaded price history; `rt_model_params` holds current regime confidence.

## Cron schedule

```
# Weekly refit — Sunday 11pm, before markets reopen Monday
0 23 * * 0  cd /path/to/regime-trend && python weekly_refit.py >> refit.log 2>&1

# Daily filtered-probability update — after market close on trading days
30 21 * * 1-5  cd /path/to/regime-trend && python daily_update.py >> daily.log 2>&1
```

Adjust the daily update time to your timezone / market close + data availability lag.

## Files

- `data_fetch.py` — Yahoo Finance ingestion (SPY, ^VIX, ^TNX)
- `regime_model.py` — HMM fitting, BIC selection, stability check, label matching,
  filtered/Viterbi decoding, incremental daily filter step
- `redis_client.py` — Upstash REST client
- `weekly_refit.py` — weekly cron job
- `daily_update.py` — daily cron job (depends on weekly_refit having run at least once)

## Design notes (why it's built this way)

- **Filtered, not smoothed, probabilities drive the live "current regime" display.**
  Smoothed probabilities use future data and would be lookahead bias if used live.
- **Weekly refit, daily filter update are deliberately decoupled.** Refitting daily
  would be needlessly heavy; filtering only weekly would mean up to 6 days of lag on
  live regime detection. This split gives same-day detection between refits.
- **Label matching by sorted mean return** (crisis=lowest, calm=highest) keeps regime
  identity stable across refits — without this, state indices can flip arbitrarily
  each time the model is refit.
- **3 states was chosen over BIC's preference for 4** after checking real 10.5-year
  SPY/VIX/TNX history: the 4-state model split "calm" into two barely-distinguishable
  states rather than finding a genuine fourth regime, and produced more flickering
  (131 transitions vs 79). 3 states gave a clean, stable, economically distinct fit,
  validated against Brexit, Volmageddon, and the Covid crash (same-day to next-day
  crisis detection on all three).
