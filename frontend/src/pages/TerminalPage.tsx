import { useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Terminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import '@xterm/xterm/css/xterm.css';
import { OltsApi } from '../api/client';

type Status = 'disconnected' | 'connecting' | 'connected' | 'error';

export default function TerminalPage() {
  const { data: olts = [] } = useQuery({ queryKey: ['olts'], queryFn: OltsApi.list });

  const [searchParams, setSearchParams] = useSearchParams();
  const presetOltId = searchParams.get('olt');

  const [oltId, setOltId] = useState<number | ''>(
    presetOltId ? Number(presetOltId) : ''
  );
  const [status, setStatus] = useState<Status>('disconnected');
  const [error, setError] = useState('');

  const containerRef = useRef<HTMLDivElement | null>(null);
  const xtermRef = useRef<Terminal | null>(null);
  const fitAddonRef = useRef<FitAddon | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  // Инициализация xterm — один раз
  useEffect(() => {
    if (!containerRef.current || xtermRef.current) return;

    const term = new Terminal({
      fontFamily: 'Consolas, Menlo, "DejaVu Sans Mono", monospace',
      fontSize: 14,
      cursorBlink: true,
      convertEol: false,
      scrollback: 5000,
      theme: {
        background: '#0b1220',
        foreground: '#e5e7eb',
        cursor: '#e5e7eb',
        selectionBackground: '#334155',
      },
    });
    const fit = new FitAddon();
    term.loadAddon(fit);
    term.open(containerRef.current);

    setTimeout(() => {
      try { fit.fit(); } catch {}
    }, 50);

    term.onData((data) => {
      const ws = wsRef.current;
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'input', data }));
      }
    });

    term.onResize(({ cols, rows }) => {
      const ws = wsRef.current;
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'resize', cols, rows }));
      }
    });

    xtermRef.current = term;
    fitAddonRef.current = fit;

    return () => {
      try { term.dispose(); } catch {}
      xtermRef.current = null;
      fitAddonRef.current = null;
    };
  }, []);

  // Синхронизация с URL: если ?olt= меняется — обновляем локальный oltId
  useEffect(() => {
    const v = searchParams.get('olt');
    setOltId(v ? Number(v) : '');
  }, [searchParams]);

  // Ресайз окна
  useEffect(() => {
    const onWinResize = () => {
      try { fitAddonRef.current?.fit(); } catch {}
    };
    window.addEventListener('resize', onWinResize);
    return () => window.removeEventListener('resize', onWinResize);
  }, []);

  const disconnect = () => {
    const ws = wsRef.current;
    wsRef.current = null;
    if (ws) {
      try { ws.close(); } catch {}
    }
    setStatus('disconnected');
  };

  const connect = () => {
    if (!oltId || !xtermRef.current) return;

    disconnect();
    setError('');
    setStatus('connecting');
    xtermRef.current.clear();
    xtermRef.current.writeln(`\x1b[36mПодключение к OLT #${oltId}…\x1b[0m`);

    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const url = `${proto}://${window.location.hostname}:8765/ws/olts/${oltId}/terminal`;
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      setStatus('connected');
      if (xtermRef.current) {
        ws.send(JSON.stringify({
          type: 'resize',
          cols: xtermRef.current.cols,
          rows: xtermRef.current.rows,
        }));
      }
    };

    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        if (msg.type === 'output') {
          xtermRef.current?.write(msg.data);
        } else if (msg.type === 'error') {
          setStatus('error');
          setError(msg.message);
          xtermRef.current?.writeln(
            `\r\n\x1b[31m[Ошибка] ${msg.message}\x1b[0m`,
          );
        }
      } catch (e) {
        console.error('ws msg', e, ev.data);
      }
    };

    ws.onerror = () => {
      setStatus('error');
      setError('WebSocket error');
    };

    ws.onclose = () => {
      if (wsRef.current === ws) {
        setStatus('disconnected');
        xtermRef.current?.writeln('\r\n\x1b[33m[Соединение закрыто]\x1b[0m');
      }
    };
  };

  const isActive = status === 'connected' || status === 'connecting';
  const statusText =
    status === 'disconnected' ? 'не подключено'
    : status === 'connecting' ? 'подключение…'
    : status === 'connected' ? 'активно'
    : `ошибка: ${error}`;

  return (
    <div>
      <h1 className="text-xl font-semibold mb-4">Терминал CLI</h1>

      <div className="flex gap-3 items-end mb-3 flex-wrap">
        <div>
          <label className="block text-sm text-slate-600 mb-1">OLT</label>
          <select
            value={oltId}
            onChange={e => {
              const v = e.target.value ? Number(e.target.value) : '';
              setOltId(v);
              const next = new URLSearchParams(searchParams);
              if (v === '') next.delete('olt');
              else next.set('olt', String(v));
              setSearchParams(next, { replace: true });
            }}
            disabled={isActive}
            className="select-base w-72"
          >
            <option value="">— выберите OLT —</option>
            {olts.map(o => (
              <option key={o.id} value={o.id}>
                {o.ip}{o.name ? ` — ${o.name}` : ''}
              </option>
            ))}
          </select>
        </div>

        {isActive ? (
          <button
            onClick={disconnect}
            className="btn btn-danger"
          >
            Отключиться
          </button>
        ) : (
          <button
            onClick={connect}
            disabled={!oltId}
            className="btn btn-primary"
          >
            Подключиться
          </button>
        )}

        <div className="text-sm text-slate-500 ml-2">
          Статус: {statusText}
        </div>
      </div>

      <div
        ref={containerRef}
        className="rounded-lg overflow-hidden border border-slate-700"
        style={{
          height: 'calc(100vh - 220px)',
          minHeight: 400,
          background: '#0b1220',
        }}
      />
    </div>
  );
}