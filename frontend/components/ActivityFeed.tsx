import type { MirrorEvent } from "../lib/types";

export function ActivityFeed({ events }: { events: MirrorEvent[] }) {
  return (
    <section className="rounded-3xl border border-slate-800 bg-slate-950/70 p-6 shadow-2xl backdrop-blur">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-100">Live Activity</h2>
        <span className="rounded-full bg-slate-900 px-3 py-1 text-xs text-slate-500">SSE</span>
      </div>
      <div className="mt-4 max-h-96 space-y-2 overflow-auto text-sm">
        {events.length === 0 ? <p className="text-slate-500">No SSE events received yet.</p> : null}
        {events.map((event, index) => (
          <article key={`${event.id ?? event.kind}-${index}`} className="rounded-2xl border border-slate-800 bg-slate-900/60 p-3">
            <div className="flex items-center justify-between gap-3">
              <span className="font-medium text-slate-200">{event.kind}</span>
              <span className={severityClass(event.severity)}>{event.severity ?? "info"}</span>
            </div>
            {event.created_at ? <p className="mt-1 text-xs text-slate-500">{new Date(event.created_at).toLocaleString()}</p> : null}
          </article>
        ))}
      </div>
    </section>
  );
}

function severityClass(severity?: string) {
  if (severity === "error") return "rounded-full bg-rose-500/10 px-2 py-1 text-xs text-rose-200";
  if (severity === "warning") return "rounded-full bg-amber-500/10 px-2 py-1 text-xs text-amber-200";
  return "rounded-full bg-teal-500/10 px-2 py-1 text-xs text-teal-200";
}
