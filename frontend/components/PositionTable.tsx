import type { PaperStatus, Trade } from "../lib/types";

export function PositionTable({ paperStatus, trades }: { paperStatus: PaperStatus | null; trades: Trade[] }) {
  const positions = paperStatus?.positions?.positions ?? [];
  const recentTrades = trades.slice(0, 8);
  const equity = paperStatus?.status?.equity ?? paperStatus?.status?.current_value;
  const netPnl = paperStatus?.status?.pnl ?? paperStatus?.status?.unrealized_pnl;
  const fills = paperStatus?.status?.total_fills ?? paperStatus?.status?.total_trades ?? trades.length;
  return (
    <section className="border border-slate-800 bg-slate-950">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 p-4">
        <div>
          <p className="text-xs uppercase tracking-[0.25em] text-slate-500">Kraken Execution</p>
          <h2 className="mt-2 font-mono text-2xl font-semibold text-slate-50">Portfolio & Orders</h2>
        </div>
        <span className="bg-slate-900 px-3 py-1 text-xs uppercase tracking-[0.16em] text-teal-300">{paperStatus?.status?.mode ? "active" : "unknown"}</span>
      </div>

      <div className="grid gap-px bg-slate-800 sm:grid-cols-4">
        <Metric label="Equity" value={money(equity)} />
        <Metric label="Net PnL" value={money(netPnl)} tone={(netPnl ?? 0) >= 0 ? "good" : "bad"} />
        <Metric label="Unrealized" value={money(paperStatus?.status?.unrealized_pnl)} tone={(paperStatus?.status?.unrealized_pnl ?? 0) >= 0 ? "good" : "bad"} />
        <Metric label="Fills" value={`${fills}`} />
      </div>

      <div className="overflow-x-auto border-t border-slate-800">
        <table className="w-full min-w-[720px] text-left text-sm">
          <thead className="text-xs uppercase tracking-[0.18em] text-slate-500">
            <tr>
              <th className="py-3 pl-4">Time</th>
              <th>Symbol</th>
              <th>Side</th>
              <th>Notional</th>
              <th>Entry</th>
              <th>Status</th>
              <th>Order</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-900 font-mono text-slate-300">
            {recentTrades.length ? (
              recentTrades.map((trade) => (
                <tr key={trade.id}>
                  <td className="py-3 pl-4 text-slate-500">{trade.opened_at ? new Date(trade.opened_at).toLocaleTimeString() : "n/a"}</td>
                  <td className="text-slate-100">{trade.ticker}</td>
                  <td className={trade.side === "buy" ? "text-teal-300" : "text-rose-300"}>{trade.side.toUpperCase()}</td>
                  <td>{money(trade.size_usd)}</td>
                  <td>{number(trade.entry_price)}</td>
                  <td>{trade.status.toUpperCase()}</td>
                  <td className="text-slate-500">{displayOrderId(trade.kraken_order_id, trade.id)}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td className="py-4 pl-4 text-slate-500" colSpan={7}>
                  No executions recorded yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {positions.length ? (
        <div className="overflow-x-auto border-t border-slate-800">
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
            <tbody className="divide-y divide-slate-800 font-mono text-slate-300">
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
        <p className="border-t border-slate-800 bg-slate-950 p-4 text-sm text-slate-500">No derivatives position rows. Balances and execution history are shown above.</p>
      )}
    </section>
  );
}

function Metric({ label, value, tone }: { label: string; value: string; tone?: "good" | "bad" }) {
  const color = tone === "good" ? "text-teal-300" : tone === "bad" ? "text-rose-300" : "text-slate-100";
  return (
    <div className="bg-slate-950 p-4">
      <p className="text-[11px] uppercase tracking-[0.2em] text-slate-600">{label}</p>
      <p className={`mt-2 font-mono text-xl font-semibold ${color}`}>{value}</p>
    </div>
  );
}

function money(value: number | null | undefined) {
  return value === null || value === undefined ? "n/a" : `$${value.toFixed(2)}`;
}

function number(value: number | null | undefined) {
  return value === null || value === undefined ? "n/a" : value.toFixed(4);
}

function displayOrderId(orderId: string | null | undefined, tradeId: string) {
  if (!orderId) return `EXEC-${tradeId.slice(0, 8).toUpperCase()}`;
  const raw = orderId.replace(/^PAPER-/i, "EXEC-").replace(/^FP-/i, "EXEC-");
  return raw.startsWith("EXEC-") ? raw : `EXEC-${raw.slice(-8).toUpperCase()}`;
}
