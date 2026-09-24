import { Link, useParams, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useMemo, useState, useEffect } from 'react';
import { OntsApi, OltsApi, OntMacsApi, Ont } from '../api/client';
import StatusBadge from '../components/StatusBadge';
import OntAddModal from '../components/OntAddModal';
import { SkeletonTable } from '../components/Skeleton';
import ErrorState from '../components/ErrorState';

type SortKey =
  | 'serial'
  | 'ont_id'
  | 'gpon_port'
  | 'status'
  | 'rssi_db'
  | 'version'
  | 'equipment_id'
  | 'description'
  | 'macs';

type SortDir = 'asc' | 'desc';

const PAGE_SIZE = 50;

export default function OntList() {
  const { id } = useParams();
  const oltId = Number(id);
  const [params, setParams] = useSearchParams();

  const [search, setSearch] = useState('');
  const [status, setStatus] = useState(params.get('status') || '');
  const [gponPort, setGponPort] = useState(params.get('gpon_port') || '');
  const [showAdd, setShowAdd] = useState(false);

  const sortKey = (params.get('sort') as SortKey) || 'gpon_port';
  const sortDir = (params.get('dir') as SortDir) || 'asc';
  const page = Math.max(1, Number(params.get('page') || '1'));

  const { data: olt } = useQuery({
    queryKey: ['olt', oltId],
    queryFn: () => OltsApi.get(oltId),
  });
  const maxPort = (olt?.model || '').endsWith('8X') ? 7 : 3;

  const {
    data,
    isLoading,
    isError,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: ['onts', oltId, status, gponPort],
    queryFn: () =>
      OntsApi.list(oltId, {
        status: status || undefined,
        gpon_port: gponPort ? Number(gponPort) : undefined,
      }),
    refetchInterval: 30_000,
  });

  const {
    data: macsByOnt,
    refetch: refetchMacs,
    isFetching: macsFetching,
  } = useQuery({
    queryKey: ['onts-macs-summary', oltId],
    queryFn: () => OntMacsApi.summary(oltId),
    refetchInterval: 5 * 60_000,
    staleTime: 2 * 60_000,
  });

  // ---- Фильтр по поиску ---------------------------------------------------
  const filtered = useMemo(() => {
    if (!data) return [];
    if (!search.trim()) return data;
    const n = search.toLowerCase();
    return data.filter(
      o =>
        o.serial.toLowerCase().includes(n) ||
        (o.description || '').toLowerCase().includes(n) ||
        (o.equipment_id || '').toLowerCase().includes(n),
    );
  }, [data, search]);

  // ---- Сортировка ---------------------------------------------------------
  const sorted = useMemo(() => {
    const arr = [...filtered];
    const dir = sortDir === 'asc' ? 1 : -1;

    const cmp = (a: Ont, b: Ont): number => {
      const macsA = macsByOnt?.[`${a.gpon_port}/${a.ont_id}`] || [];
      const macsB = macsByOnt?.[`${b.gpon_port}/${b.ont_id}`] || [];

      switch (sortKey) {
        case 'serial':
          return a.serial.localeCompare(b.serial) * dir;
        case 'ont_id':
          return (a.ont_id - b.ont_id) * dir;
        case 'gpon_port':
          return (
            (a.gpon_port - b.gpon_port || a.ont_id - b.ont_id) * dir
          );
        case 'status':
          return a.status.localeCompare(b.status) * dir;
        case 'rssi_db': {
          const av = a.rssi_db ?? -Infinity;
          const bv = b.rssi_db ?? -Infinity;
          return (av - bv) * dir;
        }
        case 'version':
          return (a.version || '').localeCompare(b.version || '') * dir;
        case 'equipment_id':
          return (
            (a.equipment_id || '').localeCompare(b.equipment_id || '') * dir
          );
        case 'description':
          return (
            (a.description || '').localeCompare(b.description || '') * dir
          );
        case 'macs': {
          const av = macsA.length;
          const bv = macsB.length;
          if (av !== bv) return (av - bv) * dir;
          return (
            (macsA[0] || '').localeCompare(macsB[0] || '') * dir
          );
        }
        default:
          return 0;
      }
    };

    return arr.sort(cmp);
  }, [filtered, sortKey, sortDir, macsByOnt]);

  // ---- Пагинация ----------------------------------------------------------
  const totalPages = Math.max(1, Math.ceil(sorted.length / PAGE_SIZE));
  const currentPage = Math.min(page, totalPages);
  const pageStart = (currentPage - 1) * PAGE_SIZE;
  const pageEnd = pageStart + PAGE_SIZE;
  const paged = sorted.slice(pageStart, pageEnd);

  // Сброс страницы при смене фильтра/поиска
  useEffect(() => {
    if (page !== 1 && (search || status || gponPort)) {
      const next = new URLSearchParams(params);
      next.set('page', '1');
      setParams(next, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, status, gponPort]);

  const applyFilter = (key: 'status' | 'gpon_port', val: string) => {
    const next = new URLSearchParams(params);
    if (val) next.set(key, val);
    else next.delete(key);
    next.set('page', '1');
    setParams(next, { replace: true });
  };

  const setSort = (key: SortKey) => {
    const next = new URLSearchParams(params);
    if (sortKey === key) {
      next.set('dir', sortDir === 'asc' ? 'desc' : 'asc');
    } else {
      next.set('sort', key);
      next.set('dir', 'asc');
    }
    next.set('page', '1');
    setParams(next, { replace: true });
  };

  const setPage = (p: number) => {
    const next = new URLSearchParams(params);
    next.set('page', String(p));
    setParams(next, { replace: true });
  };

  const exportCsv = () => {
    const headers = [
      'Serial', 'ONT ID', 'GPON-port', 'Status', 'RSSI[dBm]',
      'Version', 'EquipmentID', 'Description', 'MACs',
    ];
    const rows = sorted.map(o => {
      const macs = macsByOnt?.[`${o.gpon_port}/${o.ont_id}`] || [];
      return [
        o.serial, o.ont_id, o.gpon_port, o.status,
        o.rssi_db ?? '', o.version ?? '', o.equipment_id ?? '', o.description ?? '',
        macs.join(' '),
      ];
    });
    const csv = [headers, ...rows]
      .map(r => r.map(v => `"${String(v).replace(/"/g, '""')}"`).join(','))
      .join('\n');
    const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `olt-${oltId}-onts-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div>
      <div className="mb-2 text-sm text-slate-500">
        <Link to="/" className="text-accent-600 hover:text-accent-700 hover:underline">OLT</Link>
        <span className="mx-2">/</span>
        <Link to={`/olts/${oltId}`} className="text-accent-600 hover:text-accent-700 hover:underline">
          {olt?.name || oltId}
        </Link>
        <span className="mx-2">/</span>
        <span className="text-slate-700">ONT</span>
      </div>

      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-semibold">
          ONT ({sorted.length}
          {sorted.length !== (data?.length ?? 0) && ` из ${data?.length}`})
        </h1>
        <div className="flex gap-2">
          <button
            onClick={() => setShowAdd(true)}
            className="btn btn-primary"
          >
            + Добавить ONT
          </button>
          <button
            onClick={() => { refetch(); refetchMacs(); }}
            disabled={isFetching || macsFetching}
            className="btn btn-secondary"
          >
            {isFetching || macsFetching ? 'Обновляю…' : 'Обновить'}
          </button>
          <button
            onClick={exportCsv}
            className="btn btn-secondary"
          >
            Экспорт CSV
          </button>
        </div>
      </div>

      <div className="flex gap-3 mb-4">
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Поиск по серийнику, описанию, оборудованию…"
          className="input-base flex-1"
        />
        <select
          value={status}
          onChange={e => { setStatus(e.target.value); applyFilter('status', e.target.value); }}
          className="select-base"
        >
          <option value="">Все статусы</option>
          <option value="OK">OK</option>
          <option value="OFFLINE">OFFLINE</option>
          <option value="FAILED">FAILED</option>
          <option value="BLOCKED">BLOCKED</option>
          <option value="DISABLED">DISABLED</option>
        </select>
        <select
          value={gponPort}
          onChange={e => { setGponPort(e.target.value); applyFilter('gpon_port', e.target.value); }}
          className="select-base"
        >
          <option value="">Все порты</option>
          {Array.from({ length: maxPort + 1 }, (_, p) => (
            <option key={p} value={p}>GPON-{p}</option>
          ))}
        </select>
      </div>

      <div className="card overflow-hidden">
        {isError ? (
          <div className="p-4">
            <ErrorState
              title="Не удалось загрузить список ONT"
              message="OLT не отвечает или backend вернул ошибку."
              onRetry={() => refetch()}
            />
          </div>
        ) : isLoading ? (
          <SkeletonTable rows={8} cols={9} />
        ) : (
          <table className="w-full text-sm">
            <thead className="text-slate-500 border-b border-slate-200">
              <tr>
                <SortTh
                  label="Serial"
                  sortKey="serial"
                  currentKey={sortKey}
                  dir={sortDir}
                  onClick={setSort}
                />
                <SortTh
                  label="ONT ID"
                  sortKey="ont_id"
                  currentKey={sortKey}
                  dir={sortDir}
                  onClick={setSort}
                />
                <SortTh
                  label="Порт"
                  sortKey="gpon_port"
                  currentKey={sortKey}
                  dir={sortDir}
                  onClick={setSort}
                />
                <SortTh
                  label="Статус"
                  sortKey="status"
                  currentKey={sortKey}
                  dir={sortDir}
                  onClick={setSort}
                />
                <SortTh
                  label="RSSI, dBm"
                  sortKey="rssi_db"
                  currentKey={sortKey}
                  dir={sortDir}
                  onClick={setSort}
                  align="right"
                />
                <SortTh
                  label="Версия"
                  sortKey="version"
                  currentKey={sortKey}
                  dir={sortDir}
                  onClick={setSort}
                />
                <SortTh
                  label="Оборудование"
                  sortKey="equipment_id"
                  currentKey={sortKey}
                  dir={sortDir}
                  onClick={setSort}
                />
                <SortTh
                  label="Описание"
                  sortKey="description"
                  currentKey={sortKey}
                  dir={sortDir}
                  onClick={setSort}
                />
                <SortTh
                  label="MAC"
                  sortKey="macs"
                  currentKey={sortKey}
                  dir={sortDir}
                  onClick={setSort}
                />
              </tr>
            </thead>
            <tbody>
              {paged.length === 0 && (
                <tr>
                  <td colSpan={9} className="p-3 text-slate-400">
                    Ничего не найдено
                  </td>
                </tr>
              )}
              {paged.map(o => {
                const macs = macsByOnt?.[`${o.gpon_port}/${o.ont_id}`] || [];
                const display = macs.length === 0
                  ? '—'
                  : macs.length === 1
                  ? macs[0]
                  : `${macs[0]} +${macs.length - 1}`;
                const title = macs.length > 1 ? macs.join(', ') : undefined;
                return (
                  <tr
                    key={o.id}
                    className="border-b border-slate-100 last:border-0 hover:bg-slate-50"
                  >
                    <td className="p-3 font-mono">
                      <Link
                        to={`/olts/${oltId}/onts/${o.gpon_port}/${o.ont_id}`}
                        className="text-accent-600 hover:text-accent-700 hover:underline"
                      >
                        {o.serial}
                      </Link>
                    </td>
                    <td className="p-3">{o.ont_id}</td>
                    <td className="p-3">{o.gpon_port}</td>
                    <td className="p-3"><StatusBadge status={o.status} /></td>
                    <td className="p-3 text-right font-mono">
                      {o.rssi_db !== null ? o.rssi_db.toFixed(2) : '—'}
                    </td>
                    <td className="p-3">{o.version || '—'}</td>
                    <td className="p-3">{o.equipment_id || '—'}</td>
                    <td className="p-3 max-w-[200px] truncate" title={o.description || ''}>
                      {o.description || '—'}
                    </td>
                    <td className="p-3 font-mono text-xs" title={title}>
                      {display}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {!isLoading && !isError && sorted.length > PAGE_SIZE && (
        <Pagination
          page={currentPage}
          totalPages={totalPages}
          total={sorted.length}
          pageStart={pageStart}
          pageEnd={pageEnd}
          onChange={setPage}
        />
      )}

      {showAdd && (
        <OntAddModal oltId={oltId} maxPort={maxPort} onClose={() => setShowAdd(false)} />
      )}
    </div>
  );
}

// ---- Сортируемый заголовок -----------------------------------------------

function SortTh({
  label,
  sortKey,
  currentKey,
  dir,
  onClick,
  align,
}: {
  label: string;
  sortKey: SortKey;
  currentKey: SortKey;
  dir: SortDir;
  onClick: (k: SortKey) => void;
  align?: 'left' | 'right';
}) {
  const active = currentKey === sortKey;
  const arrow = active ? (dir === 'asc' ? '↑' : '↓') : '';
  return (
    <th
      className={`p-3 cursor-pointer select-none hover:text-slate-700 ${
        align === 'right' ? 'text-right' : 'text-left'
      } ${active ? 'text-slate-900 font-medium' : ''}`}
      onClick={() => onClick(sortKey)}
      title="Клик — сортировать"
    >
      <span className="inline-flex items-center gap-1">
        {label}
        <span className="text-xs opacity-60">{arrow}</span>
      </span>
    </th>
  );
}

// ---- Пагинация -----------------------------------------------------------

function Pagination({
  page,
  totalPages,
  total,
  pageStart,
  pageEnd,
  onChange,
}: {
  page: number;
  totalPages: number;
  total: number;
  pageStart: number;
  pageEnd: number;
  onChange: (p: number) => void;
}) {
  const pages = buildPageList(page, totalPages);

  return (
    <div className="mt-4 flex items-center justify-between text-sm">
      <div className="text-slate-500">
        Показано {pageStart + 1}–{Math.min(pageEnd, total)} из {total}
      </div>
      <div className="flex items-center gap-1">
        <button
          onClick={() => onChange(page - 1)}
          disabled={page <= 1}
          className="btn btn-secondary btn-sm"
        >
          ← Назад
        </button>
        {pages.map((p, i) =>
          p === '…' ? (
            <span key={`gap-${i}`} className="px-2 text-slate-400">
              …
            </span>
          ) : (
            <button
              key={p}
              onClick={() => onChange(p)}
              className={`btn btn-sm ${
                p === page
                  ? 'btn-primary'
                  : 'btn-secondary'
              }`}
            >
              {p}
            </button>
          ),
        )}
        <button
          onClick={() => onChange(page + 1)}
          disabled={page >= totalPages}
          className="btn btn-secondary btn-sm"
        >
          Вперёд →
        </button>
      </div>
    </div>
  );
}

function buildPageList(page: number, totalPages: number): (number | '…')[] {
  if (totalPages <= 7) {
    return Array.from({ length: totalPages }, (_, i) => i + 1);
  }
  const result: (number | '…')[] = [1];
  const start = Math.max(2, page - 1);
  const end = Math.min(totalPages - 1, page + 1);

  if (start > 2) result.push('…');
  for (let i = start; i <= end; i++) result.push(i);
  if (end < totalPages - 1) result.push('…');
  result.push(totalPages);
  return result;
}