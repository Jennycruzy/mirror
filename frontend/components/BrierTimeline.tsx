"use client";

import { useEffect, useState } from "react";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { fetchJson } from "../lib/api";
import type { Forecast } from "../lib/types";

export function BrierTimeline({ agentId }: { agentId?: string }) {
  const [forecasts, setForecasts] = useState<Forecast[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchJson<Forecast[]>("/forecasts").then(setForecasts).catch((err) => setError(err.message));
  }, []);

  const data = forecasts
    .filter((forecast) => (!agentId || forecast.agent_id === agentId) && forecast.brier_score !== null && forecast.brier_score !== undefined)
    .reverse()
    .map((forecast) => ({ emitted_at: new Date(forecast.emitted_at).toLocaleTimeString(), brier: forecast.brier_score }));

  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6">
      <h2 className="text-lg font-semibold">Brier Timeline</h2>
      {error ? <p className="mt-4 text-rose-300">{error}</p> : null}
      {!error && data.length === 0 ? <p className="mt-4 text-slate-400">No Brier scores stored yet.</p> : null}
      {data.length > 0 ? (
        <div className="mt-4 h-72">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data}>
              <XAxis dataKey="emitted_at" stroke="#64748b" />
              <YAxis stroke="#64748b" />
              <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid #334155" }} />
              <Line type="monotone" dataKey="brier" stroke="#2dd4bf" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      ) : null}
    </section>
  );
}
