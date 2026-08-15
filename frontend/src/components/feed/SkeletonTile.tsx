export default function SkeletonTile() {
  return (
    <div
      data-skeleton-tile="true"
      className="flex h-14 animate-pulse flex-col items-center justify-center gap-1.5 rounded-md border border-zinc-800 bg-zinc-900"
    >
      <div className="h-3 w-10 rounded bg-zinc-800" />
      <div className="flex gap-1">
        <div className="h-1.5 w-1.5 rounded-full bg-zinc-800" />
        <div className="h-1.5 w-1.5 rounded-full bg-zinc-800" />
        <div className="h-1.5 w-1.5 rounded-full bg-zinc-800" />
      </div>
    </div>
  );
}
