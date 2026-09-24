import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import {
  OntFullConfig, OntGeneralEditPayload,
  OntManageApi, OntEditApi,
} from '../api/client';

interface Props {
  oltId: number;
  gponPort: number;
  ontId: number;
  current: OntFullConfig;
  onClose: () => void;
}

export default function OntEditGeneralModal({
  oltId, gponPort, ontId, current, onClose,
}: Props) {
  const qc = useQueryClient();

  const [description, setDescription] = useState(current.description ?? '');
  const [password, setPassword] = useState('');
  const [fec, setFec] = useState(current.fec_up);
  const [easyMode, setEasyMode] = useState(current.easy_mode);
  const [bcEnable, setBcEnable] = useState(current.downstream_broadcast);
  const [bcFilter, setBcFilter] = useState(current.downstream_broadcast_filter);
  const [mcFilter, setMcFilter] = useState(current.downstream_multicast_filter);
  const [omciTolerant, setOmciTolerant] = useState(current.omci_error_tolerant);
  const [rfState, setRfState] = useState(current.rf_port_state ?? 'no-change');

  const [pPorts, setPPorts] = useState(current.profile_ports ?? '');
  const [pMgmt, setPMgmt] = useState(current.profile_management ?? '');
  const [pShaping, setPShaping] = useState(current.profile_shaping ?? '');
  const [pVoice, setPVoice] = useState(current.profile_voice ?? '');
  const [template, setTemplate] = useState(current.template ?? '');

  const { data: profilesPorts = [] } = useQuery({
    queryKey: ['profiles', oltId, 'ports'],
    queryFn: () => OntManageApi.profiles(oltId, 'ports'),
    staleTime: 5 * 60_000,
  });
  const { data: profilesMgmt = [] } = useQuery({
    queryKey: ['profiles', oltId, 'management'],
    queryFn: () => OntManageApi.profiles(oltId, 'management'),
    staleTime: 5 * 60_000,
  });
  const { data: profilesShaping = [] } = useQuery({
    queryKey: ['profiles', oltId, 'shaping'],
    queryFn: () => OntManageApi.profiles(oltId, 'shaping'),
    staleTime: 5 * 60_000,
  });
  const { data: profilesVoice = [] } = useQuery({
    queryKey: ['profiles', oltId, 'voice'],
    queryFn: () => OntManageApi.profiles(oltId, 'voice'),
    staleTime: 5 * 60_000,
  });
  const { data: templates = [] } = useQuery({
    queryKey: ['templates', oltId],
    queryFn: () => OntManageApi.templates(oltId),
    staleTime: 5 * 60_000,
  });

  const mut = useMutation({
    mutationFn: (payload: OntGeneralEditPayload) =>
      OntEditApi.updateGeneral(oltId, gponPort, ontId, payload),
    onSuccess: (r) => {
      if (r.ok) {
        toast.success(
          r.changes.length > 0
            ? `Применено изменений: ${r.changes.length}`
            : 'Изменений нет',
        );
        qc.invalidateQueries({ queryKey: ['ont-config', oltId, gponPort, ontId] });
        qc.invalidateQueries({ queryKey: ['ont', oltId, gponPort, ontId] });
        qc.invalidateQueries({ queryKey: ['onts', oltId] });
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

  const submit = () => {
    const payload: OntGeneralEditPayload = {
      description,
      fec_up: fec,
      easy_mode: easyMode,
      downstream_broadcast: bcEnable,
      downstream_broadcast_filter: bcFilter,
      downstream_multicast_filter: mcFilter,
      omci_error_tolerant: omciTolerant,
      rf_port_state: rfState,
      profile_ports: pPorts || null,
      profile_management: pMgmt || null,
      profile_shaping: pShaping || null,
      profile_voice: pVoice || null,
      template: template || null,
    };
    if (password) payload.password = password;
    mut.mutate(payload);
  };

  return (
    <div className="fixed inset-0 bg-black/30 flex items-start justify-center z-50 overflow-auto py-8">
      <div className="bg-white rounded-lg p-5 w-[720px] shadow-xl">
        <h2 className="text-lg font-semibold mb-4">
          Редактирование ONT {gponPort}/{ontId}
        </h2>

        <Section title="Общие параметры">
          <Field label="Описание">
            <input
              value={description}
              onChange={e => setDescription(e.target.value)}
              maxLength={127}
              className="input-base"
            />
          </Field>
          <Field label="Пароль PLOAM" hint="10 символов. Оставьте пустым, чтобы не менять.">
            <input
              value={password}
              onChange={e => setPassword(e.target.value)}
              maxLength={10}
              className="input-base font-mono"
            />
          </Field>
          <Field label="RF-port state">
            <select
              value={rfState}
              onChange={e => setRfState(e.target.value)}
              className="select-base w-full"
            >
              <option value="no-change">no-change (не менять)</option>
              <option value="enabled">enabled</option>
              <option value="disabled">disabled</option>
            </select>
          </Field>
        </Section>

        <Section title="Флаги">
          <div className="grid grid-cols-2 gap-2">
            <Checkbox label="FEC (upstream)" checked={fec} onChange={setFec} />
            <Checkbox label="Easy mode" checked={easyMode} onChange={setEasyMode} />
            <Checkbox label="Downstream broadcast" checked={bcEnable} onChange={setBcEnable} />
            <Checkbox label="Downstream broadcast filter" checked={bcFilter} onChange={setBcFilter} />
            <Checkbox label="Downstream multicast filter" checked={mcFilter} onChange={setMcFilter} />
            <Checkbox label="OMCI error tolerant" checked={omciTolerant} onChange={setOmciTolerant} />
          </div>
        </Section>

        <Section title="Профили">
          <div className="grid grid-cols-2 gap-3">
            <Field label="Profile ports">
              <SelectProfile value={pPorts} onChange={setPPorts} items={profilesPorts} />
            </Field>
            <Field label="Profile management">
              <SelectProfile value={pMgmt} onChange={setPMgmt} items={profilesMgmt} />
            </Field>
            <Field label="Profile shaping">
              <SelectProfile value={pShaping} onChange={setPShaping} items={profilesShaping} />
            </Field>
            <Field label="Profile voice">
              <SelectProfile value={pVoice} onChange={setPVoice} items={profilesVoice} />
            </Field>
            <Field label="Template">
              <select
                value={template}
                onChange={e => setTemplate(e.target.value)}
                className="select-base w-full"
              >
                <option value="">— без шаблона —</option>
                {templates.map(t => (
                  <option key={t.name} value={t.name}>{t.name} — {t.description}</option>
                ))}
              </select>
            </Field>
          </div>
        </Section>

        <div className="flex justify-end gap-2 mt-6">
          <button
            onClick={onClose}
            disabled={mut.isPending}
            className="btn btn-secondary"
          >
            Отмена
          </button>
          <button
            onClick={submit}
            disabled={mut.isPending}
            className="btn btn-primary"
          >
            {mut.isPending ? 'Применяю…' : 'Применить'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ---- мелкие компоненты -------------------------------------------------

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-5">
      <h3 className="text-sm font-medium text-slate-500 mb-2">{title}</h3>
      <div className="space-y-2">{children}</div>
    </div>
  );
}

function Field({
  label, hint, children,
}: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-sm text-slate-600 mb-1">{label}</label>
      {children}
      {hint && <p className="text-xs text-slate-400 mt-1">{hint}</p>}
    </div>
  );
}

function Checkbox({
  label, checked, onChange,
}: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="flex items-center gap-2 text-sm cursor-pointer">
      <input
        type="checkbox"
        checked={checked}
        onChange={e => onChange(e.target.checked)}
        className="rounded border-slate-300 text-accent-600 focus:ring-accent-500"
      />
      {label}
    </label>
  );
}

function SelectProfile({
  value, onChange, items,
}: {
  value: string;
  onChange: (v: string) => void;
  items: { name: string; description: string }[];
}) {
  return (
    <select
      value={value}
      onChange={e => onChange(e.target.value)}
      className="select-base w-full"
    >
      <option value="">— не назначен —</option>
      {items.map(p => (
        <option key={p.name} value={p.name}>{p.name} — {p.description}</option>
      ))}
    </select>
  );
}