import { useEffect, useState } from 'react';

/**
 * Полоса прогресса сверху окна, показывает активные HTTP-запросы.
 * Подключается в App.tsx и слушает глобальный счётчик.
 */
let activeCount = 0;
const listeners = new Set<(n: number) => void>();

export function trackRequestStart() {
  activeCount++;
  listeners.forEach(l => l(activeCount));
}

export function trackRequestEnd() {
  activeCount = Math.max(0, activeCount - 1);
  listeners.forEach(l => l(activeCount));
}

export default function TopLoadingBar() {
  const [count, setCount] = useState(0);

  useEffect(() => {
    const listener = (n: number) => setCount(n);
    listeners.add(listener);
    return () => { listeners.delete(listener); };
  }, []);

  const visible = count > 0;

  return (
    <div
      className="fixed top-0 left-0 right-0 h-0.5 bg-transparent z-[100] pointer-events-none"
      style={{ opacity: visible ? 1 : 0, transition: 'opacity 200ms' }}
    >
      <div className="h-full bg-indigo-500 animate-loading-bar" />
      <style>{`
        @keyframes loading-bar {
          0%   { width: 0%; margin-left: 0%; }
          50%  { width: 40%; margin-left: 30%; }
          100% { width: 20%; margin-left: 80%; }
        }
        .animate-loading-bar {
          animation: loading-bar 1.2s ease-in-out infinite;
        }
      `}</style>
    </div>
  );
}