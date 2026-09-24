const STATUS_COLORS: Record<string, string> = {
  OK:        'bg-green-100 text-green-800',
  OFFLINE:   'bg-red-100 text-red-800',
  FAILED:    'bg-red-200 text-red-900',
  BLOCKED:   'bg-yellow-100 text-yellow-800',
  UNACTIVATED: 'bg-slate-100 text-slate-700',
  AUTHFAILED: 'bg-orange-100 text-orange-800',
  FWUPDATING: 'bg-blue-100 text-blue-800',
  CFGFAILED: 'bg-red-100 text-red-800',
};

export default function StatusBadge({ status }: { status: string }) {
  const cls = STATUS_COLORS[status] || 'bg-slate-100 text-slate-700';
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${cls}`}>
      {status}
    </span>
  );
}