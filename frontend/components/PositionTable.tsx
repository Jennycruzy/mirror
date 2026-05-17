import type { PaperStatus, Trade } from "../lib/types";

export function PositionTable({ paperStatus, trades }: { paperStatus: PaperStatus | null; trades: Trade[] }) {
  const positions = paperStatus?.positions?.positions ?? [];
  return (
    <section className="rounded-3xl border border-slate-800 bg-slate-950/70 p-6 shadow-xl">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.25em] text-slate-500">Kraken Futures Paper</p>
          <h2 className="mt-2 text-2xl font-semibold text-slate-50">Open Positions & PnL</h2>
        </div>
        <span className="rounded-full bg-slate-800 px-3 py-1 text-xs text-slate-300">{paperStatus?.status?.mode ?? "unknown"}</span>
      </div>

      <div className="mt-5 grid gap-3 sm:grid-cols-4">
        <Metric label="Equity" value={money(paperStatus?.status?.equity)} />
        <Metric label="Net PnL" value={money(paperStatus?.status?.pnl)} tone={(paperStatus?.status?.pnl ?? 0) >= 0 ? "good" : "bad"} />
        <Metric label="Unrealized" value={money(paperStatus?.status?.unrealized_pnl)} tone={(paperStatus?.status?.unrealized_pnl ?? 0) >= 0 ? "good" : "bad"} />
        <Metric label="Fills" value={`${paperStatus?.status?.total_fills ?? trades.length}`} />
      </div>

      {positions.length ? (
        <div className="mt-5 overflow-x-auto">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead className="text-xs uppercase tracking-[0.18em] text-slate-500">
              <tr>
                <th className="py-3">Symbol</th>
                <th>Side</th>
                <th>Size</th>
                <th>Entry</th>
                <th>Mark</th>
                <th>Leverage</th>
                <th>Unrealized</th>
                <th>Liq.</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800 text-slate-300">
              {positions.map((position) => (
                <tr key={`${position.symbol}-${position.side}`}>
                  <td className="py-3 font-medium text-slate-100">{position.symbol}</td>
                  <td className="capitalize">{position.side}</td>
                  <td>{position.size.toFixed(6)}</td>
                  <td>{number(position.entry_price)}</td>
                  <td>{number(position.mark_price)}</td>
                  <td>{position.leverage}x</td>
                  <td className={(position.unrealized_pnl ?? 0) >= 0 ? "text-teal-300" : "text-rose-300"}>{money(position.unrealized_pnl)}</td>
                  <td>{number(position.liquidation_price)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="mt-5 rounded-2xl border border-slate-800 bg-slate-900/70 p-5 text-sm text-slate-400">No open Kraken futures paper positions.</p>
      )}
    </section>
  );
}

function Metric({ label, value, tone }: { label: string; value: string; tone?: "good" | "bad" }) {
  const color = tone === "good" ? "text-teal-300" : tone === "bad" ? "text-rose-300" : "text-slate-100";
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-4">
      <p className="text-[11px] uppercase tracking-[0.2em] text-slate-600">{label}</p>
      <p className={`mt-2 text-xl font-semibold ${color}`}>{value}</p>
    </div>
  );
}

function money(value: number | null | undefined) {
  return value === null || value === undefined ? "n/a" : `$${value.toFixed(2)}`;
}

function number(value: number | null | undefined) {
  return value === null || value === undefined ? "n/a" : value.toFixed(4);
}
