import { PhylogeneticTree } from "../../components/PhylogeneticTree";

export default function LineagePage() {
  return (
    <main className="min-h-screen bg-slate-950 px-5 py-8 lg:px-10">
      <p className="text-xs uppercase tracking-[0.5em] text-teal-300">Lineage</p>
      <h1 className="mb-6 mt-3 text-4xl font-semibold tracking-tight text-slate-50">Phylogenetic exchange map</h1>
      <PhylogeneticTree />
    </main>
  );
}
