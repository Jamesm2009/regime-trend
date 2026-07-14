"use client";

import { useEffect } from "react";

const REGIME_COLOR = ["#C4362C", "#D9A441", "#3FA796"];

export default function GuideModal({ onClose }: { onClose: () => void }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
    };
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4 md:p-8"
      onClick={onClose}
    >
      <div
        className="bg-panel border border-hairline rounded-lg max-w-2xl w-full max-h-[85vh] overflow-y-auto p-8"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex justify-between items-start mb-6">
          <h2 className="font-mono text-sm tracking-widest text-subtext uppercase">
            How regime-trend works
          </h2>
          <button
            onClick={onClose}
            className="text-subtext hover:text-text font-mono text-sm border border-hairline rounded px-2 py-1"
          >
            close
          </button>
        </div>

        <div className="space-y-6 text-sm leading-relaxed">
          <section>
            <h3 className="text-text font-semibold mb-2">What it does</h3>
            <p className="text-subtext">
              Every day, the market's price action, volatility, and rates leave statistical
              &quot;fingerprints&quot; — but never announce which kind of market they belong to. This
              model reads SPY returns, VIX level, and 10-year Treasury yield changes together and
              infers which of three hidden regimes is most likely generating that behavior right
              now. It doesn&apos;t predict the future — it estimates the present.
            </p>
          </section>

          <section>
            <h3 className="text-text font-semibold mb-2">The three regimes</h3>
            <div className="space-y-3">
              <RegimeDef
                color={REGIME_COLOR[2]}
                name="Calm"
                desc="Steady positive returns, low volatility (VIX ~13). The market grinding higher without much drama."
              />
              <RegimeDef
                color={REGIME_COLOR[1]}
                name="Transitional"
                desc="Mixed signals — moderate volatility (VIX ~18), returns positive but less consistent, more rate movement. Neither clearly calm nor in crisis."
              />
              <RegimeDef
                color={REGIME_COLOR[0]}
                name="Crisis"
                desc="Negative average returns, high volatility (VIX ~28+). Sharp drawdowns, elevated fear — this is where Volmageddon, Brexit's shock, and the Covid crash all showed up."
              />
            </div>
          </section>

          <section>
            <h3 className="text-text font-semibold mb-2">Reading the confidence number</h3>
            <p className="text-subtext">
              The percentage next to the current regime is a confidence level, not a certainty —
              it reflects everything observed up through the last close, with no lookahead. In
              backtesting against real history, this measure correctly flagged the onset of
              Volmageddon, Brexit, and the Covid crash within 0-2 trading days of the actual event.
              A reading sitting near 50/50 between two regimes is itself informative: it means the
              market&apos;s statistical behavior is genuinely ambiguous right now, not that the model
              is malfunctioning.
            </p>
          </section>

          <section>
            <h3 className="text-text font-semibold mb-2">How to use this in decisions</h3>
            <p className="text-subtext mb-2">
              Treat this as context, not a trade signal:
            </p>
            <ul className="text-subtext list-disc list-inside space-y-1">
              <li>A shift toward Crisis with rising confidence is a reason to reduce risk appetite or tighten hedges — not to panic-sell on day one.</li>
              <li>Sustained Calm readings support staying the course on longer-horizon positioning.</li>
              <li>Transitional readings are a signal to wait for more confirmation rather than act on ambiguity.</li>
              <li>Cross-reference with VIX Term Trigger (shown above) and your other dashboards — agreement across independent models is more meaningful than either alone. See below for how these two specifically relate.</li>
            </ul>
          </section>

          <section>
            <h3 className="text-text font-semibold mb-2">Update schedule</h3>
            <p className="text-subtext">
              The model refits its full 10-year view weekly (Sunday night). Between refits, the
              current-regime confidence updates daily after market close using the prior day&apos;s
              model — this is what gives near-real-time detection without the cost of refitting
              every day.
            </p>
          </section>

          <section>
            <h3 className="text-text font-semibold mb-2">The VIX Term Trigger reading</h3>
            <p className="text-subtext mb-2">
              The reading shown above is a separate tool (
              <a
                href="https://riskindicator-v4.vercel.app"
                target="_blank"
                rel="noopener noreferrer"
                className="underline hover:text-text"
              >
                open the full app
              </a>
              ) — a faster z-scored composite of VIX term structure (VIX9D vs. VIX) and SPY 5-day
              momentum. It reacts to near-term stress on a day-to-day basis, while regime-trend
              describes the broader statistical character of the market over weeks to months.
              They are not measuring the same thing, and a backtest against 10 years of real data
              confirms they behave differently:
            </p>
            <ul className="text-subtext list-disc list-inside space-y-1">
              <li>On sharp, obvious shocks (Volmageddon, the Covid crash), both flagged the same day — neither has a real speed edge on major moves.</li>
              <li>During regime-trend&apos;s Crisis periods, VIX Term Trigger only read Risk Off or Lean Off about 44% of the time — it&apos;s reacting to moment-to-moment stress spikes within a sustained crisis, not the crisis itself.</li>
              <li>About 1 in 5 of VIX Term Trigger&apos;s Risk Off signals fired while regime-trend still read the market as Calm — a meaningful false-alarm-looking rate in isolation.</li>
            </ul>
            <p className="text-subtext mt-2">
              Practical takeaway: treat a VIX Term Trigger Risk Off signal as higher-conviction
              when regime-trend is also in Crisis or Transitional, and more skeptically when
              regime-trend still reads Calm.
            </p>
          </section>

          <section>
            <h3 className="text-text font-semibold mb-2">Limits worth knowing</h3>
            <p className="text-subtext">
              Regimes are statistical clusters fit to the trailing 10 years, not fixed physical
              categories — &quot;Crisis&quot; today reflects a blend of Volmageddon, Covid, and other
              stress periods in that window, not a single fixed threshold. As older history rolls
              out of the 10-year window over time, regime boundaries can drift slightly. This is a
              descriptive tool for understanding current market character, not a predictive one.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}

function RegimeDef({ color, name, desc }: { color: string; name: string; desc: string }) {
  return (
    <div className="flex gap-3">
      <div className="w-1 rounded-full flex-shrink-0" style={{ background: color }} />
      <div>
        <div className="font-mono font-semibold" style={{ color }}>
          {name}
        </div>
        <div className="text-subtext">{desc}</div>
      </div>
    </div>
  );
}
