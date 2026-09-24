import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { OntManageApi, UnactivatedOnt } from '../api/client';

interface Props {
  oltId: number;
  maxPort: number;
  preset?: Partial<UnactivatedOnt>;
  onClose: () => void;
}

export default function OntAddModal({ oltId, maxPort, preset, onClose }: Props) {
  const qc = useQueryClient();

  const [gponPort, setGponPort] = useState<number>(preset?.gpon_port ?? 0);
  const [ontId, setOntId] = useState<number | ''>('');
  const [serial, setSerial] = useState(preset?.serial ?? '');
  const [description, setDescription] = useState('');
  const [template, setTemplate] = useState('');
  const [pCC, setPCC] = useState('');
  const [pDba, setPDba] = useState('');
  const [pPorts, setPPorts] = useState('');
  const [pMgmt, setPMgmt] = useState('');

  const templateActive = !!template;
  const profilesDisabled = templateActive;

  // ---- Queries ----
  const { data: templates = [] } = useQuery({
    queryKey: ['templates', oltId],
    queryFn: () => OntManageApi.templates(oltId),
    staleTime: 5 * 60_000,
  });

  const { data: profilesCC = [] } = useQuery({
    queryKey: ['profiles', oltId, 'cross-connect'],
    queryFn: () => OntManageApi.profiles(oltId, 'cross-connect'),
    staleTime: 5 * 60_000,
    enabled: !templateActive,
  });

  const { data: profilesDba = [] } = useQuery({
    queryKey: ['profiles', oltId, 'dba'],
    queryFn: () => OntManageApi.profiles(oltId, 'dba'),
    staleTime: 5 * 60_000,
    enabled: !templateActive,
  });

  const { data: profilesPorts = [] } = useQuery({
    queryKey: ['profiles', oltId, 'ports'],
    queryFn: () => OntManageApi.profiles(oltId, 'ports'),
    staleTime: 5 * 60_000,
    enabled: !templateActive,
  });

  const { data: profilesMgmt = [] } = useQuery({
    queryKey: ['profiles', oltId, 'management'],
    queryFn: () => OntManageApi.profiles(oltId, 'management'),
    staleTime: 5 * 60_000,
    enabled: !templateActive,
  });

  // ---- Автоподстановка next-free-id ----
  useEffect(() => {
    let alive = true;
    OntManageApi.nextFreeId(oltId, gponPort).then(id => {
      if (alive) setOntId(id);
    });
    return () => { alive = false; };
  }, [oltId, gponPort]);

  // ---- Валидация ----
  // Обязательные: serial, ontId, и (template ИЛИ (CC + DBA + ports))
  const canSubmit =
    !!serial.trim() &&
    ontId !== '' &&
    (templateActive || (pCC && pDba && pPorts));

  // ---- Mutation ----
  const addMut = useMutation({
    mutationFn: () => OntManageApi.add(oltId, {
      gpon_port: gponPort,
      ont_id: Number(ontId),
      serial: serial.trim().toUpperCase(),
      description: !templateActive && description.trim()
        ? description.trim()
        : undefined,
      template: template || undefined,
      profile_cross_connect: !templateActive && pCC ? pCC : undefined,
      profile_dba: !templateActive && pDba ? pDba : undefined,
      profile_ports: !templateActive && pPorts ? pPorts : undefined,
      profile_management: !templateActive && pMgmt ? pMgmt : undefined,
    }),
    onSuccess: (r) => {
      if (r.ok) {
        toast.success(`ONT ${serial} добавлен на ${gponPort}/${ontId}`);
        qc.invalidateQueries({ queryKey: ['onts', oltId] });
        qc.invalidateQueries({ queryKey: ['onts-summary', oltId] });
        qc.invalidateQueries({ queryKey: ['unactivated', oltId] });
        onClose();
      } else {
        toast.error('Не удалось добавить ONT', {
          description: r.error || 'Неизвестная ошибка', duration: 12000,
        });
      }
    },
    onError: (e: any) =>
      toast.error(e?.response?.data?.detail || 'Ошибка запроса'),
  });

  const ports = Array.from({ length: maxPort + 1 }, (_, i) => i);

  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50 overflow-auto">
      <div className="bg-white rounded-lg p-5 w-[720px] my-8 shadow-xl">
        <h2 className="text-lg font-semibold mb-4">Добавить ONT</h2>

        {/* Строка 1: GPON-порт / ONT ID / Serial */}
        <div className="flex gap-3 mb-3">
          <div className="w-36 shrink-0">
            <label className="block text-sm mb-1 text-slate-600">GPON-порт</label>
            <select
              value={gponPort}
              onChange={e => setGponPort(Number(e.target.value))}
              className="select-base w-full"
            >
              {ports.map(p => <option key={p} value={p}>GPON-{p}</option>)}
            </select>
          </div>
          <div className="w-28 shrink-0">
            <label className="block text-sm mb-1 text-slate-600">ONT ID</label>
            <input
              type="number"
              value={ontId}
              onChange={e => setOntId(e.target.value === '' ? '' : Number(e.target.value))}
              className="input-base font-mono"
            />
          </div>
          <div className="flex-1">
            <label className="block text-sm mb-1 text-slate-600">Serial</label>
            <input
              value={serial}
              onChange={e => setSerial(e.target.value.toUpperCase())}
              placeholder="ELTX62151198"
              className="input-base font-mono"
            />
          </div>
        </div>

        {/* Строка 2: Description / Template */}
        <div className="flex gap-3 mb-3">
          <div className="flex-1">
            <label className="block text-sm mb-1 text-slate-600">
              Описание <span className="text-slate-400">(необязательно)</span>
            </label>
            <input
              value={description}
              onChange={e => setDescription(e.target.value)}
              placeholder="ipcam"
              className="input-base"
              disabled={profilesDisabled}
            />
          </div>
          <div className="flex-1">
            <label className="block text-sm mb-1 text-slate-600">Шаблон (template)</label>
            <select
              value={template}
              onChange={e => setTemplate(e.target.value)}
              className="select-base w-full"
            >
              <option value="">— без шаблона (задать профили) —</option>
              {templates.map(t => (
                <option key={t.name} value={t.name}>
                  {t.name}{t.description ? ` — ${t.description}` : ''}
                </option>
              ))}
            </select>
            <p className="text-xs text-slate-500 mt-1">
              Если выбрать шаблон — поля ниже игнорируются.
            </p>
          </div>
        </div>

        {/* Строка 3: Profile cross-connect / Profile dba */}
        <div className="grid grid-cols-2 gap-3 mb-3">
          <div>
            <label className="block text-sm mb-1 text-slate-600">
              Profile cross-connect <span className="text-red-500">*</span>
            </label>
            <select
              value={pCC}
              onChange={e => setPCC(e.target.value)}
              className="select-base w-full"
              disabled={profilesDisabled}
            >
              <option value="">— выберите профиль —</option>
              {profilesCC.map(p => (
                <option key={p.name} value={p.name}>
                  {p.name}{p.description ? ` — ${p.description}` : ''}
                </option>
              ))}
            </select>
            <p className="text-xs text-slate-500 mt-1">
              Service 0, определяет VLAN и tag-режим.
            </p>
          </div>
          <div>
            <label className="block text-sm mb-1 text-slate-600">
              Profile dba <span className="text-red-500">*</span>
            </label>
            <select
              value={pDba}
              onChange={e => setPDba(e.target.value)}
              className="select-base w-full"
              disabled={profilesDisabled}
            >
              <option value="">— выберите профиль —</option>
              {profilesDba.map(p => (
                <option key={p.name} value={p.name}>
                  {p.name}{p.description ? ` — ${p.description}` : ''}
                </option>
              ))}
            </select>
            <p className="text-xs text-slate-500 mt-1">
              Полоса пропускания (SLA) для service 0.
            </p>
          </div>
        </div>

        {/* Строка 4: Profile ports / Profile management */}
        <div className="grid grid-cols-2 gap-3 mb-3">
          <div>
            <label className="block text-sm mb-1 text-slate-600">
              Profile ports <span className="text-red-500">*</span>
            </label>
            <select
              value={pPorts}
              onChange={e => setPPorts(e.target.value)}
              className="select-base w-full"
              disabled={profilesDisabled}
            >
              <option value="">— выберите профиль —</option>
              {profilesPorts.map(p => (
                <option key={p.name} value={p.name}>
                  {p.name}{p.description ? ` — ${p.description}` : ''}
                </option>
              ))}
            </select>
            <p className="text-xs text-slate-500 mt-1">
              Настройка LAN-портов, IGMP/MLD, multicast.
            </p>
          </div>
          <div>
            <label className="block text-sm mb-1 text-slate-600">
              Profile management <span className="text-slate-400">(необязательно)</span>
            </label>
            <select
              value={pMgmt}
              onChange={e => setPMgmt(e.target.value)}
              className="select-base w-full"
              disabled={profilesDisabled}
            >
              <option value="">— не назначать —</option>
              {profilesMgmt.map(p => (
                <option key={p.name} value={p.name}>
                  {p.name}{p.description ? ` — ${p.description}` : ''}
                </option>
              ))}
            </select>
          </div>
        </div>

        <p className="text-xs text-slate-500 mb-4">
          Дополнительные сервисы (service 1..27, custom, selective-tunnel)
          добавляются в карточке ONT.
        </p>

        <div className="flex justify-end gap-2">
          <button onClick={onClose} className="btn btn-secondary">
            Отмена
          </button>
          <button
            onClick={() => addMut.mutate()}
            disabled={!canSubmit || addMut.isPending}
            className="btn btn-primary"
          >
            {addMut.isPending ? 'Добавляю…' : 'Добавить'}
          </button>
        </div>
      </div>
    </div>
  );
}