import { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { OltsApi, Olt, OntsApi, GlobalOntSearchItem, DashboardApi } from '../api/client';
import { SkeletonTable } from '../components/Skeleton';
import ErrorState from '../components/ErrorState';
import ConfirmModal from '../components/ConfirmModal';
import { formatRelativeTime } from '../lib/format';

function StatusBadge({ status }: { status: Olt['status'] }) {
  const map = {
    online:  'bg-green-100 text-green-800',
    offline: 'bg-red-100 text-red-800',
    unknown: 'bg-slate-100 text-slate-700',
  } as const;
  const label = { online: 'online', offline: 'offline', unknown: '—' } as const;
  return <span className={`px-2 py-0.5 rounded text-xs ${map[status]}`}>{label[status]}</span>;
}

function OntStatusBadge({ status }: { status: string }) {
  const cls =
    status === 'OK'   ? 'bg-green-100 text-green-800'
  : status === 'OFFLINE' ? 'bg-red-100 text-red-800'
  : 'bg-slate-100 text-slate-700';
  return <span className={`px-2 py-0.5 rounded text-xs ${cls}`}>{status}</span>;
}

interface PendingDelete {
  id: number;
  ip: string;
}

// ---- Хук debounce -------------------------------------------------------

function useDebounced<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(t);
  }, [value, delayMs]);
  return debounced;
}

export default function OltList() {
  const qc = useQueryClient();
  const navigate = useNavigate();

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['olts'],
    queryFn: OltsApi.list,
  });

  // ---- Сводка для метрик ----
  const { data: summary } = useQuery({
    queryKey: ['dashboard-summary'],
    queryFn: DashboardApi.summary,
    refetchInterval: 30_000,
  });

  // ---- Глобальный поиск ONT ----
  const [searchInput, setSearchInput] = useState('');
  const searchQuery = useDebounced(searchInput.trim(), 300);

  const {
    data: searchData,
    isFetching: searchFetching,
    isError: searchError,
  } = useQuery({
    queryKey: ['onts-search', searchQuery],
    queryFn: () => OntsApi.globalSearch(searchQuery, 200),
    enabled: searchQuery.length >= 2,
    staleTime: 15_000,
  });

  const searchActive = searchQuery.length >= 2;

  const [showAdd, setShowAdd] = useState(false);
  const [ip, setIp] = useState('');
  const [name, setName] = useState('');
  const [pendingDelete, setPendingDelete] = useState<PendingDelete | null>(null);
  const [confirmIp, setConfirmIp] = useState('');

  const addMut = useMutation({
    mutationFn: () => OltsApi.add(ip.trim(), name.trim() || undefined),
    onSuccess: () => {
      toast.success(`OLT ${ip} добавлен`);
      setShowAdd(false); setIp(''); setName('');
      qc.invalidateQueries({ queryKey: ['olts'] });
      qc.invalidateQueries({ queryKey: ['dashboard-summary'] });
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || 'Ошибка добавления'),
  });

  const delMut = useMutation({
    mutationFn: (id: number) => OltsApi.remove(id),
    onSuccess: () => {
      toast.success('Удалено');
      setPendingDelete(null);
      setConfirmIp('');
      qc.invalidateQueries({ queryKey: ['olts'] });
      qc.invalidateQueries({ queryKey: ['dashboard-summary'] });
    },
    onError: (e: any) => {
      toast.error(e?.response?.data?.detail || 'Ошибка удаления');
    },
  });

  const checkMut = useMutation({
    mutationFn: (id: number) => OltsApi.check(id),
    onSuccess: (r) => {
      toast.message(`Проверка ${r.ip}`, {
        description: `ping ${r.ping_ok ? r.ping_ms + ' мс' : 'нет'}, SNMP ${r.snmp_ok ? 'ok' : 'нет'}${r.model ? ', ' + r.model : ''}`,
      });
      qc.invalidateQueries({ queryKey: ['olts'] });
      qc.invalidateQueries({ queryKey: ['dashboard-summary'] });
    },
  });

  const checkAllMut = useMutation({
    mutationFn: OltsApi.checkAll,
    onSuccess: () => {
      toast.success('Проверка завершена');
      qc.invalidateQueries({ queryKey: ['olts'] });
      qc.invalidateQueries({ queryKey: ['dashboard-summary'] });
    },
  });

  const openDelete = (o: Olt) => {
    setPendingDelete({ id: o.id, ip: o.ip });
    setConfirmIp('');
  };

  const runDelete = () => {
    if (!pendingDelete) return;
    if (confirmIp.trim() !== pendingDelete.ip) {
      toast.error('IP не совпадает', { description: 'Введите точный IP-адрес OLT для подтверждения.' });
      return;
    }
    delMut.mutate(pendingDelete.id);
  };

  const canConfirmDelete =
    pendingDelete !== null && confirmIp.trim() === pendingDelete.ip;

  const openOnt = (item: GlobalOntSearchItem) => {
    navigate(`/olts/${item.olt_id}/onts/${item.gpon_port}/${item.ont_id}`);
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-semibold">OLT</h1>
        <div className="flex gap-2">
          <button
            onClick={() => checkAllMut.mutate()}
            disabled={checkAllMut.isPending}
            className="btn btn-secondary"
          >
            {checkAllMut.isPending ? 'Проверяю…' : 'Проверить все'}
          </button>
          <button
            onClick={() => setShowAdd(true)}
            className="btn btn-primary"
          >
            + Добавить OLT
          </button>
        </div>
      </div>

      {/* ---- Метрики ---- */}
      {summary && (
        <section className="grid grid-cols-2 gap-4 mb-4">
          <MetricCard
            title="OLT"
            value={summary.olts_total}
            subtitle={
              <>
                <span className="text-green-700">online: {summary.olts_online}</span>
                {summary.olts_offline > 0 && (
                  <span className="ml-3 text-red-700">offline: {summary.olts_offline}</span>
                )}
              </>
            }
          />
          <MetricCard
            title="ONT"
            value={summary.onts_total}
            subtitle={
              <>
                <span className="text-green-700">OK: {summary.onts_ok}</span>
                {summary.onts_offline > 0 && (
                  <span className="ml-3 text-red-700">offline: {summary.onts_offline}</span>
                )}
                {summary.onts_other > 0 && (
                  <span className="ml-3 text-slate-500">прочие: {summary.onts_other}</span>
                )}
              </>
            }
          />
        </section>
      )}

      {/* ---- Поиск ONT по всем OLT ---- */}
      <div className="card p-3 mb-4">
        <div className="flex items-center gap-3">
          <div className="relative flex-1">
            <input
              value={searchInput}
              onChange={e => setSearchInput(e.target.value)}
              placeholder="Поиск ONT по серийному номеру, описанию или оборудованию…"
              className="input-base pr-8"
            />
            {searchInput && (
              <button
                type="button"
                onClick={() => setSearchInput('')}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                title="Очистить"
              >
                ✕
              </button>
            )}
          </div>
          {searchFetching && (
            <span className="text-xs text-slate-400">поиск…</span>
          )}
        </div>
      </div>

      {/* ---- Результаты поиска ONT ---- */}
      {searchActive ? (
        <div className="card">
          {searchError ? (
            <div className="p-4">
              <ErrorState
                title="Не удалось выполнить поиск"
                message="Backend не отвечает или вернул ошибку."
              />
            </div>
          ) : searchFetching && !searchData ? (
            <SkeletonTable rows={5} cols={7} />
          ) : !searchData || searchData.items.length === 0 ? (
            <div className="p-6 text-center text-slate-400">
              Ничего не найдено по запросу «{searchQuery}»
            </div>
          ) : (
            <>
              <div className="card-header flex items-center text-sm text-slate-500">
                <span className="flex-1">
                  Найдено: {searchData.total}
                  {searchData.total > searchData.items.length && (
                    <span className="ml-2 text-slate-400">
                      (показаны первые {searchData.items.length})
                    </span>
                  )}
                </span>
              </div>
              <table className="w-full text-sm">
                <thead className="text-slate-500 border-b border-slate-200">
                  <tr>
                    <th className="text-left p-3">OLT</th>
                    <th className="text-left p-3">Serial</th>
                    <th className="text-left p-3">Порт / ID</th>
                    <th className="text-left p-3">Статус</th>
                    <th className="text-right p-3">RSSI, dBm</th>
                    <th className="text-left p-3">Оборудование</th>
                    <th className="text-left p-3">Описание</th>
                  </tr>
                </thead>
                <tbody>
                  {searchData.items.map(it => (
                    <tr
                      key={`${it.olt_id}/${it.gpon_port}/${it.ont_id}`}
                      onClick={() => openOnt(it)}
                      className="border-b border-slate-100 last:border-0 hover:bg-slate-50 cursor-pointer"
                    >
                      <td className="p-3">
                        <div className="leading-tight">
                          <div className="font-medium">{it.olt_name}</div>
                          <div className="text-xs text-slate-500 font-mono">
                            {it.olt_ip}
                          </div>
                        </div>
                      </td>
                      <td className="p-3 font-mono text-accent-600 hover:text-accent-700">
                        {it.serial}
                      </td>
                      <td className="p-3 font-mono">
                        {it.gpon_port}/{it.ont_id}
                      </td>
                      <td className="p-3">
                        <OntStatusBadge status={it.status} />
                      </td>
                      <td className="p-3 text-right font-mono">
                        {it.rssi_db !== null && it.rssi_db !== undefined ? (
                          it.rssi_db.toFixed(2)
                        ) : (
                          <span className="text-slate-300">—</span>
                        )}
                      </td>
                      <td className="p-3">{it.equipment_id || '—'}</td>
                      <td className="p-3">{it.description || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </div>
      ) : (
        /* ---- Таблица OLT ---- */
        <div className="card">
          {isError ? (
            <div className="p-4">
              <ErrorState
                title="Не удалось загрузить список OLT"
                message="Backend не отвечает или вернул ошибку."
                onRetry={() => refetch()}
              />
            </div>
          ) : isLoading ? (
            <SkeletonTable rows={5} cols={8} />
          ) : (
            <table className="w-full text-sm">
              <thead className="text-slate-500 border-b border-slate-200">
                <tr>
                  <th className="text-left p-3">IP</th>
                  <th className="text-left p-3">Имя</th>
                  <th className="text-left p-3">Модель</th>
                  <th className="text-left p-3">Ревизия</th>
                  <th className="text-left p-3">Статус</th>
                  <th className="text-left p-3">ping, мс</th>
                  <th className="text-left p-3">Последний отклик</th>
                  <th className="p-3"></th>
                </tr>
              </thead>
              <tbody>
                {data?.length === 0 && (
                  <tr>
                    <td className="p-3 text-slate-400" colSpan={8}>
                      OLT не добавлены
                    </td>
                  </tr>
                )}
                {data?.map(o => (
                  <tr key={o.id} className="border-b border-slate-100 last:border-0 hover:bg-slate-50">
                    <td className="p-3 font-mono">
                      <Link to={`/olts/${o.id}`} className="text-accent-600 hover:text-accent-700 hover:underline">
                        {o.ip}
                      </Link>
                    </td>
                    <td className="p-3">
                      <Link to={`/olts/${o.id}`} className="text-accent-600 hover:text-accent-700 hover:underline">
                        {o.name || '—'}
                      </Link>
                    </td>
                    <td className="p-3">{o.model || '—'}</td>
                    <td className="p-3">{o.hw_revision || '—'}</td>
                    <td className="p-3"><StatusBadge status={o.status} /></td>
                    <td className="p-3">{o.last_ping_ms ?? '—'}</td>
                    <td className="p-3" title={o.last_seen_at ?? undefined}>
                      {formatRelativeTime(o.last_seen_at)}
                    </td>
                    <td className="p-3 text-right whitespace-nowrap">
                      <button
                        onClick={() => checkMut.mutate(o.id)}
                        disabled={checkMut.isPending}
                        className="btn btn-secondary btn-sm mr-2"
                      >
                        Проверить
                      </button>
                      <button
                        onClick={() => openDelete(o)}
                        className="btn btn-danger btn-sm"
                      >
                        Удалить
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {showAdd && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-5 w-[420px] shadow-xl">
            <h2 className="text-lg font-semibold mb-4">Добавить OLT</h2>

            <label className="block text-sm mb-1 text-slate-600">IP-адрес</label>
            <input
              value={ip}
              onChange={e => setIp(e.target.value)}
              placeholder="192.168.1.2"
              className="input-base font-mono mb-3"
            />

            <label className="block text-sm mb-1 text-slate-600">Имя (необязательно)</label>
            <input
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="Узел №1"
              className="input-base mb-4"
            />

            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowAdd(false)}
                className="btn btn-secondary"
              >
                Отмена
              </button>
              <button
                onClick={() => addMut.mutate()}
                disabled={!ip || addMut.isPending}
                className="btn btn-primary"
              >
                {addMut.isPending ? 'Добавляю…' : 'Добавить'}
              </button>
            </div>
          </div>
        </div>
      )}

      {pendingDelete && (
        <ConfirmModal
          open={true}
          title="Удаление OLT"
          message={`УДАЛИТЬ OLT ${pendingDelete.ip} ИЗ СПИСКА?\n\nЭто удалит запись из базы и остановит опрос. Данные на самой OLT не изменятся.\n\nДля подтверждения введите IP-адрес OLT ниже.`}
          variant="danger"
          confirmLabel={canConfirmDelete ? 'Удалить' : 'Введите IP для подтверждения'}
          busy={delMut.isPending}
          onConfirm={runDelete}
          onCancel={() => {
            setPendingDelete(null);
            setConfirmIp('');
          }}
        >
          <input
            value={confirmIp}
            onChange={e => setConfirmIp(e.target.value)}
            placeholder={pendingDelete.ip}
            className="input-base font-mono mt-3"
            autoFocus
          />
        </ConfirmModal>
      )}
    </div>
  );
}

// ---- Метрика -----------------------------------------------------------

function MetricCard({
  title,
  value,
  subtitle,
}: {
  title: string;
  value: number | string;
  subtitle?: React.ReactNode;
}) {
  return (
    <div className="card p-4">
      <div className="text-sm text-slate-500">{title}</div>
      <div className="text-3xl font-semibold mt-1 text-slate-900">{value}</div>
      {subtitle && (
        <div className="text-xs mt-1">{subtitle}</div>
      )}
    </div>
  );
}