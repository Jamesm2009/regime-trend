"use client";

import { useEffect, useState } from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceArea,
} from "recharts";
import GuideModal from "./GuideModal";

const REGIME_COLOR = ["#C4362C", "#D9A441", "#3FA796"]; // crisis, transitional, calm
const REGIME_NAME = ["Crisis", "Transitional", "Calm"];

type ApiData = {
  modelParams: {
    last_date: string;
    refit_date: string;
    stability: { avg_duration_days: number; n_transitions: number; is_stable: boolean };
  };
  history: {
    dates: string[];
    regime: number[];
    filtered_probs: number[][];
    spy_close: number[];
  };
};

export default function Home() {
  const [data, setData] = useState<ApiData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showGuide, setShowGuide] = useState(false);

  useEffect(() => {
    fetch("/api/regime")
      .then((r) => r.json())
      .then((d) => (d.error ? setError(d.error) : setData(d)))
      .catch((e) => setError(String(e)));
  }, []);

  if (error) {
    return (
      <main className="min-h-screen flex items-center justify-center p-8">
        <div className="text-crisis font-mono text-sm border border-hairline rounded p-6 bg-panel">
          {error}
        </div>
      </main>
    );
  }

  if (!data) {
    return (
      <main className="min-h-screen flex items-center justify-center">
        <div className="text-subtext font-mono text-sm animate-pulse">reading signal…</div>
      </main>
    );
  }

  const { modelParams, history } = data;
  const currentProbs = history.filtered_probs[history.filtered_probs.length - 1];
  const currentRegime = currentProbs.indexOf(Math.max(...currentProbs));

  // Build contiguous regime segments for chart shading + regime tape
  const segments: { start: number; end: number; regime: number }[] = [];
  let segStart = 0;
  for (let i = 1; i <= history.regime.length; i++) {
    if (i === history.regime.length || history.regime[i] !== history.regime[segStart]) {
      segments.push({ start: segStart, end: i - 1, regime: history.regime[segStart] });
      segStart = i;
    }
  }

  const chartData = history.dates.map((date, i) => ({
    date,
    price: history.spy_close[i],
  }));

  return (
    <main className="min-h-screen px-6 py-10 md:px-12 max-w-6xl mx-auto">
      <header className="mb-10 flex items-baseline justify-between flex-wrap gap-2">
        <div>
          <h1 className="font-mono text-sm tracking-widest text-subtext uppercase">regime-trend</h1>
          <p className="text-subtext text-xs mt-1">
            SPY · VIX · TNX — 10yr rolling window, 3-state HMM
          </p>
        </div>
        <div className="flex items-center gap-4">
          <button
            onClick={() => setShowGuide(true)}
            className="text-xs font-mono text-subtext hover:text-text border border-hairline rounded px-3 py-1.5 uppercase tracking-widest transition-colors"
          >
            Guide
          </button>
          <div className="text-xs text-subtext font-mono text-right">
            <div>as of {modelParams.last_date}</div>
            <div>refit {modelParams.refit_date}</div>
          </div>
        </div>
      </header>

      {showGuide && <GuideModal onClose={() => setShowGuide(false)} />}

      {/* Hero: current regime readout */}
      <section className="mb-10 bg-panel border border-hairline rounded-lg p-8">
        <div className="text-subtext text-xs uppercase tracking-widest mb-2">Current Regime</div>
        <div className="flex items-end gap-4 mb-6">
          <div
            className="text-5xl md:text-6xl font-mono font-semibold"
            style={{ color: REGIME_COLOR[currentRegime] }}
          >
            {REGIME_NAME[currentRegime]}
          </div>
          <div className="text-2xl font-mono text-subtext mb-1">
            {(currentProbs[currentRegime] * 100).toFixed(1)}%
          </div>
        </div>
        <div className="grid grid-cols-3 gap-3">
          {[0, 1, 2].map((r) => (
            <div key={r} className="border border-hairline rounded p-3">
              <div className="text-xs text-subtext uppercase tracking-wide mb-1">
                {REGIME_NAME[r]}
              </div>
              <div className="font-mono text-lg" style={{ color: REGIME_COLOR[r] }}>
                {(currentProbs[r] * 100).toFixed(1)}%
              </div>
              <div className="h-1 mt-2 rounded-full bg-ink overflow-hidden">
                <div
                  className="h-full"
                  style={{
                    width: `${currentProbs[r] * 100}%`,
                    background: REGIME_COLOR[r],
                  }}
                />
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Regime tape — signature element: compressed full-history strip */}
      <section className="mb-10">
        <div className="text-subtext text-xs uppercase tracking-widest mb-2">
          Regime Tape — {history.dates[0]} to {history.dates[history.dates.length - 1]}
        </div>
        <div className="flex h-6 rounded overflow-hidden border border-hairline">
          {segments.map((seg, i) => (
            <div
              key={i}
              style={{
                flexGrow: seg.end - seg.start + 1,
                background: REGIME_COLOR[seg.regime],
              }}
              title={`${REGIME_NAME[seg.regime]}: ${history.dates[seg.start]} to ${history.dates[seg.end]}`}
            />
          ))}
        </div>
      </section>

      {/* Price chart with regime-shaded background */}
      <section className="mb-10 bg-panel border border-hairline rounded-lg p-6">
        <div className="text-subtext text-xs uppercase tracking-widest mb-4">
          SPY vs. Detected Regime
        </div>
        <ResponsiveContainer width="100%" height={360}>
          <AreaChart data={chartData}>
            <defs>
              <linearGradient id="priceFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#E8EAED" stopOpacity={0.25} />
                <stop offset="100%" stopColor="#E8EAED" stopOpacity={0} />
              </linearGradient>
            </defs>
            {segments.map((seg, i) => (
              <ReferenceArea
                key={i}
                x1={chartData[seg.start].date}
                x2={chartData[seg.end].date}
                fill={REGIME_COLOR[seg.regime]}
                fillOpacity={0.12}
                stroke="none"
              />
            ))}
            <XAxis
              dataKey="date"
              tick={{ fill: "#8A9099", fontSize: 11, fontFamily: "IBM Plex Mono" }}
              tickLine={false}
              axisLine={{ stroke: "#262B31" }}
              minTickGap={80}
            />
            <YAxis
              tick={{ fill: "#8A9099", fontSize: 11, fontFamily: "IBM Plex Mono" }}
              tickLine={false}
              axisLine={{ stroke: "#262B31" }}
              domain={["auto", "auto"]}
            />
            <Tooltip
              contentStyle={{
                background: "#14181D",
                border: "1px solid #262B31",
                borderRadius: 6,
                fontFamily: "IBM Plex Mono",
                fontSize: 12,
              }}
              labelStyle={{ color: "#8A9099" }}
            />
            <Area
              type="monotone"
              dataKey="price"
              stroke="#E8EAED"
              strokeWidth={1.5}
              fill="url(#priceFill)"
            />
          </AreaChart>
        </ResponsiveContainer>
      </section>

      {/* Stability stats */}
      <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatCard
          label="Avg Regime Duration"
          value={`${modelParams.stability.avg_duration_days.toFixed(1)} days`}
        />
        <StatCard
          label="Transitions (10yr)"
          value={String(modelParams.stability.n_transitions)}
        />
        <StatCard
          label="Stability Check"
          value={modelParams.stability.is_stable ? "Passing" : "Flagged"}
          color={modelParams.stability.is_stable ? "#3FA796" : "#C4362C"}
        />
      </section>
    </main>
  );
}

function StatCard({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="bg-panel border border-hairline rounded-lg p-5">
      <div className="text-subtext text-xs uppercase tracking-widest mb-2">{label}</div>
      <div className="font-mono text-2xl" style={{ color: color || "#E8EAED" }}>
        {value}
      </div>
    </div>
  );
}
