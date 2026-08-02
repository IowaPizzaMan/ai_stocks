export default function SkeletonCard() {
  return (
    <div className="animate-pulse rounded-xl border border-zinc-800 bg-zinc-900 p-5">
      <div className="mb-3 flex items-center gap-3">
        <div className="h-5 w-16 rounded bg-zinc-800" />
        <div className="h-5 w-20 rounded-full bg-zinc-800" />
        <div className="ml-auto h-4 w-24 rounded bg-zinc-800" />
      </div>
      <div className="mb-2 h-4 w-full rounded bg-zinc-800" />
      <div className="mb-2 h-4 w-5/6 rounded bg-zinc-800" />
      <div className="h-4 w-2/3 rounded bg-zinc-800" />
    </div>
  );
}
