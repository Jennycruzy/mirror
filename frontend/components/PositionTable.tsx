"use client";

import { useMemo, useState } from "react";
import type { PaperStatus, Trade } from "../lib/types";

export function PositionTable({ paperStatus, trades }: { paperStatus: PaperStatus | null; trades: Trade[] }) {
  const [sideFilter, setSideFilter] = useState<"all" | "buy" | "sell">("all");
  const [statusFilter, setStatusFilter] = useState<"all" | "open" | "closed">("all");
  const [selectedTradeId, setSelectedTradeId] = useState<string | null>(null);
  const positions = paperStatus?.positions?.positions ?? [];
  const accountTrades = trades.filter((trade) => trade.mode === "account");
  const recentTrades = useMemo(
    () =>
      accountTrades
        .filter((trade) => sideFilter === "all" || trade.side === sideFilter)
        .filter((trade) => statusFilter === "all" || trade.status === statusFilter)
        .slice(0, 10),
    [accountTrades, sideFilter, statusFilter]
  );
  const selectedTrade = recentTrades.find((trade) => trade.id === selectedTradeId) ?? accountTrades.find((trade) => trade.id === selectedTradeId);
  const equity = paperStatus?.status?.equity ?? paperStatus?.status?.current_value;
  const netPnl = paperStatus?.status?.pnl ?? paperStatus?.status?.unrealized_pnl;
  const fills = trades.filter((trade) => trade.status === "closed").length;
  const openTrades = accountTrades.filter((trade) => trade.status === "open").length;
  return (
    <section className="mirror-panel">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-cyan-400/10 p-4">
        <div>
          <p className="text-xs uppercase tracking-[0.25em] text-cyan-300/60">Kraken Execution</p>
          <h2 className="mt-2 font-mono text-2xl font-semibold text-slate-50 drop-shadow-[0_0_16px_rgba(34,211,238,0.18)]">Portfolio & Orders</h2>
        </div>
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 animate-pulse rounded-full bg-teal-300 shadow-[0_0_16px_rgba(45,212,191,0.9)]" />
          <span className="border border-teal-400/20 bg-teal-500/10 px-3 py-1 text-xs uppercase tracking-[0.16em] text-teal-200">{paperStatus?.status?.mode ?? "unknown"}</span>
        </div>
      </div>

      <div className="grid gap-px bg-cyan-400/10 sm:grid-cols-5">
        <Metric label="Equity" value={money(equity)} />
        <Metric label="Net PnL" value={money(netPnl)} tone={(netPnl ?? 0) >= 0 ? "good" : "bad"} />
        <Metric label="Unrealized" value={money(paperStatus?.status?.unrealized_pnl)} tone={(paperStatus?.status?.unrealized_pnl ?? 0) >= 0 ? "good" : "bad"} />
        <Metric label="Open" value={`${openTrades}`} />
        <Metric label="Fills" value={`${fills}`} />
      </div>

      <div className="flex flex-wrap items-center gap-2 border-t border-cyan-400/10 p-3">
        <span className="mr-2 text-xs uppercase tracking-[0.22em] text-cyan-200/45">Filters</span>
        {(["all", "buy", "sell"] as const).map((value) => (
          <button key={value} className={filterButtonClass(sideFilter === value)} type="button" onClick={() => setSideFilter(value)}>
            {value}
          </button>
        ))}
        <span className="mx-1 h-5 w-px bg-slate-800" />
        {(["all", "open", "closed"] as const).map((value) => (
          <button key={value} className={filterButtonClass(statusFilter === value)} type="button" onClick={() => setStatusFilter(value)}>
            {value}
          </button>
        ))}
        {selectedTrade ? (
          <button className="ml-auto border border-slate-700 px-3 py-1 text-xs uppercase tracking-[0.16em] text-slate-300 hover:bg-slate-800" type="button" onClick={() => setSelectedTradeId(null)}>
            Clear detail
          </button>
        ) : null}
      </div>

      <div className="overflow-x-auto border-t border-cyan-400/10">
        <table className="w-full min-w-[720px] text-left text-sm">
          <thead className="bg-slate-950/70 text-xs uppercase tracking-[0.18em] text-cyan-200/45">
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
                <tr key={trade.id} className={`cursor-pointer hover:bg-cyan-950/20 ${selectedTradeId === trade.id ? "bg-cyan-950/30" : ""}`} onClick={() => setSelectedTradeId(selectedTradeId === trade.id ? null : trade.id)}>
                  <td className="py-3 pl-4 text-slate-500">{trade.opened_at ? new Date(trade.opened_at).toLocaleTimeString() : "n/a"}</td>
                  <td className="text-slate-100">{trade.ticker}</td>
                  <td>
                    <span className={trade.side === "buy" ? "border border-teal-400/20 bg-teal-400/10 px-2 py-1 text-teal-300" : "border border-rose-400/20 bg-rose-400/10 px-2 py-1 text-rose-300"}>{String(trade.side ?? "").toUpperCase()}</span>
                  </td>
                  <td>{money(trade.size_usd)}</td>
                  <td>{number(trade.entry_price)}</td>
                  <td className={trade.status === "open" ? "text-amber-200" : "text-slate-400"}>{String(trade.status ?? "").toUpperCase()}</td>
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

      {selectedTrade ? (
        <div className="grid gap-3 border-t border-cyan-400/10 bg-slate-950/95 p-4 text-sm md:grid-cols-4">
          <Detail label="Trade ID" value={selectedTrade.id.slice(0, 8)} />
          <Detail label="Forecast" value={selectedTrade.forecast_id.slice(0, 8)} />
          <Detail label="Exit" value={selectedTrade.exit_price ? number(selectedTrade.exit_price) : "open"} />
          <Detail label="Realized PnL" value={money(selectedTrade.realized_pnl_usd)} tone={(selectedTrade.realized_pnl_usd ?? 0) >= 0 ? "good" : "bad"} />
        </div>
      ) : null}

      {positions.length ? (
        <div className="overflow-x-auto border-t border-cyan-400/10">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead className="bg-slate-950/70 text-xs uppercase tracking-[0.18em] text-cyan-200/45">
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
                <tr key={`${position.symbol}-${position.side}`} className="hover:bg-cyan-950/20">
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
        <p className="border-t border-cyan-400/10 bg-slate-950 p-4 text-sm text-slate-500">No derivatives position rows. Balances and execution history are shown above.</p>
      )}
    </section>
  );
}

function Metric({ label, value, tone }: { label: string; value: string; tone?: "good" | "bad" }) {
  const color = tone === "good" ? "text-teal-300 drop-shadow-[0_0_12px_rgba(45,212,191,0.35)]" : tone === "bad" ? "text-rose-300 drop-shadow-[0_0_12px_rgba(251,113,133,0.28)]" : "text-slate-100";
  return (
    <div className="bg-slate-950/95 p-4 transition-colors hover:bg-slate-900/90">
      <p className="text-[11px] uppercase tracking-[0.2em] text-cyan-200/45">{label}</p>
      <p className={`mt-2 font-mono text-xl font-semibold ${color}`}>{value}</p>
    </div>
  );
}

function Detail({ label, value, tone }: { label: string; value: string; tone?: "good" | "bad" }) {
  const color = tone === "good" ? "text-teal-300" : tone === "bad" ? "text-rose-300" : "text-slate-100";
  return (
    <div className="border border-slate-800 bg-slate-900/50 p-3">
      <p className="text-[10px] uppercase tracking-[0.2em] text-cyan-200/45">{label}</p>
      <p className={`mt-1 font-mono ${color}`}>{value}</p>
    </div>
  );
}

function filterButtonClass(active: boolean) {
  return active
    ? "border border-cyan-300/40 bg-cyan-400/15 px-3 py-1 text-xs uppercase tracking-[0.16em] text-cyan-100"
    : "border border-slate-800 bg-slate-950 px-3 py-1 text-xs uppercase tracking-[0.16em] text-slate-500 hover:border-cyan-400/20 hover:text-slate-200";
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
