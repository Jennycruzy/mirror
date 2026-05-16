import { PhylogeneticTree } from "../../components/PhylogeneticTree";

export default function LineagePage() {
  return (
    <main className="min-h-screen p-8">
      <h1 className="mb-6 text-3xl font-semibold">Lineage</h1>
      <PhylogeneticTree />
    </main>
  );
}

