import { PatchDiff } from "../../../components/PatchDiff";
import { fetchJson } from "../../../lib/api";
import type { PatchRecord } from "../../../lib/types";

export default async function PatchPage({ params }: { params: { id: string } }) {
  let patch: PatchRecord | undefined;
  try {
    const patches = await fetchJson<PatchRecord[]>("/patches");
    patch = patches.find((item) => item.id === params.id);
  } catch {
    patch = undefined;
  }
  return (
    <main className="min-h-screen bg-slate-950 px-5 py-8 lg:px-10">
      <p className="text-xs uppercase tracking-[0.5em] text-violet-300">Patch</p>
      <h1 className="mb-6 mt-3 text-4xl font-semibold tracking-tight text-slate-50">Holdout gate record</h1>
      <PatchDiff patch={patch} />
    </main>
  );
}
