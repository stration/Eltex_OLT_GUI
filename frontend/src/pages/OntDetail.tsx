import { Link, useParams, useSearchParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { toast } from 'sonner';
import {
  RotateCw, Zap, AlertTriangle, Pause, Play, KeyRound, Trash2,
  ChevronDown, ChevronRight, Copy, Check,
} from 'lucide-react';
import {
  OntsApi,
  OntActionsApi,
  OntAction,
  OntFullConfig,
  OntMacsApi,
  OntPortsApi,
} from '../api/client';
import StatusBadge from '../components/StatusBadge';
import RssiChart from '../components/RssiChart';
import OntEditGeneralModal from '../components/OntEditGeneralModal';
import OntServiceEditModal from '../components/OntServiceEditModal';
import ConfirmModal from '../components/ConfirmModal';
import { Skeleton } from '../components/Skeleton';
import ErrorState from '../components/ErrorState';
import { formatRelativeTime } from '../lib/format';

type Tab = 'overview' | 'config';

interface PendingAction {
  action: OntAction;
  title: string;
  message: string;
  variant?: 'default' | 'danger';
  serial?: string;
}

export default function OntDetail() {
  const { id, port, ont } = useParams();
  const oltId = Number(id);
  const gponPort = Number(port);
  const ontId = Number(ont);

  const [params, setParams] = useSearchParams();
  const tab = (params.get('tab') as Tab) || 'overview';
  const setTab = (t: Tab) => {
    const next = new URLSearchParams(params);
    next.set('tab', t);
    setParams(next, { replace: true });
  };

  const qc = useQueryClient();
  const [hours, setHours] = useState(24);
  const [replaceOpen, setReplaceOpen] = useState(false);
  const [newSerial, setNewSerial] = useState('');
  const [editOpen, setEditOpen] = useState(false);
  const [editServiceId, setEditServiceId] = useState<number | null>(null);
  const [pending, setPending] = useState<PendingAction | null>(null);

  const {
    data: ontData,
    isLoading,
    isError: ontError,
    refetch: refetchOnt,
  } = useQuery({
    queryKey: ['ont', oltId, gponPort, ontId],
    queryFn: () => OntsApi.get(oltId, gponPort, ontId),
    refetchInterval: 30_000,
  });

  const { data: history } = useQuery({
    queryKey: ['ont-rssi', oltId, gponPort, ontId, hours],
    queryFn: () => OntsApi.rssiHistory(oltId, gponPort, ontId, hours),
    refetchInterval: 60_000,
    enabled: tab === 'overview',
  });

  const {
    data: macs,
    refetch: refetchMacs,
    isFetching: macsFetching,
  } = useQuery({
    queryKey: ['ont-macs', oltId, gponPort, ontId],
    queryFn: () => OntMacsApi.forOnt(oltId, gponPort, ontId),
    enabled: tab === 'overview',
    staleTime: 60_000,
  });

  const {
    data: portsState,
    refetch: refetchPorts,
    isFetching: portsFetching,
  } = useQuery({
    queryKey: ['ont-ports', oltId, gponPort, ontId],
    queryFn: () => OntPortsApi.forOnt(oltId, gponPort, ontId),
    enabled: tab === 'overview',
    staleTime: 60_000,
  });

  const {
    data: fullConfig,
    isLoading: configLoading,
    refetch: refetchConfig,
    isFetching: configFetching,
  } = useQuery({
    queryKey: ['ont-config', oltId, gponPort, ontId],
    queryFn: () => OntsApi.configuration(oltId, gponPort, ontId),
    enabled: tab === 'config',
    staleTime: 60_000,
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['ont', oltId, gponPort, ontId] });
    qc.invalidateQueries({ queryKey: ['onts', oltId] });
    qc.invalidateQueries({ queryKey: ['onts-summary', oltId] });
    setTimeout(() => {
      qc.invalidateQueries({ queryKey: ['ont', oltId, gponPort, ontId] });
      qc.invalidateQueries({ queryKey: ['onts', oltId] });
    }, 8000);
  };

  const actionMut = useMutation({
    mutationFn: ({ action, serial }: { action: OntAction; serial?: string }) =>
      OntActionsApi.run(oltId, gponPort, ontId, action, serial),
    onSuccess: (r, vars) => {
      setPending(null);
      if (r.ok) {
        toast.success(`Действие «${vars.action}» выполнено`);
        invalidate();
        if (vars.action === 'delete') {
          setTimeout(() => {
            window.location.href = `/olts/${oltId}/onts`;
          }, 1200);
        }
      } else {
        toast.error(`Не удалось выполнить «${vars.action}»`, {
          description: r.error || 'Неизвестная ошибка',
          duration: 12000,
        });
      }
    },
    onError: (e: any) => {
      setPending(null);
      toast.error(e?.response?.data?.detail || 'Ошибка запроса');
    },
  });

  const askAndRun = (
    action: OntAction,
    title: string,
    message: string,
    variant: 'default' | 'danger' = 'default',
    serial?: string,
  ) => {
    setPending({ action, title, message, variant, serial });
  };

  const runPending = () => {
    if (!pending) return;
    actionMut.mutate({ action: pending.action, serial: pending.serial });
  };

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-6 w-64" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (ontError || !ontData) {
    return (
      <ErrorState
        title="ONT не найдена"
        message="Не удалось получить данные ONT с сервера."
        onRetry={() => refetchOnt()}
      />
    );
  }

  const isActive = ontData.status === 'OK';

  return (
    <div>
      <div className="mb-2 text-sm text-slate-500">
        <Link to="/" className="text-accent-600 hover:text-accent-700 hover:underline">OLT</Link>
        <span className="mx-2">/</span>
        <Link to={`/olts/${oltId}`} className="text-accent-600 hover:text-accent-700 hover:underline">
          {oltId}
        </Link>
        <span className="mx-2">/</span>
        <Link to={`/olts/${oltId}/onts`} className="text-accent-600 hover:text-accent-700 hover:underline">
          ONT
        </Link>
        <span className="mx-2">/</span>
        <span className="text-slate-700">{ontData.serial}</span>
      </div>

      <div className="flex items-baseline mb-4">
        <h1 className="text-xl font-semibold font-mono flex-1">{ontData.serial}</h1>
        <StatusBadge status={ontData.status} />
      </div>

      <div className="flex gap-1 mb-4 border-b border-slate-200">
        <TabButton active={tab === 'overview'} onClick={() => setTab('overview')}>
          Обзор
        </TabButton>
        <TabButton active={tab === 'config'} onClick={() => setTab('config')}>
          Конфигурация
        </TabButton>
      </div>

      {tab === 'overview' && (
        <>
          <section className="card p-4 mb-4">
            <h2 className="text-sm font-medium text-slate-500 mb-3">Общие сведения</h2>
            <div className="text-sm">
              <Row k="GPON-порт" v={gponPort} />
              <Row k="ONT ID" v={ontId} />
              <Row k="Версия ПО" v={ontData.version || '—'} />
              <Row k="Оборудование" v={ontData.equipment_id || '—'} />
              <Row k="Описание" v={ontData.description || '—'} />
              <Row
                k="Последний отклик"
                v={formatRelativeTime(ontData.last_seen_at)}
              />
            </div>
          </section>

          <section className="card p-4 mb-4">
            <div className="flex items-center mb-3">
              <h2 className="text-sm font-medium text-slate-500 flex-1">
                MAC-адреса ({macs?.total ?? 0})
              </h2>
              <button
                onClick={() => refetchMacs()}
                disabled={macsFetching}
                className="btn btn-secondary btn-sm"
              >
                {macsFetching ? 'Обновляю…' : 'Обновить'}
              </button>
            </div>

            {!macs || macs.items.length === 0 ? (
              <div className="text-slate-400 text-sm">Нет обученных MAC-адресов</div>
            ) : (
              <table className="w-full text-sm">
                <thead className="text-slate-500 border-b border-slate-200">
                  <tr>
                    <th className="text-left p-2">MAC</th>
                    <th className="text-right p-2">GEM</th>
                    <th className="text-right p-2">UVID</th>
                    <th className="text-right p-2">CVID</th>
                    <th className="text-right p-2">SVID</th>
                  </tr>
                </thead>
                <tbody>
                  {macs.items.map((m, i) => (
                    <tr key={i} className="border-b border-slate-100 last:border-0">
                      <td className="p-2 font-mono">{m.mac}</td>
                      <td className="p-2 text-right font-mono">{m.gem ?? '—'}</td>
                      <td className="p-2 text-right font-mono">{m.uvid ?? '—'}</td>
                      <td className="p-2 text-right font-mono">{m.cvid ?? '—'}</td>
                      <td className="p-2 text-right font-mono">{m.svid ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>

          <section className="card p-4 mb-4">
            <div className="flex items-center mb-3">
              <h2 className="text-sm font-medium text-slate-500 flex-1">Порты (LAN)</h2>
              <button
                onClick={() => refetchPorts()}
                disabled={portsFetching}
                className="btn btn-secondary btn-sm"
              >
                {portsFetching ? 'Обновляю…' : 'Обновить'}
              </button>
            </div>

            {!portsState || portsState.items.length === 0 ? (
              <div className="text-slate-400 text-sm">
                Нет данных о портах (ONT не подключена или порты недоступны)
              </div>
            ) : (
              <table className="w-full text-sm">
                <thead className="text-slate-500 border-b border-slate-200">
                  <tr>
                    <th className="text-left p-2">Порт</th>
                    <th className="text-left p-2">Link</th>
                    <th className="text-left p-2">Скорость</th>
                    <th className="text-left p-2">Дуплекс</th>
                    <th className="text-left p-2">PoE</th>
                  </tr>
                </thead>
                <tbody>
                  {portsState.items.map(p => (
                    <tr key={p.port_id} className="border-b border-slate-100 last:border-0">
                      <td className="p-2 font-mono">port {p.port_id}</td>
                      <td className="p-2">
                        <LinkBadge state={p.link} />
                      </td>
                      <td className="p-2 font-mono">{formatSpeed(p.speed)}</td>
                      <td className="p-2">
                        {p.duplex === 'full' ? 'full' : p.duplex === 'half' ? 'half' : '—'}
                      </td>
                      <td className="p-2">
                        {p.poe_state === 'enable' ? 'on' : p.poe_state === 'disable' ? 'off' : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>

          <section className="card p-4 mb-4">
            <div className="flex items-center mb-3">
              <h2 className="text-sm font-medium text-slate-500 flex-1">RSSI, dBm</h2>
              <div className="flex gap-1 text-sm">
                {[
                  { h: 1, label: '1 ч' },
                  { h: 24, label: '24 ч' },
                  { h: 24 * 7, label: '7 д' },
                ].map(({ h, label }) => (
                  <button
                    key={h}
                    onClick={() => setHours(h)}
                    className={`btn btn-sm ${hours === h ? 'btn-primary' : 'btn-secondary'}`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>
            <div className="text-3xl font-semibold font-mono mb-3">
              {ontData.rssi_db !== null
                ? `${ontData.rssi_db.toFixed(2)} dBm`
                : 'нет данных'}
            </div>
            <RssiChart points={history?.points || []} height={220} />
          </section>

          <section className="card p-4">
            <h2 className="text-sm font-medium text-slate-500 mb-3">Действия</h2>
            <div className="flex flex-wrap gap-2 text-sm">
              <ActionButton
                icon={<RotateCw size={16} />}
                onClick={() => actionMut.mutate({ action: 'reconfigure' })}
                pending={actionMut.isPending && actionMut.variables?.action === 'reconfigure'}
              >
                Реконфигурация
              </ActionButton>
              <ActionButton
                icon={<Zap size={16} />}
                variant="danger"
                onClick={() =>
                  askAndRun(
                    'reset',
                    'Перезагрузка ONT',
                    `Перезагрузить ONT ${gponPort}/${ontId} (${ontData.serial})?\n\nСессия абонента прервётся на 1–2 минуты.`,
                    'danger',
                  )
                }
                pending={actionMut.isPending && actionMut.variables?.action === 'reset'}
              >
                Перезагрузка
              </ActionButton>
              <ActionButton
                icon={<AlertTriangle size={16} />}
                variant="danger"
                onClick={() =>
                  askAndRun(
                    'restore',
                    'Сброс ONT к заводским',
                    `СБРОСИТЬ ONT ${gponPort}/${ontId} (${ontData.serial}) К ЗАВОДСКИМ?\n\nВсе настройки ONT будут потеряны, потребуется повторная авторизация и конфигурация от OLT.`,
                    'danger',
                  )
                }
                pending={actionMut.isPending && actionMut.variables?.action === 'restore'}
              >
                Сброс к заводским
              </ActionButton>
              {isActive ? (
                <ActionButton
                  icon={<Pause size={16} />}
                  variant="danger"
                  onClick={() =>
                    askAndRun(
                      'disable',
                      'Деактивация ONT',
                      `Деактивировать ONT ${gponPort}/${ontId} (${ontData.serial})?\n\nONT перестанет обслуживаться OLT. Сервис абонента прекратится до повторной активации.`,
                      'danger',
                    )
                  }
                  pending={actionMut.isPending && actionMut.variables?.action === 'disable'}
                >
                  Деактивировать
                </ActionButton>
              ) : (
                <ActionButton
                  icon={<Play size={16} />}
                  onClick={() =>
                    askAndRun(
                      'enable',
                      'Активация ONT',
                      `Активировать ONT ${gponPort}/${ontId} (${ontData.serial})?`,
                    )
                  }
                  pending={actionMut.isPending && actionMut.variables?.action === 'enable'}
                >
                  Активировать
                </ActionButton>
              )}
              <ActionButton
                icon={<KeyRound size={16} />}
                onClick={() => { setReplaceOpen(true); setNewSerial(''); }}
              >
                Заменить серийник
              </ActionButton>
              <ActionButton
                icon={<Trash2 size={16} />}
                variant="danger"
                onClick={() =>
                  askAndRun(
                    'delete',
                    'Удаление ONT из конфигурации',
                    `УДАЛИТЬ ONT ${gponPort}/${ontId} (${ontData.serial}) ИЗ КОНФИГУРАЦИИ?\n\nЭто освободит ONT ID ${ontId} на порту ${gponPort}. Действие необратимо.`,
                    'danger',
                  )
                }
                pending={actionMut.isPending && actionMut.variables?.action === 'delete'}
              >
                Удалить из конфигурации
              </ActionButton>
            </div>
          </section>
        </>
      )}

      {tab === 'config' && (
        <>
          {fullConfig && (
            <CliConfigBlock
              gponPort={gponPort}
              ontId={ontId}
              cfg={fullConfig}
            />
          )}

          <section className="card p-4">
            <div className="flex items-center mb-3 gap-2">
              <h2 className="text-sm font-medium text-slate-500 flex-1">
                Полная конфигурация ONT
              </h2>
              <button
                onClick={() => refetchConfig()}
                disabled={configFetching}
                className="btn btn-secondary btn-sm"
              >
                {configFetching ? 'Обновляю…' : 'Обновить'}
              </button>
              {fullConfig && (
                <button
                  onClick={() => setEditOpen(true)}
                  className="btn btn-primary btn-sm"
                >
                  Редактировать
                </button>
              )}
            </div>

            {configLoading && (
              <div className="space-y-3">
                <Skeleton className="h-5 w-48" />
                <Skeleton className="h-24 w-full" />
                <Skeleton className="h-24 w-full" />
              </div>
            )}
            {fullConfig && (
              <ConfigView
                cfg={fullConfig}
                onEditService={sid => setEditServiceId(sid)}
              />
            )}
          </section>
        </>
      )}

      {replaceOpen && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-5 w-[440px] shadow-xl">
            <h2 className="text-lg font-semibold mb-3">Замена серийного номера</h2>
            <p className="text-sm text-slate-600 mb-3">
              ONT <span className="font-mono">{gponPort}/{ontId}</span>, текущий{' '}
              <span className="font-mono">{ontData.serial}</span>
            </p>
            <input
              value={newSerial}
              onChange={e => setNewSerial(e.target.value.toUpperCase())}
              placeholder="ELTX62151198"
              className="input-base font-mono mb-2"
            />
            <p className="text-xs text-slate-500 mb-4">
              Форматы: ELTX… (12 симв.), 16 hex-символов, или XX-XX-XX-XX-XX-XX-XX-XX
            </p>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setReplaceOpen(false)}
                className="btn btn-secondary"
              >
                Отмена
              </button>
              <button
                disabled={!newSerial}
                onClick={() => {
                  setReplaceOpen(false);
                  setPending({
                    action: 'replace-serial',
                    title: 'Замена серийного номера',
                    message: `Заменить серийный номер ONT ${gponPort}/${ontId} на ${newSerial}?`,
                    variant: 'danger',
                    serial: newSerial,
                  });
                }}
                className="btn btn-danger"
              >
                Заменить
              </button>
            </div>
          </div>
        </div>
      )}

      {editOpen && fullConfig && (
        <OntEditGeneralModal
          oltId={oltId}
          gponPort={gponPort}
          ontId={ontId}
          current={fullConfig}
          onClose={() => setEditOpen(false)}
        />
      )}

      {editServiceId !== null && fullConfig && (() => {
        const svc = fullConfig.services.find(s => s.service_id === editServiceId);
        if (!svc) return null;
        return (
          <OntServiceEditModal
            oltId={oltId}
            gponPort={gponPort}
            ontId={ontId}
            service={svc}
            currentUtilization={fullConfig.collect_utilization_statistics}
            onClose={() => setEditServiceId(null)}
          />
        );
      })()}

      <ConfirmModal
        open={pending !== null}
        title={pending?.title || ''}
        message={pending?.message || ''}
        variant={pending?.variant}
        busy={actionMut.isPending}
        onConfirm={runPending}
        onCancel={() => setPending(null)}
      />
    </div>
  );
}

// ---- CLI-конфигурация ---------------------------------------------------

function buildCliConfig(
  gponPort: number,
  ontId: number,
  cfg: OntFullConfig,
): string {
  const lines: string[] = [];
  const IND = '  ';

  lines.push(`interface ont ${gponPort}/${ontId}`);

  if (cfg.description) {
    lines.push(`${IND}description "${cfg.description}"`);
  }
  if (cfg.serial) {
    lines.push(`${IND}serial "${cfg.serial}"`);
  }
  if (cfg.password) {
    lines.push(`${IND}password "${cfg.password}"`);
  }
  if (cfg.fec_up) {
    lines.push(`${IND}fec`);
  }

  for (const s of cfg.services) {
    const empty =
      !s.profile_cross_connect &&
      !s.profile_dba &&
      s.custom_cross_connect !== 'enabled' &&
      !s.selective_tunnel_user_vlans;
    if (empty) continue;

    if (s.profile_cross_connect) {
      lines.push(
        `${IND}service ${s.service_id} profile cross-connect "${s.profile_cross_connect}"`,
      );
    }
    if (s.profile_dba) {
      lines.push(
        `${IND}service ${s.service_id} profile dba "${s.profile_dba}"`,
      );
    }
    if (s.custom_cross_connect === 'enabled') {
      lines.push(`${IND}service ${s.service_id} custom cross-connect`);
      if (s.custom_cvid != null) {
        lines.push(`${IND}service ${s.service_id} custom c-vid ${s.custom_cvid}`);
      }
      if (s.custom_svid != null) {
        lines.push(`${IND}service ${s.service_id} custom s-vid ${s.custom_svid}`);
      }
      if (s.custom_cos != null) {
        lines.push(`${IND}service ${s.service_id} custom cos ${s.custom_cos}`);
      }
    }
    if (s.selective_tunnel_user_vlans) {
      lines.push(
        `${IND}service ${s.service_id} selective-tunnel uvid ${s.selective_tunnel_user_vlans}`,
      );
    }
  }

  if (cfg.profile_ports) {
    lines.push(`${IND}profile ports "${cfg.profile_ports}"`);
  }
  if (cfg.profile_management) {
    lines.push(`${IND}profile management "${cfg.profile_management}"`);
  }
  if (cfg.profile_voice) {
    lines.push(`${IND}profile voice "${cfg.profile_voice}"`);
  }
  if (cfg.template) {
    lines.push(`${IND}template "${cfg.template}"`);
  }

  lines.push('exit');
  return lines.join('\n');
}

function CliConfigBlock({
  gponPort,
  ontId,
  cfg,
}: {
  gponPort: number;
  ontId: number;
  cfg: OntFullConfig;
}) {
  const text = buildCliConfig(gponPort, ontId, cfg);
  const [copied, setCopied] = useState(false);

  const onCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      toast.error('Не удалось скопировать');
    }
  };

  return (
    <section className="card p-4 mb-4">
      <div className="flex items-center mb-3">
        <h2 className="text-sm font-medium text-slate-500 flex-1">
          Конфигурация (как в CLI)
        </h2>
        <button
          onClick={onCopy}
          className="btn btn-secondary btn-sm inline-flex items-center gap-1"
          title="Скопировать в буфер"
        >
          {copied ? (
            <>
              <Check size={14} />
              Скопировано
            </>
          ) : (
            <>
              <Copy size={14} />
              Скопировать
            </>
          )}
        </button>
      </div>
      <pre className="font-mono text-xs bg-slate-50 p-4 rounded border border-slate-200 overflow-x-auto whitespace-pre">
{text}
      </pre>
    </section>
  );
}

// ---- Вспомогательные компоненты -----------------------------------------

function Row({ k, v }: { k: string; v: string | number }) {
  return (
    <div className="flex py-0.5">
      <div className="w-56 shrink-0 text-slate-500">{k}</div>
      <div className="font-mono">{v}</div>
    </div>
  );
}

function LinkBadge({ state }: { state: string | null }) {
  if (state === 'up') {
    return (
      <span className="px-2 py-0.5 rounded text-xs bg-green-100 text-green-800">
        up
      </span>
    );
  }
  if (state === 'down') {
    return (
      <span className="px-2 py-0.5 rounded text-xs bg-slate-100 text-slate-600">
        down
      </span>
    );
  }
  return <span className="text-slate-400">—</span>;
}

function formatSpeed(s: string | null): string {
  if (!s) return '—';
  const up = s.toUpperCase();
  if (up === '10M') return '10 Mb';
  if (up === '100M') return '100 Mb';
  if (up === '1000M') return '1 Gb';
  return s;
}

function ActionButton({
  children,
  onClick,
  pending,
  variant,
  icon,
}: {
  children: React.ReactNode;
  onClick: () => void;
  pending?: boolean;
  variant?: 'danger';
  icon?: React.ReactNode;
}) {
  const cls = variant === 'danger' ? 'btn btn-danger' : 'btn btn-secondary';
  return (
    <button onClick={onClick} disabled={pending} className={cls}>
      {pending ? (
        <>
          <span className="inline-block w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
          <span>Выполняется…</span>
        </>
      ) : (
        <>
          {icon}
          <span>{children}</span>
        </>
      )}
    </button>
  );
}

function TabButton({
  children,
  active,
  onClick,
}: {
  children: React.ReactNode;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-2 text-sm border-b-2 transition-colors ${
        active
          ? 'border-accent-500 text-accent-700 font-medium'
          : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
      }`}
    >
      {children}
    </button>
  );
}

// ---- Просмотр конфигурации ----------------------------------------------

function isServiceEmpty(s: OntFullConfig['services'][number]): boolean {
  return (
    !s.profile_cross_connect &&
    !s.profile_dba &&
    s.custom_cross_connect !== 'enabled' &&
    !s.selective_tunnel_user_vlans
  );
}

function ConfigView({
  cfg,
  onEditService,
}: {
  cfg: OntFullConfig;
  onEditService: (serviceId: number) => void;
}) {
  const [showAll, setShowAll] = useState(false);

  const emptyCount = cfg.services.filter(isServiceEmpty).length;
  const activeCount = cfg.services.length - emptyCount;
  const visibleServices = showAll ? cfg.services : cfg.services.filter(s => !isServiceEmpty(s));

  return (
    <div className="text-sm">
      <ConfigBlock title="Общие параметры">
        <KV k="Описание" v={cfg.description} mono />
        <KV k="Включён" v={cfg.enabled ? 'да' : 'нет'} />
        <KV k="Серийный номер" v={cfg.serial} mono />
        <KV k="Пароль" v={cfg.password} mono />
        <KV k="FEC (upstream)" v={cfg.fec_up ? 'включён' : 'выключен'} />
        <KV k="Easy mode" v={cfg.easy_mode ? 'включён' : 'выключен'} />
        <KV k="Downstream broadcast" v={cfg.downstream_broadcast ? 'включён' : 'выключен'} />
        <KV k="Downstream broadcast filter" v={cfg.downstream_broadcast_filter ? 'включён' : 'выключен'} />
        <KV k="Downstream multicast filter" v={cfg.downstream_multicast_filter ? 'включён' : 'выключен'} />
        <KV k="BER interval" v={cfg.ber_interval ?? '—'} mono />
        <KV k="BER update period" v={String(cfg.ber_update_period)} mono />
        <KV k="RF port state" v={cfg.rf_port_state ?? '—'} />
        <KV k="OMCI error tolerant" v={cfg.omci_error_tolerant ? 'включён' : 'выключен'} />
      </ConfigBlock>

      <ConfigBlock
        title={`Сервисы (${activeCount} активных${emptyCount > 0 ? `, ${emptyCount} пустых` : ''})`}
      >
        {emptyCount > 0 && (
          <div className="mb-3">
            <button
              onClick={() => setShowAll(v => !v)}
              className="text-xs text-accent-600 hover:text-accent-700 hover:underline inline-flex items-center gap-1"
            >
              {showAll ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
              {showAll ? 'Скрыть пустые' : `Показать все (${cfg.services.length})`}
            </button>
          </div>
        )}

        {visibleServices.length === 0 && (
          <div className="text-slate-400">Активных сервисов нет</div>
        )}

        {visibleServices.map(s => (
          <ServiceCard key={s.service_id} s={s} onEdit={() => onEditService(s.service_id)} />
        ))}
      </ConfigBlock>

      <ConfigBlock title="Профили (глобальные)">
        <KV k="Profile shaping" v={cfg.profile_shaping} mono />
        <KV k="Profile ports" v={cfg.profile_ports} mono />
        <KV k="Profile management" v={cfg.profile_management} mono />
        <KV k="Profile voice" v={cfg.profile_voice} mono />
        <KV k="Template" v={cfg.template} mono />
        <KV k="PPPoE sessions unlimited" v={cfg.pppoe_sessions_unlimited ? 'да' : 'нет'} />
        <KV k="Collect utilization statistics" v={cfg.collect_utilization_statistics ? 'да' : 'нет'} />
      </ConfigBlock>

      <ConfigBlock title={`Порты (${cfg.ports.length})`}>
        <div className="flex flex-wrap gap-3">
          {cfg.ports.map(p => (
            <div key={p.port_id} className="border border-slate-200 rounded p-3 w-64">
              <div className="font-medium mb-1">Port [{p.port_id}]</div>
              <div className="text-xs">
                <KV k="shutdown" v={p.shutdown ? 'да' : 'нет'} />
                <KV k="PoE enable" v={p.poe_enable ? 'да' : 'нет'} />
                <KV k="PSE class" v={String(p.poe_pse_class_control)} mono />
                <KV k="Power priority" v={p.poe_power_priority ?? '—'} />
              </div>
            </div>
          ))}
        </div>
      </ConfigBlock>
    </div>
  );
}

function ServiceCard({
  s,
  onEdit,
}: {
  s: OntFullConfig['services'][number];
  onEdit: () => void;
}) {
  const empty = isServiceEmpty(s);
  return (
    <div
      className={`border rounded p-3 mb-2 ${
        empty ? 'border-slate-100 bg-slate-50' : 'border-slate-200'
      }`}
    >
      <div className="flex items-center mb-2">
        <div className={`font-medium flex-1 ${empty ? 'text-slate-400' : ''}`}>
          Service [{s.service_id}]
          {empty && <span className="ml-2 text-xs font-normal">(пустой)</span>}
        </div>
        <button onClick={onEdit} className="btn btn-secondary btn-sm">
          Редактировать
        </button>
      </div>
      {!empty && (
        <div className="text-xs">
          <KV k="Profile cross-connect" v={s.profile_cross_connect} mono />
          <KV k="Описание" v={s.profile_cross_connect_desc} />
          <KV k="Profile dba" v={s.profile_dba} mono />
          <KV k="Описание" v={s.profile_dba_desc} />
          <KV k="Custom cross-connect" v={s.custom_cross_connect} />
          {s.custom_cross_connect === 'enabled' && (
            <>
              <KV k="  custom c-vid" v={String(s.custom_cvid ?? '—')} mono />
              <KV k="  custom s-vid" v={String(s.custom_svid ?? '—')} mono />
              <KV k="  custom cos" v={String(s.custom_cos ?? '—')} mono />
            </>
          )}
          {s.selective_tunnel_user_vlans && (
            <KV k="Selective-tunnel uvid" v={s.selective_tunnel_user_vlans} mono />
          )}
        </div>
      )}
    </div>
  );
}

function ConfigBlock({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="mb-6">
      <h3 className="font-medium text-slate-700 mb-2">{title}</h3>
      {children}
    </div>
  );
}

function KV({
  k,
  v,
  mono,
}: {
  k: string;
  v: string | null | undefined;
  mono?: boolean;
}) {
  return (
    <div className="flex py-0.5">
      <div className="w-56 shrink-0 text-slate-500">{k}</div>
      <div className={mono ? 'font-mono' : ''}>{v ?? '—'}</div>
    </div>
  );
}