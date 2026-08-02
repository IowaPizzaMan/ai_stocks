# frontend/src/components/shared/SkeletonCard.tsx

## Purpose
Animated loading placeholder for AnalysisCard while data fetches. Matches the exact dimensions of AnalysisCard to prevent layout shift.

## Implementation
```tsx
export function SkeletonCard() {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 animate-pulse">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className="w-16 h-5 bg-slate-700 rounded" />   {/* ticker */}
          <div className="w-20 h-5 bg-slate-800 rounded-full" /> {/* signal badge */}
        </div>
        <div className="w-24 h-4 bg-slate-800 rounded" />     {/* timestamp */}
      </div>
      <div className="space-y-2">
        <div className="w-full h-4 bg-slate-800 rounded" />
        <div className="w-4/5 h-4 bg-slate-800 rounded" />
        <div className="w-2/3 h-4 bg-slate-800 rounded" />
      </div>
      <div className="flex items-center gap-4 mt-4">
        <div className="flex gap-1">
          {[0,1,2].map(i => <div key={i} className="w-2 h-2 rounded-full bg-slate-700" />)}
        </div>
        <div className="w-20 h-3 bg-slate-800 rounded" />
      </div>
    </div>
  )
}
```

## Usage
Render 5–10 SkeletonCards in the feed during initial load. Use `Array.from({ length: n }).map((_, i) => <SkeletonCard key={i} />)`.
