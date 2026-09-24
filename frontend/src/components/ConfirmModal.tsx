import { useEffect, useRef, ReactNode } from 'react';

interface Props {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: 'default' | 'danger';
  busy?: boolean;
  children?: ReactNode;
  onConfirm: () => void;
  onCancel: () => void;
}

export default function ConfirmModal({
  open,
  title,
  message,
  confirmLabel = 'Подтвердить',
  cancelLabel = 'Отмена',
  variant = 'default',
  busy = false,
  children,
  onConfirm,
  onCancel,
}: Props) {
  const confirmRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !busy) onCancel();
      if (e.key === 'Enter' && !busy && !children) onConfirm();
    };
    window.addEventListener('keydown', onKey);
    if (!children) setTimeout(() => confirmRef.current?.focus(), 50);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, busy, onCancel, onConfirm, children]);

  if (!open) return null;

  const confirmCls =
    variant === 'danger'
      ? 'bg-red-600 hover:bg-red-700 text-white'
      : 'bg-slate-900 hover:bg-slate-800 text-white';

  return (
    <div
      className="fixed inset-0 bg-black bg-opacity-30 z-50 flex items-center justify-center"
      onClick={() => !busy && onCancel()}
    >
      <div
        className="bg-white rounded-lg p-5 w-[460px] shadow-xl"
        onClick={e => e.stopPropagation()}
      >
        <h2 className="text-lg font-semibold mb-3">{title}</h2>
        <div className="text-sm text-slate-700 mb-3 whitespace-pre-line">
          {message}
        </div>
        {children && <div className="mb-4">{children}</div>}
        <div className="flex justify-end gap-2">
          <button
            onClick={onCancel}
            disabled={busy}
            className="px-4 py-2 text-sm rounded border border-slate-300 hover:bg-slate-100 disabled:opacity-50"
          >
            {cancelLabel}
          </button>
          <button
            ref={confirmRef}
            onClick={onConfirm}
            disabled={busy}
            className={`px-4 py-2 text-sm rounded disabled:opacity-50 ${confirmCls}`}
          >
            {busy ? '⏳ Выполняется…' : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}