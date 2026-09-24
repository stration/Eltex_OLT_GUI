interface Props {
  className?: string;
}

export function Skeleton({ className = '' }: Props) {
  return (
    <div
      className={`animate-pulse bg-slate-200 rounded ${className}`}
    />
  );
}

export function SkeletonTable({ rows = 5, cols = 5 }: { rows?: number; cols?: number }) {
  return (
    <table className="w-full text-sm">
      <thead className="border-b border-slate-200">
        <tr>
          {Array.from({ length: cols }).map((_, i) => (
            <th key={i} className="text-left p-3">
              <Skeleton className="h-4 w-24" />
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {Array.from({ length: rows }).map((_, r) => (
          <tr key={r} className="border-b border-slate-100 last:border-0">
            {Array.from({ length: cols }).map((_, c) => (
              <td key={c} className="p-3">
                <Skeleton className="h-4 w-full" />
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}