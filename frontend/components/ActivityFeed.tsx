import type { MirrorEvent } from "../lib/types";

export function ActivityFeed({ events }: { events: MirrorEvent[] }) {
  return (
    <section className="border border-slate-800 bg-slate-950">
      <div className="flex items-center justify-between border-b border-slate-800 p-4">
        <h2 className="font-mono text-lg font-semibold text-slate-100">Event Tape</h2>
        <span className="bg-slate-900 px-3 py-1 text-xs uppercase tracking-[0.16em] text-slate-500">stream</span>
      </div>
      <div className="max-h-96 overflow-auto text-sm">
        {events.length === 0 ? <p className="p-4 text-slate-500">No stream events received yet.</p> : null}
        {events.map((event, index) => (
          <article key={`${event.id ?? event.kind}-${index}`} className="border-b border-slate-900 p-3">
            <div className="flex items-center justify-between gap-3">
              <span className="font-mono text-slate-200">{event.kind}</span>
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
  if (severity === "error") return "bg-rose-500/10 px-2 py-1 text-xs text-rose-200";
  if (severity === "warning") return "bg-amber-500/10 px-2 py-1 text-xs text-amber-200";
  return "bg-teal-500/10 px-2 py-1 text-xs text-teal-200";
}
