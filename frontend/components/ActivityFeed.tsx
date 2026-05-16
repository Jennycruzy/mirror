"use client";

import { useEffect, useState } from "react";
import { openMirrorStream } from "../lib/sse";

export function ActivityFeed() {
  const [events, setEvents] = useState<string[]>([]);

  useEffect(() => {
    const source = openMirrorStream();
    source.onmessage = (event) => setEvents((current) => [event.data, ...current].slice(0, 20));
    source.onerror = () => setEvents((current) => ["SSE connection error", ...current].slice(0, 20));
    return () => source.close();
  }, []);

  return (
    <section className="rounded-3xl border border-slate-800 bg-slate-900/70 p-6">
      <h2 className="text-lg font-semibold">Live Activity</h2>
      <div className="mt-4 space-y-2 text-sm text-slate-400">
        {events.length === 0 ? <p>No SSE events received yet.</p> : events.map((event, index) => <p key={`${event}-${index}`}>{event}</p>)}
      </div>
    </section>
  );
}

