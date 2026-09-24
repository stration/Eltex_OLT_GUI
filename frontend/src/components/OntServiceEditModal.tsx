import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import {
  OntServiceConfig, OntServiceEditPayload,
  OntManageApi, OntServicesApi,
} from '../api/client';
import ConfirmModal from './ConfirmModal';

interface Props {
  oltId: number;
  gponPort: number;
  ontId: number;
  service: OntServiceConfig;
  currentUtilization: boolean;
  onClose: () => void;
}

export default function OntServiceEditModal({
  oltId, gponPort, ontId, service, currentUtilization, onClose,
}: Props) {
  const qc = useQueryClient();

  const [pCC, setPCC] = useState(service.profile_cross_connect ?? '');
  const [pDba, setPDba] = useState(service.profile_dba ?? '');

  const [customEnabled, setCustomEnabled] = useState(service.custom_cross_connect === 'enabled');
  const [cvid, setCvid] = useState<string>(service.custom_cvid?.toString() ?? '');
  const [svid, setSvid] = useState<string>(service.custom_svid?.toString() ?? '');
  const [cos, setCos] = useState<string>(service.custom_cos?.toString() ?? '');

  const [uvid, setUvid] = useState(service.selective_tunnel_user_vlans ?? '');
  const [utilization, setUtilization] = useState(currentUtilization);

  const [confirmDelete, setConfirmDelete] = useState(false);

  const { data: profilesCC = [] } = useQuery({
    queryKey: ['profiles', oltId, 'cross-connect'],
    queryFn: () => OntManageApi.profiles(oltId, 'cross-connect'),
    staleTime: 5 * 60_000,
  });
  const { data: profilesDba = [] } = useQuery({
    queryKey: ['profiles', oltId, 'dba'],
    queryFn: () => OntManageApi.profiles(oltId, 'dba'),
    staleTime: 5 * 60_000,
  });

  const saveMut = useMutation({
    mutationFn: (payload: OntServiceEditPayload) =>
      OntServicesApi.update(oltId, gponPort, ontId, service.service_id, payload),
    onSuccess: (r) => {
      if (r.ok) {
        toast.success(
          r.changes.length > 0
            ? `Применено изменений: ${r.changes.length}`
            : 'Изменений нет',
        );
        qc.invalidateQueries({ queryKey: ['ont-config', oltId, gponPort, ontId] });
        onClose();
      } else {
        toast.error('Не удалось применить', {
          description: r.error || 'Неизвестная ошибка',
          duration: 12000,
        });
      }
    },
    onError: (e: any) =>
      toast.error(e?.response?.data?.detail || 'Ошибка запроса'),
  });

  const delMut = useMutation({
    mutationFn: () =>
      OntServicesApi.remove(oltId, gponPort, ontId, service.service_id),
    onSuccess: (r) => {
      if (r.ok) {
        toast.success(`Сервис ${service.service_id} удалён`);
        qc.invalidateQueries({ queryKey: ['ont-config', oltId, gponPort, ontId] });
        onClose();
      } else {
        toast.error('Не удалось удалить', { description: r.error, duration: 12000 });
      }
    },
  });

  const submit = () => {
    const payload: OntServiceEditPayload = {
      profile_cross_connect: pCC || null,
      profile_dba: pDba || null,
      custom_enabled: customEnabled,
      utilization_enable: utilization,
    };
    if (customEnabled) {
      if (cvid) payload.cvid = Number(cvid);
      if (svid) payload.svid = Number(svid);
      if (cos !== '') payload.cos = Number(cos);
    }
    payload.selective_tunnel_uvid = uvid.trim();
    saveMut.mutate(payload);
  };

  return (
    <div className="fixed inset-0 bg-black/30 flex items-start justify-center z-50 overflow-auto py-8">
      <div className="bg-white rounded-lg p-5 w-[640px] shadow-xl">
        <h2 className="text-lg font-semibold mb-4">
          Сервис [{service.service_id}] — ONT {gponPort}/{ontId}
        </h2>

        <div className="grid grid-cols-2 gap-3 mb-5">
          <div>
            <label className="block text-sm text-slate-600 mb-1">Profile cross-connect</label>
            <select
              value={pCC}
              onChange={e => setPCC(e.target.value)}
              className="select-base w-full"
            >
              <option value="">— не назначен —</option>
              {profilesCC.map(p => (
                <option key={p.name} value={p.name}>{p.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm text-slate-600 mb-1">Profile dba</label>
            <select
              value={pDba}
              onChange={e => setPDba(e.target.value)}
              className="select-base w-full"
            >
              <option value="">— не назначен —</option>
              {profilesDba.map(p => (
                <option key={p.name} value={p.name}>{p.name}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="mb-5">
          <label className="flex items-center gap-2 text-sm cursor-pointer mb-2">
            <input
              type="checkbox"
              checked={customEnabled}
              onChange={e => setCustomEnabled(e.target.checked)}
              className="rounded border-slate-300 text-accent-600 focus:ring-accent-500"
            />
            <span className="font-medium text-slate-700">Custom cross-connect</span>
          </label>
          {customEnabled && (
            <div className="grid grid-cols-3 gap-3 pl-6">
              <div>
                <label className="block text-xs text-slate-500 mb-1">c-vid (1..4094)</label>
                <input
                  type="number" min={1} max={4094}
                  value={cvid}
                  onChange={e => setCvid(e.target.value)}
                  className="input-base font-mono"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">s-vid (1..4094)</label>
                <input
                  type="number" min={1} max={4094}
                  value={svid}
                  onChange={e => setSvid(e.target.value)}
                  className="input-base font-mono"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">cos (0..7)</label>
                <input
                  type="number" min={0} max={7}
                  value={cos}
                  onChange={e => setCos(e.target.value)}
                  className="input-base font-mono"
                />
              </div>
            </div>
          )}
        </div>

        <div className="mb-5">
          <label className="block text-sm text-slate-600 mb-1">
            Selective-tunnel uvid
          </label>
          <input
            value={uvid}
            onChange={e => setUvid(e.target.value)}
            placeholder="например: 300,301,400-405"
            className="input-base font-mono"
          />
          <p className="text-xs text-slate-400 mt-1">
            Через запятую, диапазоны через дефис. Пусто — снять все.
          </p>
        </div>

        <div className="mb-5">
          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <input
              type="checkbox"
              checked={utilization}
              onChange={e => setUtilization(e.target.checked)}
              className="rounded border-slate-300 text-accent-600 focus:ring-accent-500"
            />
            Collect utilization statistics (сбор статистики утилизации)
          </label>
        </div>

        <div className="flex justify-between gap-2 mt-6">
          <button
            onClick={() => setConfirmDelete(true)}
            disabled={delMut.isPending || saveMut.isPending}
            className="btn btn-danger"
          >
            {delMut.isPending ? 'Удаляю…' : 'Удалить сервис'}
          </button>
          <div className="flex gap-2">
            <button
              onClick={onClose}
              disabled={saveMut.isPending}
              className="btn btn-secondary"
            >
              Отмена
            </button>
            <button
              onClick={submit}
              disabled={saveMut.isPending}
              className="btn btn-primary"
            >
              {saveMut.isPending ? 'Применяю…' : 'Применить'}
            </button>
          </div>
        </div>
      </div>

      <ConfirmModal
        open={confirmDelete}
        title="Удаление сервиса"
        message={`УДАЛИТЬ СЕРВИС [${service.service_id}] У ONT ${gponPort}/${ontId}?\n\nСервис будет удалён из конфигурации ONT. Действие необратимо.`}
        variant="danger"
        confirmLabel="Удалить"
        busy={delMut.isPending}
        onConfirm={() => { setConfirmDelete(false); delMut.mutate(); }}
        onCancel={() => setConfirmDelete(false)}
      />
    </div>
  );
}