import { useEffect, useRef } from 'react';
import uPlot from 'uplot';
import 'uplot/dist/uPlot.min.css';
import type { RssiPoint } from '../api/client';

const MONTHS_RU = [
  'янв', 'фев', 'мар', 'апр', 'май', 'июн',
  'июл', 'авг', 'сен', 'окт', 'ноя', 'дек',
];

/** Форматирование времени для оси X: "6:30", "22.09 6:30", "22 сен" */
function formatTime(sec: number, spanSec: number): string {
  const d = new Date(sec * 1000);
  const hh = d.getHours();
  const mm = d.getMinutes().toString().padStart(2, '0');

  // Спан больше 3 суток — показываем дату
  if (spanSec > 3 * 24 * 3600) {
    const dd = d.getDate().toString().padStart(2, '0');
    const month = MONTHS_RU[d.getMonth()];
    return `${dd} ${month}`;
  }
  // Спан больше 12 часов — "дд.мм чч:мм"
  if (spanSec > 12 * 3600) {
    const dd = d.getDate().toString().padStart(2, '0');
    const mm2 = (d.getMonth() + 1).toString().padStart(2, '0');
    return `${dd}.${mm2} ${hh}:${mm}`;
  }
  // Иначе только время
  return `${hh}:${mm}`;
}

/** Полное форматирование для tooltip: "22.09.2026, 14:35:20" */
function formatFull(sec: number): string {
  const d = new Date(sec * 1000);
  const dd = d.getDate().toString().padStart(2, '0');
  const mm = (d.getMonth() + 1).toString().padStart(2, '0');
  const yyyy = d.getFullYear();
  const hh = d.getHours().toString().padStart(2, '0');
  const mi = d.getMinutes().toString().padStart(2, '0');
  const ss = d.getSeconds().toString().padStart(2, '0');
  return `${dd}.${mm}.${yyyy}, ${hh}:${mi}:${ss}`;
}

export default function RssiChart({
  points, height = 240,
}: { points: RssiPoint[]; height?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const u = useRef<uPlot | null>(null);

  useEffect(() => {
    if (!ref.current || points.length === 0) return;

    const xs = points.map(p => new Date(p.ts).getTime() / 1000);
    const ys = points.map(p => p.rssi_db);

    // Диапазон для X (для форматирования)
    const spanSec = xs.length > 1 ? xs[xs.length - 1] - xs[0] : 0;

    // Границы Y с запасом
    const yMin = Math.min(...ys);
    const yMax = Math.max(...ys);
    const pad = Math.max((yMax - yMin) * 0.15, 0.5);

    const opts: uPlot.Options = {
      width: ref.current.clientWidth || 800,
      height,
      scales: {
        x: { time: true },
        y: { range: [yMin - pad, yMax + pad] },
      },
      cursor: {
        y: false,
        points: {
          size: 8,
        },
        drag: { x: true, y: false },
      },
      series: [
        {
          label: 'Время',
          value: (u, v) => v == null ? '—' : formatFull(v),
        },
        {
          label: 'RSSI, dBm',
          stroke: '#6366f1', // accent-500
          width: 2,
          points: { show: points.length < 120, size: 5, width: 1, stroke: '#6366f1' },
          value: (u, v) => v == null ? '—' : `${v.toFixed(2)} dBm`,
        },
      ],
      axes: [
        {
          stroke: '#64748b',
          grid: { stroke: '#e2e8f0', width: 1 },
          ticks: { stroke: '#cbd5e1', width: 1 },
          font: '11px Inter, sans-serif',
          size: 42,
          values: (u, ticks) => ticks.map(t => formatTime(t, spanSec)),
        },
        {
          stroke: '#64748b',
          grid: { stroke: '#e2e8f0', width: 1 },
          ticks: { stroke: '#cbd5e1', width: 1 },
          font: '11px Inter, sans-serif',
          size: 52,
          values: (u, ticks) => ticks.map(t => `${t}`),
        },
      ],
      legend: { show: false },
    };

    u.current = new uPlot(opts, [xs, ys], ref.current);

    const onResize = () => {
      if (!ref.current) return;
      u.current?.setSize({ width: ref.current.clientWidth, height });
    };
    window.addEventListener('resize', onResize);

    return () => {
      window.removeEventListener('resize', onResize);
      u.current?.destroy();
      u.current = null;
    };
  }, [points, height]);

  if (points.length === 0) {
    return (
      <div
        className="flex items-center justify-center text-slate-400 border border-slate-200 rounded-md"
        style={{ height }}
      >
        Нет данных за выбранный период
      </div>
    );
  }

  return <div ref={ref} className="w-full" />;
}