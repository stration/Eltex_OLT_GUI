import { Link, useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { toast } from 'sonner';
import { OltsApi, OntManageApi, UnactivatedOnt } from '../api/client';
import OntAddModal from '../components/OntAddModal';
import { SkeletonTable } from '../components/Skeleton';
import ErrorState from '../components/ErrorState';

export default function OntUnactivated() {
  const { id } = useParams();
  const oltId = Number(id);
  const qc = useQueryClient();

  const { data: olt } = useQuery({
    queryKey: ['olt', oltId],
    queryFn: () => OltsApi.get(oltId),
  });

  const { data, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: ['unactivated', oltId],
    queryFn: () => OntManageApi.unactivated(oltId),
    refetchInterval: 30_000,
  });

  const [addPreset, setAddPreset] = useState<Partial<UnactivatedOnt> | null>(null);

  const autofindMut = useMutation({
    mutationFn: (enable: boolean) => OntManageApi.autofind(oltId, enable),
    onSuccess: (r, enable) => {
      if (r.ok) {
        toast.success(`Автопоиск ${enable ? 'включён' : 'выключен'} на всех портах`);
        setTimeout(() => qc.invalidateQueries({ queryKey: ['unactivated', oltId] }), 3000);
      } else {
        toast.error('Не удалось переключить автопоиск', {
          description: r.error, duration: 10000,
        });
      }
    },
  });

  const maxPort = (olt?.model || '').endsWith('8X') ? 7 : 3;

  return (
    <div>
      <div className="mb-2 text-sm text-slate-500">
        <Link to="/" className="text-accent-600 hover:text-accent-700 hover:underline">OLT</Link>
        <span className="mx-2">/</span>
        <Link to={`/olts/${oltId}`} className="text-accent-600 hover:text-accent-700 hover:underline">
          {olt?.name || oltId}
        </Link>
        <span className="mx-2">/</span>
        <span className="text-slate-700">Автообнаружение</span>
      </div>

      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-semibold">
          Автообнаружение ONT ({data?.length ?? 0})
        </h1>
        <div className="flex gap-2">
          <button
            onClick={() => autofindMut.mutate(true)}
            disabled={autofindMut.isPending}
            className="btn btn-primary"
          >
            Включить автопоиск
          </button>
          <button
            onClick={() => autofindMut.mutate(false)}
            disabled={autofindMut.isPending}
            className="btn btn-secondary"
          >
            Выключить автопоиск
          </button>
          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className="btn btn-secondary"
          >
            {isFetching ? 'Обновляю…' : 'Обновить'}
          </button>
        </div>
      </div>

      <div className="card overflow-hidden">
        {isError ? (
          <div className="p-4">
            <ErrorState
              title="Не удалось получить список необнаруженных ONT"
              message="OLT не отвечает или CLI недоступен."
              onRetry={() => refetch()}
            />
          </div>
        ) : isLoading ? (
          <SkeletonTable rows={5} cols={7} />
        ) : (
          <table className="w-full text-sm">
            <thead className="text-slate-500 border-b border-slate-200">
              <tr>
                <th className="text-left p-3">Serial</th>
                <th className="text-left p-3">Порт</th>
                <th className="text-left p-3">Статус</th>
                <th className="text-right p-3">RSSI, dBm</th>
                <th className="text-left p-3">Версия</th>
                <th className="text-left p-3">Оборудование</th>
                <th className="p-3"></th>
              </tr>
            </thead>
            <tbody>
              {(data?.length ?? 0) === 0 && (
                <tr>
                  <td colSpan={7} className="p-6 text-center text-slate-400">
                    Необнаруженных ONT нет.<br />
                    <span className="text-xs">
                      Включите автопоиск и подключите ONT к PON-дереву.
                    </span>
                  </td>
                </tr>
              )}
              {data?.map((o, i) => (
                <tr
                  key={`${o.serial}-${i}`}
                  className="border-b border-slate-100 last:border-0 hover:bg-slate-50"
                >
                  <td className="p-3 font-mono">{o.serial}</td>
                  <td className="p-3">{o.gpon_port}</td>
                  <td className="p-3">{o.status}</td>
                  <td className="p-3 text-right font-mono">
                    {o.rssi_db !== null ? o.rssi_db.toFixed(2) : '—'}
                  </td>
                  <td className="p-3">{o.version || '—'}</td>
                  <td className="p-3">{o.equipment_id || '—'}</td>
                  <td className="p-3 text-right">
                    <button
                      onClick={() => setAddPreset(o)}
                      className="btn btn-primary btn-sm"
                    >
                      Добавить
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {addPreset && (
        <OntAddModal
          oltId={oltId}
          maxPort={maxPort}
          preset={addPreset}
          onClose={() => setAddPreset(null)}
        />
      )}
    </div>
  );
}