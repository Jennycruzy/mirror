import { PatchDiff } from "../../../components/PatchDiff";

export default function PatchPage() {
  return (
    <main className="min-h-screen p-8">
      <h1 className="mb-6 text-3xl font-semibold">Patch</h1>
      <PatchDiff />
    </main>
  );
}

