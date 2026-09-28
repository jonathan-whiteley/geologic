import { RotateCcw } from 'lucide-react'

export function PageSkeleton({ statCards = 4 }: { statCards?: number }) {
  return (
    <div className="space-y-6 animate-pulse" aria-label="Loading">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {Array.from({ length: statCards }).map((_, i) => (
          <div key={i} className="card p-6 h-28 bg-gray-100" />
        ))}
      </div>
      <div className="grid lg:grid-cols-3 gap-6">
        <div className="card p-6 h-64 bg-gray-100 lg:col-span-2" />
        <div className="card p-6 h-64 bg-gray-100" />
      </div>
    </div>
  )
}

export function ErrorRetry({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="card p-6 flex items-center justify-between gap-4">
      <p className="text-sm text-red-600">{message}</p>
      <button className="btn btn-secondary" onClick={onRetry}>
        <RotateCcw className="w-4 h-4" />
        Retry
      </button>
    </div>
  )
}
