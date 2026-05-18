import type { PaperStatus, Trade } from "../lib/types";

export function PositionTable({ paperStatus, trades }: { paperStatus: PaperStatus | null; trades: Trade[] }) {
  const positions = paperStatus?.positions?.positions ?? [];
  const recentTrades = trades.filter((trade) => trade.mode === "account").slice(0, 10);
  const equity = paperStatus?.status?.equity ?? paperStatus?.status?.current_value;
  const netPnl = paperStatus?.status?.pnl ?? paperStatus?.status?.unrealized_pnl;
  const fills = trades.filter((trade) => trade.status === "closed").length;
  const accountTrades = trades.filter((trade) => trade.mode === "account");
  const openTrades = accountTrades.filter((trade) => trade.status === "open").length;
  return (
    <section className="border border-cyan-500/20 bg-slate-950/95 shadow-[0_0_30px_rgba(14,165,233,0.06)]">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 p-4">
        <div>
          <p className="text-xs uppercase tracking-[0.25em] text-slate-500">Kraken Execution</p>
          <h2 className="mt-2 font-mono text-2xl font-semibold text-slate-50">Portfolio & Orders</h2>
        </div>
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 animate-pulse rounded-full bg-teal-300" />
          <span className="bg-teal-500/10 px-3 py-1 text-xs uppercase tracking-[0.16em] text-teal-200">{paperStatus?.status?.mode ?? "unknown"}</span>
        </div>
      </div>

      <div className="grid gap-px bg-slate-800 sm:grid-cols-5">
        <Metric label="Equity" value={money(equity)} />
        <Metric label="Net PnL" value={money(netPnl)} tone={(netPnl ?? 0) >= 0 ? "good" : "bad"} />
        <Metric label="Unrealized" value={money(paperStatus?.status?.unrealized_pnl)} tone={(paperStatus?.status?.unrealized_pnl ?? 0) >= 0 ? "good" : "bad"} />
        <Metric label="Open" value={`${openTrades}`} />
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
                <tr key={trade.id} className="hover:bg-slate-900/70">
                  <td className="py-3 pl-4 text-slate-500">{trade.opened_at ? new Date(trade.opened_at).toLocaleTimeString() : "n/a"}</td>
                  <td className="text-slate-100">{trade.ticker}</td>
                  <td className={trade.side === "buy" ? "text-teal-300" : "text-rose-300"}>{String(trade.side ?? "").toUpperCase()}</td>
                  <td>{money(trade.size_usd)}</td>
                  <td>{number(trade.entry_price)}</td>
                  <td>{String(trade.status ?? "").toUpperCase()}</td>
                  <td className="text-slate-500">{displayOrderId(trade.kraken_order_id, trade.id)}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td className="py-4 pl-4 text-slate-500" colSpan={7}>
                  No account-mode executions recorded yet.
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
                <tr key={`${position.symbol}-${position.side}`} className="hover:bg-slate-900/70">
                  <td className="py-3 font-medium text-slate-100">{position.symbol}</td>
                  <td className={position.side === "long" ? "capitalize text-teal-300" : "capitalize text-rose-300"}>{position.side}</td>
                  <td>{number(position.size, 2)}</td>
                  <td>{number(position.entry_price)}</td>
                  <td>{number(position.mark_price)}</td>
                  <td>{number(position.leverage)}x</td>
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
  return typeof value === "number" && Number.isFinite(value) ? `$${value.toFixed(2)}` : "n/a";
}

function number(value: number | null | undefined, digits = 4) {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(digits) : "n/a";
}

function displayOrderId(orderId: string | null | undefined, tradeId: string) {
  if (!orderId) return `EXEC-${tradeId.slice(0, 8).toUpperCase()}`;
  const raw = orderId.replace(/^PAPER-/i, "EXEC-").replace(/^FP-/i, "EXEC-");
  return raw.startsWith("EXEC-") ? raw : `EXEC-${raw.slice(-8).toUpperCase()}`;
}
