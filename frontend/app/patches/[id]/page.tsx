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
    <main className="min-h-screen p-8">
      <h1 className="mb-6 text-3xl font-semibold">Patch</h1>
      <PatchDiff patch={patch} />
    </main>
  );
}
