export function LangGraphView() {
  const nodes = ["fetch_market_state", "build_features", "forecast", "decide_action", "execute_trade", "log_event"];
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6">
      <h2 className="text-lg font-semibold text-slate-100">LangGraph Lifecycle</h2>
      <div className="mt-4 grid gap-3 md:grid-cols-3">
        {nodes.map((node) => (
          <div key={node} className="rounded-xl border border-slate-800 bg-slate-950/70 p-3 text-sm text-slate-300">
            {node}
          </div>
        ))}
      </div>
      <p className="mt-4 text-sm text-slate-500">Live node state is emitted through backend events as runs occur.</p>
    </div>
  );
}
