"use client";

import { useEffect, useState } from "react";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { fetchJson } from "../lib/api";
import type { CalibrationBucket } from "../lib/types";

export function CalibrationCurve({ agentId }: { agentId?: string }) {
  const [data, setData] = useState<CalibrationBucket[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const query = agentId ? `?agent_id=${agentId}` : "";
    fetchJson<CalibrationBucket[]>(`/calibration${query}`).then(setData).catch((err) => setError(err.message));
  }, [agentId]);

  const chartData = data
    .filter((bucket) => bucket.predicted_avg !== null && bucket.realized_frequency !== null)
    .map((bucket) => ({
      bin: `${bucket.lower.toFixed(1)}-${bucket.upper.toFixed(1)}`,
      predicted: bucket.predicted_avg,
      realized: bucket.realized_frequency,
      ideal: bucket.predicted_avg
    }));

  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6">
      <h2 className="text-lg font-semibold">Calibration Curve</h2>
      {error ? <p className="mt-4 text-rose-300">{error}</p> : null}
      {!error && chartData.length === 0 ? <p className="mt-4 text-slate-400">No resolved forecasts available.</p> : null}
      {chartData.length > 0 ? (
        <div className="mt-4 h-72">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData}>
              <XAxis dataKey="bin" stroke="#64748b" />
              <YAxis domain={[0, 1]} stroke="#64748b" />
              <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid #334155" }} />
              <Line type="monotone" dataKey="ideal" stroke="#475569" dot={false} />
              <Line type="monotone" dataKey="realized" stroke="#f59e0b" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      ) : null}
    </section>
  );
}
