import { Link, useParams, useSearchParams } from 'react-router-dom';
import { useState, useRef } from 'react';
import { Search, Download, Eye, Terminal } from 'lucide-react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import {
  OltsApi,
  OntsApi,
  OntManageApi,
  GponPortState,
  OltSystemInfo,
  OltVlan,
  UplinkPort,
  UplinkCounters,
  ProfileItem,
  ProfileDetails,
  OltAlarm,
  OltMacEntry,
  PortInfo,
} from '../api/client';
import StatusBadge from '../components/StatusBadge';
import { Skeleton, SkeletonTable } from '../components/Skeleton';
import ErrorState from '../components/ErrorState';

type Tab = 'overview' | 'alarms' | 'macs' | 'system' | 'vlans' | 'uplinks' | 'profiles';

const ABONENT_PROFILE_TYPES: { key: string; label: string }[] = [
  { key: 'cross-connect', label: 'Cross-connect' },
  { key: 'dba',           label: 'DBA' },
  { key: 'ports',         label: 'Ports' },
  { key: 'shaping',       label: 'Shaping' },
  { key: 'management',    label: 'Management' },
  { key: 'voice',         label: 'Voice' },
];

export default function OltDetail() {
  const { id } = useParams();
  const oltId = Number(id);
  const qc = useQueryClient();

  const [params, setParams] = useSearchParams();
  const tab = (params.get('tab') as Tab) || 'overview';
  const setTab = (t: Tab) => {
    const next = new URLSearchParams(params);
    next.set('tab', t);
    setParams(next, { replace: true });
  };

  const {
    data: olt,
    isLoading: oltLoading,
    isError: oltError,
    refetch: refetchOlt,
  } = useQuery({
    queryKey: ['olt', oltId],
    queryFn: () => OltsApi.get(oltId),
  });

  const { data: summary, isLoading: summaryLoading } = useQuery({
    queryKey: ['onts-summary', oltId],
    queryFn: () => OntsApi.summary(oltId),
    refetchInterval: 30_000,
  });

  const {
    data: ports,
    isLoading: portsLoading,
    isError: portsError,
    refetch: refetchPorts,
    isFetching: portsFetching,
  } = useQuery({
    queryKey: ['gpon-ports', oltId],
    queryFn: () => OltsApi.gponPorts(oltId),
    refetchInterval: 30_000,
    enabled: tab === 'overview',
  });

  const {
    data: alarmsData,
    isLoading: alarmsLoading,
    isError: alarmsError,
    refetch: refetchAlarms,
    isFetching: alarmsFetching,
  } = useQuery({
    queryKey: ['olt-alarms', oltId],
    queryFn: () => OltsApi.alarms(oltId),
    refetchInterval: 60_000,
    enabled: tab === 'alarms',
  });

  const {
    data: macsData,
    isLoading: macsLoading,
    isError: macsError,
    refetch: refetchMacs,
    isFetching: macsFetching,
  } = useQuery({
    queryKey: ['olt-macs', oltId],
    queryFn: () => OltsApi.macs(oltId),
    staleTime: 15_000,
    enabled: tab === 'macs',
  });

  const {
    data: system,
    isLoading: systemLoading,
    isError: systemError,
    refetch: refetchSystem,
    isFetching: systemFetching,
  } = useQuery({
    queryKey: ['olt-system', oltId],
    queryFn: () => OltsApi.system(oltId),
    refetchInterval: 60_000,
    enabled: tab === 'system',
  });

  const {
    data: vlans,
    isLoading: vlansLoading,
    isError: vlansError,
    refetch: refetchVlans,
    isFetching: vlansFetching,
  } = useQuery({
    queryKey: ['olt-vlans', oltId],
    queryFn: () => OltsApi.vlans(oltId),
    refetchInterval: 60_000,
    enabled: tab === 'vlans',
  });

  const {
    data: uplinks,
    isLoading: uplinksLoading,
    isError: uplinksError,
    refetch: refetchUplinks,
    isFetching: uplinksFetching,
  } = useQuery({
    queryKey: ['olt-uplinks', oltId],
    queryFn: () => OltsApi.uplinks(oltId),
    enabled: tab === 'uplinks',
  });

  const {
    data: profiles,
    isLoading: profilesLoading,
    isError: profilesError,
    refetch: refetchProfiles,
    isFetching: profilesFetching,
  } = useQuery({
    queryKey: ['olt-profiles', oltId],
    queryFn: async (): Promise<Record<string, ProfileItem[]>> => {
      const result: Record<string, ProfileItem[]> = {};
      await Promise.all(
        ABONENT_PROFILE_TYPES.map(async t => {
          try {
            result[t.key] = await OntManageApi.profiles(oltId, t.key);
          } catch {
            result[t.key] = [];
          }
        }),
      );
      return result;
    },
    staleTime: 5 * 60_000,
    enabled: tab === 'profiles',
  });

  const checkMut = useMutation({
    mutationFn: () => OltsApi.check(oltId),
    onSuccess: r => {
      toast.message(`Проверка ${r.ip}`, {
        description: `ping ${r.ping_ok ? r.ping_ms + ' мс' : 'нет'}, SNMP ${
          r.snmp_ok ? 'ok' : 'нет'
        }${r.model ? ', ' + r.model : ''}`,
      });
      qc.invalidateQueries({ queryKey: ['olt', oltId] });
    },
    onError: (e: any) =>
      toast.error(e?.response?.data?.detail || 'Ошибка проверки OLT'),
  });

  if (oltLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-5 w-64" />
        <Skeleton className="h-8 w-96" />
        <div className="grid grid-cols-4 gap-4">
          <Skeleton className="h-24" />
          <Skeleton className="h-24" />
          <Skeleton className="h-24" />
          <Skeleton className="h-24" />
        </div>
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (oltError || !olt) {
    return (
      <ErrorState
        title="OLT не найдена"
        message="Не удалось получить данные OLT с сервера."
        onRetry={() => refetchOlt()}
      />
    );
  }

  const totalOnts = summary?.total ?? 0;
  const okCount = summary?.by_status?.OK ?? 0;
  const offlineCount = summary?.by_status?.OFFLINE ?? 0;
  const otherCount = totalOnts - okCount - offlineCount;

  return (
    <div>
      <div className="mb-2 text-sm text-slate-500">
        <Link to="/" className="text-accent-600 hover:text-accent-700 hover:underline">
          OLT
        </Link>
        <span className="mx-2">/</span>
        <span className="text-slate-700">{olt.name || olt.ip}</span>
      </div>

      <div className="flex items-baseline mb-4">
        <h1 className="text-xl font-semibold flex-1">
          {olt.name || olt.ip}
          <span className="text-slate-400 font-normal ml-2">({olt.ip})</span>
        </h1>
        <div className="text-sm text-slate-600 flex items-center gap-3">
          <span>{olt.model || '—'} · {olt.hw_revision || '—'}</span>
          <StatusBadge status={olt.status === 'online' ? 'OK' : 'OFFLINE'} />
          <Link
            to={`/terminal?olt=${oltId}`}
            className="btn btn-secondary btn-sm inline-flex items-center gap-1.5"
            title="Открыть CLI этой OLT"
          >
            <Terminal size={14} />
            Терминал
          </Link>
          <button
            onClick={() => checkMut.mutate()}
            disabled={checkMut.isPending}
            className="btn btn-secondary btn-sm inline-flex items-center gap-1.5"
          >
            <Search size={14} />
            {checkMut.isPending ? 'Проверяю…' : 'Проверить'}
          </button>
        </div>
      </div>

      <div className="flex gap-1 mb-4 border-b border-slate-200">
        <TabButton active={tab === 'overview'} onClick={() => setTab('overview')}>
          Обзор
        </TabButton>
        <TabButton active={tab === 'alarms'} onClick={() => setTab('alarms')}>
          Алармы
          {alarmsData && alarmsData.total > 0 && (
            <span className="ml-2 inline-flex items-center justify-center px-1.5 py-0.5 rounded-full text-xs bg-red-100 text-red-700">
              {alarmsData.total}
            </span>
          )}
        </TabButton>
        <TabButton active={tab === 'macs'} onClick={() => setTab('macs')}>
          MAC
        </TabButton>
        <TabButton active={tab === 'system'} onClick={() => setTab('system')}>
          Система
        </TabButton>
        <TabButton active={tab === 'vlans'} onClick={() => setTab('vlans')}>
          VLAN
        </TabButton>
        <TabButton active={tab === 'uplinks'} onClick={() => setTab('uplinks')}>
          Uplink
        </TabButton>
        <TabButton active={tab === 'profiles'} onClick={() => setTab('profiles')}>
          Профили
        </TabButton>
      </div>

      {tab === 'overview' && (
        <>
          <section className="grid grid-cols-4 gap-4 mb-6">
            <Metric title="Всего ONT" value={totalOnts} pending={summaryLoading} />
            <Metric title="OK" value={okCount} accent="green" pending={summaryLoading} />
            <Metric title="Offline" value={offlineCount} accent="red" pending={summaryLoading} />
            <Metric title="Прочие" value={otherCount} pending={summaryLoading} />
          </section>

          <section className="card">
            <div className="card-header flex items-center">
              <span className="flex-1">GPON-порты</span>
              {portsFetching && !portsLoading && (
                <span className="text-xs text-slate-400">обновляю…</span>
              )}
            </div>

            {portsError ? (
              <div className="p-4">
                <ErrorState
                  title="Не удалось загрузить состояние портов"
                  message="OLT не отвечает или SNMP недоступен."
                  onRetry={() => refetchPorts()}
                />
              </div>
            ) : portsLoading ? (
              <SkeletonTable rows={4} cols={9} />
            ) : (
              <table className="w-full text-sm">
                <thead className="text-slate-500 border-b border-slate-200">
                  <tr>
                    <th className="text-left p-3">Порт</th>
                    <th className="text-left p-3">State</th>
                    <th className="text-right p-3">ONT</th>
                    <th className="text-left p-3">SFP</th>
                    <th className="text-right p-3">Tx, dBm</th>
                    <th className="text-right p-3">Темп., °C</th>
                    <th className="text-right p-3">U, V</th>
                    <th className="text-right p-3">I, mA</th>
                    <th className="text-right p-3"></th>
                  </tr>
                </thead>
                <tbody>
                  {(ports ?? []).map(p => {
                    const portStats = summary?.by_port?.[String(p.gpon_port)] || {};
                    const ontInDb = Object.values(portStats).reduce(
                      (a, b) => a + b,
                      0,
                    );
                    return (
                      <PortRow
                        key={p.gpon_port}
                        oltId={oltId}
                        p={p}
                        ontInDb={ontInDb}
                      />
                    );
                  })}
                </tbody>
              </table>
            )}
          </section>

          <div className="mt-6 flex gap-2 flex-wrap">
            <Link to={`/olts/${oltId}/onts`} className="btn btn-primary">
              Все ONT этого OLT
            </Link>
            <Link to={`/olts/${oltId}/onts/unactivated`} className="btn btn-secondary">
              Автообнаружение ONT
            </Link>
            <a
              href={`/api/olts/${oltId}/running-config/download`}
              className="btn btn-secondary inline-flex items-center gap-1.5"
            >
              <Download size={14} />
              Скачать конфигурацию
            </a>
            <a
              href={`/api/olts/${oltId}/running-config`}
              target="_blank"
              rel="noopener noreferrer"
              className="btn btn-secondary inline-flex items-center gap-1.5"
            >
              <Eye size={14} />
              Показать конфигурацию
            </a>
          </div>
        </>
      )}

      {tab === 'alarms' && (
        <AlarmsTab
          alarms={alarmsData?.items}
          loading={alarmsLoading}
          error={alarmsError}
          refetch={refetchAlarms}
          fetching={alarmsFetching}
        />
      )}

      {tab === 'macs' && (
        <MacsTab
          data={macsData}
          loading={macsLoading}
          error={macsError}
          refetch={refetchMacs}
          fetching={macsFetching}
        />
      )}

      {tab === 'system' && (
        <SystemTab
          system={system}
          loading={systemLoading}
          error={systemError}
          refetch={refetchSystem}
          fetching={systemFetching}
        />
      )}

      {tab === 'vlans' && (
        <VlansTab
          vlans={vlans}
          loading={vlansLoading}
          error={vlansError}
          refetch={refetchVlans}
          fetching={vlansFetching}
        />
      )}

      {tab === 'uplinks' && (
        <UplinksTab
          uplinks={uplinks}
          loading={uplinksLoading}
          error={uplinksError}
          refetch={refetchUplinks}
          fetching={uplinksFetching}
        />
      )}

      {tab === 'profiles' && (
        <ProfilesTab
          oltId={oltId}
          profiles={profiles}
          loading={profilesLoading}
          error={profilesError}
          refetch={refetchProfiles}
          fetching={profilesFetching}
        />
      )}
    </div>
  );
}

// ---- Вкладка «Алармы» ---------------------------------------------------

const SEVERITY_ORDER: Record<string, number> = {
  critical: 0,
  major: 1,
  minor: 2,
  info: 3,
};

function AlarmsTab({
  alarms,
  loading,
  error,
  refetch,
  fetching,
}: {
  alarms: OltAlarm[] | undefined;
  loading: boolean;
  error: boolean;
  refetch: () => void;
  fetching: boolean;
}) {
  if (error) {
    return (
      <ErrorState
        title="Не удалось загрузить активные аварии"
        message="OLT не отвечает или CLI недоступен."
        onRetry={refetch}
      />
    );
  }

  if (loading || !alarms) {
    return <SkeletonTable rows={4} cols={4} />;
  }

  if (alarms.length === 0) {
    return (
      <div className="card p-6 text-center">
        <div className="text-2xl mb-2">✓</div>
        <div className="text-green-700 font-medium">Активных аварий нет</div>
        <div className="text-xs text-slate-400 mt-1">
          Автообновление раз в 60 секунд
        </div>
      </div>
    );
  }

  const sorted = [...alarms].sort((a, b) => {
    const sa = SEVERITY_ORDER[a.severity] ?? 99;
    const sb = SEVERITY_ORDER[b.severity] ?? 99;
    if (sa !== sb) return sa - sb;
    return a.index - b.index;
  });

  return (
    <div className="space-y-4">
      {fetching && (
        <div className="text-xs text-slate-400 text-right">обновляю…</div>
      )}

      <section className="card">
        <div className="card-header flex items-center">
          <span className="flex-1">
            Активные аварии ({alarms.length})
          </span>
          <button
            onClick={() => refetch()}
            disabled={fetching}
            className="btn btn-secondary btn-sm"
          >
            {fetching ? 'Обновляю…' : '↻ Обновить'}
          </button>
        </div>

        <table className="w-full text-sm">
          <thead className="text-slate-500 border-b border-slate-200">
            <tr>
              <th className="text-left p-3 w-24">Severity</th>
              <th className="text-left p-3">Тип</th>
              <th className="text-left p-3">Объект</th>
              <th className="text-left p-3">Описание</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map(a => (
              <tr
                key={`${a.index}-${a.type}-${a.description}`}
                className="border-b border-slate-100 last:border-0 hover:bg-slate-50"
              >
                <td className="p-3">
                  <SeverityBadge severity={a.severity} raw={a.severity_raw} />
                </td>
                <td className="p-3">{a.type || '—'}</td>
                <td className="p-3 font-mono text-xs">
                  {a.ont_gpon_port !== null && a.ont_id !== null ? (
                    <span>
                      ONT {a.ont_gpon_port}/{a.ont_id}
                      {a.ont_serial ? (
                        <span className="text-slate-400 ml-1">
                          ({a.ont_serial})
                        </span>
                      ) : null}
                    </span>
                  ) : (
                    <span className="text-slate-300">—</span>
                  )}
                </td>
                <td className="p-3">{a.description || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}

function SeverityBadge({ severity, raw }: { severity: string; raw: string }) {
  const map: Record<string, string> = {
    critical: 'bg-red-100 text-red-800',
    major:    'bg-orange-100 text-orange-800',
    minor:    'bg-yellow-100 text-yellow-800',
    info:     'bg-blue-100 text-blue-800',
  };
  const cls = map[severity] || 'bg-slate-100 text-slate-700';
  return (
    <span className={`px-2 py-0.5 rounded text-xs ${cls}`}>
      {raw || severity}
    </span>
  );
}

// ---- Вкладка «MAC-таблица» ----------------------------------------------

function MacsTab({
  data,
  loading,
  error,
  refetch,
  fetching,
}: {
  data: { items: OltMacEntry[]; total: number; limit: number } | undefined;
  loading: boolean;
  error: boolean;
  refetch: () => void;
  fetching: boolean;
}) {
  const [search, setSearch] = useState('');
  const [vidFilter, setVidFilter] = useState<string>('');
  const [ifaceFilter, setIfaceFilter] = useState<string>('');
  const [typeFilter, setTypeFilter] = useState<string>('');

  if (error) {
    return (
      <ErrorState
        title="Не удалось загрузить MAC-таблицу"
        message="OLT не отвечает или CLI недоступен."
        onRetry={refetch}
      />
    );
  }

  if (loading || !data) {
    return <SkeletonTable rows={8} cols={4} />;
  }

  const items = data.items;

  const vids = Array.from(new Set(items.map(i => i.vid))).sort((a, b) => a - b);
  const ifaces = Array.from(new Set(items.map(i => i.interface))).sort();

  const needle = search.trim().toLowerCase();
  const filtered = items.filter(i => {
    if (vidFilter && String(i.vid) !== vidFilter) return false;
    if (ifaceFilter && i.interface !== ifaceFilter) return false;
    if (typeFilter && i.type !== typeFilter) return false;
    if (needle && !i.mac.includes(needle) && !i.interface.toLowerCase().includes(needle)) {
      return false;
    }
    return true;
  });

  if (items.length === 0) {
    return (
      <div className="card p-6 text-center text-slate-400">
        MAC-таблица пуста
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {fetching && (
        <div className="text-xs text-slate-400 text-right">обновляю…</div>
      )}

      <section className="card p-3">
        <div className="flex flex-wrap gap-3 items-center">
          <div className="flex-1 min-w-[240px]">
            <input
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Поиск по MAC или интерфейсу…"
              className="input-base font-mono"
            />
          </div>
          <select
            value={vidFilter}
            onChange={e => setVidFilter(e.target.value)}
            className="select-base"
          >
            <option value="">Все VLAN</option>
            {vids.map(v => (
              <option key={v} value={String(v)}>VLAN {v}</option>
            ))}
          </select>
          <select
            value={ifaceFilter}
            onChange={e => setIfaceFilter(e.target.value)}
            className="select-base"
          >
            <option value="">Все интерфейсы</option>
            {ifaces.map(i => (
              <option key={i} value={i}>{i}</option>
            ))}
          </select>
          <select
            value={typeFilter}
            onChange={e => setTypeFilter(e.target.value)}
            className="select-base"
          >
            <option value="">Все типы</option>
            <option value="dynamic">Dynamic</option>
            <option value="static">Static</option>
          </select>
          <button
            onClick={() => refetch()}
            disabled={fetching}
            className="btn btn-secondary btn-sm"
          >
            {fetching ? 'Обновляю…' : '↻ Обновить'}
          </button>
        </div>
      </section>

      <section className="card">
        <div className="card-header flex items-center text-sm text-slate-500">
          <span className="flex-1">
            Найдено: {filtered.length}
            {filtered.length !== items.length && (
              <span className="ml-2 text-slate-400">
                (из {items.length})
              </span>
            )}
            <span className="ml-2 text-slate-400">
              · всего на OLT: {data.total} из {data.limit}
            </span>
          </span>
        </div>

        <table className="w-full text-sm">
          <thead className="text-slate-500 border-b border-slate-200">
            <tr>
              <th className="text-right p-3 w-24">VID</th>
              <th className="text-left p-3">MAC address</th>
              <th className="text-left p-3">Interface</th>
              <th className="text-left p-3 w-32">Type</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((m, idx) => (
              <tr
                key={`${m.vid}-${m.mac}-${idx}`}
                className="border-b border-slate-100 last:border-0 hover:bg-slate-50"
              >
                <td className="p-3 text-right font-mono">{m.vid}</td>
                <td className="p-3 font-mono">{m.mac}</td>
                <td className="p-3">{m.interface}</td>
                <td className="p-3">
                  <span
                    className={`px-2 py-0.5 rounded text-xs ${
                      m.type === 'static'
                        ? 'bg-indigo-100 text-indigo-800'
                        : 'bg-slate-100 text-slate-600'
                    }`}
                  >
                    {m.type}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {filtered.length === 0 && (
          <div className="p-6 text-center text-slate-400">
            Ничего не найдено по заданным фильтрам
          </div>
        )}
      </section>
    </div>
  );
}

// ---- Вкладка «Система» --------------------------------------------------

function SystemTab({
  system,
  loading,
  error,
  refetch,
  fetching,
}: {
  system: OltSystemInfo | undefined;
  loading: boolean;
  error: boolean;
  refetch: () => void;
  fetching: boolean;
}) {
  if (error) {
    return (
      <ErrorState
        title="Не удалось загрузить системную информацию"
        message="OLT не отвечает или SNMP недоступен."
        onRetry={refetch}
      />
    );
  }

  if (loading || !system) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {fetching && (
        <div className="text-xs text-slate-400 text-right">обновляю…</div>
      )}

      <section className="card p-4">
        <h2 className="text-sm font-medium text-slate-500 mb-3">Общее</h2>
        <div className="grid grid-cols-2 gap-x-8 gap-y-1 text-sm">
          <Row k="Uptime" v={formatUptime(system.uptime_sec)} />
          <Row k="MAC" v={system.mac ?? '—'} mono />
          <Row k="Hardware rev" v={system.hardware_rev ?? '—'} mono />
          <div className="col-span-2">
            <Row k="Firmware" v={system.firmware_rev ?? '—'} />
          </div>
        </div>
      </section>

      <section className="card p-4">
        <h2 className="text-sm font-medium text-slate-500 mb-3">
          Процессор и память
        </h2>
        <div className="grid grid-cols-2 gap-x-8 gap-y-1 text-sm">
          <Row k="CPU load, 1 мин" v={formatPercent(system.cpu_load_1m)} />
          <Row k="CPU load, 5 мин" v={formatPercent(system.cpu_load_5m)} />
          <Row k="CPU load, 15 мин" v={formatPercent(system.cpu_load_15m)} />
          <Row k="RAM (свободно)" v={formatMb(system.ram_free_bytes)} />
          <Row k="Disk (свободно)" v={formatKb(system.disk_free_kb)} />
        </div>
      </section>

      <section className="card p-4">
        <h2 className="text-sm font-medium text-slate-500 mb-3">Окружение</h2>
        <div className="grid grid-cols-2 gap-x-8 gap-y-1 text-sm">
          <Row k="Температура, датчик 1" v={formatTemp(system.sensor1_temp)} />
          <Row k="Температура, датчик 2" v={formatTemp(system.sensor2_temp)} />
          <Row k="Вентилятор 0" v={formatRpm(system.fan0_rpm)} />
          <Row k="Вентилятор 1" v={formatRpm(system.fan1_rpm)} />
        </div>
      </section>

      {system.psu.length > 0 && (
        <section className="card p-4">
          <h2 className="text-sm font-medium text-slate-500 mb-3">
            Блоки питания
          </h2>
          <table className="w-full text-sm">
            <thead className="text-slate-500 border-b border-slate-200">
              <tr>
                <th className="text-left p-2">№</th>
                <th className="text-left p-2">Модуль</th>
                <th className="text-left p-2">Тип</th>
                <th className="text-left p-2">Состояние</th>
              </tr>
            </thead>
            <tbody>
              {system.psu.map(p => (
                <tr key={p.index} className="border-b border-slate-100 last:border-0">
                  <td className="p-2">{p.index}</td>
                  <td className="p-2 font-mono">{p.name ?? '—'}</td>
                  <td className="p-2">{p.type ?? '—'}</td>
                  <td className="p-2">
                    {p.intact === true ? (
                      <span className="px-2 py-0.5 rounded text-xs bg-green-100 text-green-800">
                        OK
                      </span>
                    ) : p.intact === false ? (
                      <span className="px-2 py-0.5 rounded text-xs bg-red-100 text-red-800">
                        Сбой
                      </span>
                    ) : (
                      <span className="text-slate-400">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </div>
  );
}

// ---- Вкладка «VLAN» -----------------------------------------------------

function VlansTab({
  vlans,
  loading,
  error,
  refetch,
  fetching,
}: {
  vlans: OltVlan[] | undefined;
  loading: boolean;
  error: boolean;
  refetch: () => void;
  fetching: boolean;
}) {
  if (error) {
    return (
      <ErrorState
        title="Не удалось загрузить список VLAN"
        message="OLT не отвечает или SNMP недоступен."
        onRetry={refetch}
      />
    );
  }

  if (loading || !vlans) {
    return <SkeletonTable rows={5} cols={8} />;
  }

  if (vlans.length === 0) {
    return (
      <div className="card p-6 text-center text-slate-400">
        На этой OLT не найдено ни одной VLAN
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {fetching && (
        <div className="text-xs text-slate-400 text-right">обновляю…</div>
      )}

      <section className="card">
        <div className="card-header flex items-center">
          <span className="flex-1">VLAN ({vlans.length})</span>
        </div>

        <table className="w-full text-sm">
          <thead className="text-slate-500 border-b border-slate-200">
            <tr>
              <th className="text-right p-3">VID</th>
              <th className="text-left p-3">Имя</th>
              <th className="text-left p-3">Tagged</th>
              <th className="text-left p-3">Untagged</th>
              <th className="text-center p-3" title="IGMP snooping">IGMP</th>
              <th className="text-center p-3" title="IGMP querier">IGMP-Q</th>
              <th className="text-center p-3" title="MLD snooping">MLD</th>
              <th className="text-center p-3" title="MLD querier">MLD-Q</th>
            </tr>
          </thead>
          <tbody>
            {vlans.map(v => (
              <tr
                key={v.vid}
                className="border-b border-slate-100 last:border-0 hover:bg-slate-50"
              >
                <td className="p-3 text-right font-mono font-medium">{v.vid}</td>
                <td className="p-3">{v.name || '—'}</td>
                <td className="p-3">
                  <PortsList ports={v.tagged_ports_info} />
                </td>
                <td className="p-3">
                  <PortsList ports={v.untagged_ports_info} />
                </td>
                <td className="p-3 text-center">
                  <BoolBadge value={v.igmp_snooping} />
                </td>
                <td className="p-3 text-center">
                  <BoolBadge value={v.igmp_querier} />
                </td>
                <td className="p-3 text-center">
                  <BoolBadge value={v.mld_snooping} />
                </td>
                <td className="p-3 text-center">
                  <BoolBadge value={v.mld_querier} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}

// ---- Вкладка «Uplink» ---------------------------------------------------

function UplinksTab({
  uplinks,
  loading,
  error,
  refetch,
  fetching,
}: {
  uplinks: UplinkPort[] | undefined;
  loading: boolean;
  error: boolean;
  refetch: () => void;
  fetching: boolean;
}) {
  const [expanded, setExpanded] = useState<Set<number>>(new Set());

  const toggle = (ifIndex: number) => {
    setExpanded(prev => {
      const next = new Set(prev);
      if (next.has(ifIndex)) next.delete(ifIndex);
      else next.add(ifIndex);
      return next;
    });
  };

  if (error) {
    return (
      <ErrorState
        title="Не удалось загрузить состояние uplink-портов"
        message="OLT не отвечает или SNMP недоступен."
        onRetry={refetch}
      />
    );
  }

  if (loading || !uplinks) {
    return <SkeletonTable rows={6} cols={6} />;
  }

  if (uplinks.length === 0) {
    return (
      <div className="card p-6 text-center text-slate-400">
        Uplink-порты не найдены
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {fetching && (
        <div className="text-xs text-slate-400 text-right">обновляю…</div>
      )}

      <section className="card">
        <div className="card-header flex items-center">
          <span className="flex-1">Uplink-порты</span>
          <button
            onClick={() => refetch()}
            disabled={fetching}
            className="btn btn-secondary btn-sm"
          >
            {fetching ? 'Обновляю…' : '↻ Обновить'}
          </button>
        </div>

        <table className="w-full text-sm">
          <thead className="text-slate-500 border-b border-slate-200">
            <tr>
              <th className="text-left p-3 w-8"></th>
              <th className="text-left p-3">Порт</th>
              <th className="text-left p-3">State</th>
              <th className="text-left p-3">Speed</th>
              <th className="text-right p-3" title="Приём, kbit/s (last 30s)">
                ↓ RX
              </th>
              <th className="text-right p-3" title="Передача, kbit/s (last 30s)">
                ↑ TX
              </th>
            </tr>
          </thead>
          <tbody>
            {uplinks.map(u => {
              const up = u.oper_status === 'up';
              const isOpen = expanded.has(u.if_index);
              return (
                <>
                  <tr
                    key={u.if_index}
                    onClick={() => toggle(u.if_index)}
                    className="border-b border-slate-100 last:border-0 hover:bg-slate-50 cursor-pointer"
                  >
                    <td className="p-3 text-slate-400">
                      <span
                        className={`inline-block transition-transform ${
                          isOpen ? 'rotate-90' : ''
                        }`}
                      >
                        ▶
                      </span>
                    </td>
                    <td className="p-3 font-mono font-medium">{u.name}</td>
                    <td className="p-3">
                      <UplinkStateBadge status={u.oper_status} />
                    </td>
                    <td className="p-3 text-slate-600">
                      {formatLinkSpeed(u.speed_mbps)}
                    </td>
                    <td
                      className="p-3 text-right font-mono"
                      title={
                        u.avg_kbits_recv !== null && u.avg_kbits_recv !== undefined
                          ? `Среднее за 5 мин: ${formatKbit(u.avg_kbits_recv)}`
                          : undefined
                      }
                    >
                      {up && u.last_kbits_recv !== null ? (
                        formatKbit(u.last_kbits_recv)
                      ) : (
                        <span className="text-slate-300">—</span>
                      )}
                    </td>
                    <td
                      className="p-3 text-right font-mono"
                      title={
                        u.avg_kbits_sent !== null && u.avg_kbits_sent !== undefined
                          ? `Среднее за 5 мин: ${formatKbit(u.avg_kbits_sent)}`
                          : undefined
                      }
                    >
                      {up && u.last_kbits_sent !== null ? (
                        formatKbit(u.last_kbits_sent)
                      ) : (
                        <span className="text-slate-300">—</span>
                      )}
                    </td>
                  </tr>
                  {isOpen && (
                    <tr key={`${u.if_index}-details`} className="bg-slate-50">
                      <td colSpan={6} className="p-4">
                        <CountersBlock counters={u.counters} />
                      </td>
                    </tr>
                  )}
                </>
              );
            })}
          </tbody>
        </table>
      </section>
    </div>
  );
}

type CounterKind = 'bytes' | 'packets' | 'errors';

interface CounterRow {
  label: string;
  value: number | null;
  kind: CounterKind;
}

function CountersBlock({ counters }: { counters: UplinkCounters | null }) {
  if (!counters) {
    return (
      <div className="text-sm text-slate-400 text-center py-2">
        Счётчики недоступны (SNMP не ответил)
      </div>
    );
  }

  const rows: CounterRow[] = [
    { label: 'RX bytes', value: counters.rx_bytes, kind: 'bytes' },
    { label: 'TX bytes', value: counters.tx_bytes, kind: 'bytes' },
    { label: 'RX packets', value: counters.rx_pkts, kind: 'packets' },
    { label: 'TX packets', value: counters.tx_pkts, kind: 'packets' },
    { label: 'RX broadcast', value: counters.rx_broadcast, kind: 'packets' },
    { label: 'RX multicast', value: counters.rx_multicast, kind: 'packets' },
    { label: 'RX errors', value: counters.rx_errors, kind: 'errors' },
    { label: 'RX CRC errors', value: counters.rx_crc_errors, kind: 'errors' },
    { label: 'RX drops', value: counters.rx_drops, kind: 'errors' },
    { label: 'RX undersize', value: counters.rx_undersize, kind: 'errors' },
    { label: 'RX oversize', value: counters.rx_oversize, kind: 'errors' },
    { label: 'RX fragments', value: counters.rx_fragments, kind: 'errors' },
    { label: 'RX jabber', value: counters.rx_jabber, kind: 'errors' },
    { label: 'RX MAC errors', value: counters.rx_mac_errors, kind: 'errors' },
    { label: 'TX collisions', value: counters.tx_collisions, kind: 'errors' },
    { label: 'TX late collisions', value: counters.tx_late_collisions, kind: 'errors' },
    { label: 'TX MAC errors', value: counters.tx_mac_errors, kind: 'errors' },
    { label: 'Flow control (RX)', value: counters.rx_flow_control, kind: 'errors' },
    { label: 'Flow control (TX)', value: counters.tx_flow_control, kind: 'errors' },
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-x-6 gap-y-1.5 text-sm">
      {rows.map(r => {
        const hasValue = r.value !== null && r.value !== undefined;
        const isNonZero = hasValue && r.value !== 0;
        const isErrorField = r.kind === 'errors';
        const color = isErrorField && isNonZero ? 'text-red-700 font-semibold' : '';
        return (
          <div key={r.label} className="flex justify-between gap-3">
            <span className="text-slate-500 truncate">{r.label}</span>
            <span
              className={`font-mono tabular-nums shrink-0 ${color}`}
              title={hasValue ? (r.value as number).toString() : undefined}
            >
              {hasValue ? formatCounter(r.value as number, r.kind) : '—'}
            </span>
          </div>
        );
      })}
    </div>
  );
}

function formatCounter(v: number, kind: CounterKind): string {
  if (kind === 'bytes') return formatBytes(v);
  if (kind === 'packets') return formatPackets(v);
  return v.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
}

function formatBytes(v: number): string {
  if (v < 1024) return `${v} B`;
  const kb = v / 1024;
  if (kb < 1024) return `${kb.toFixed(2)} KB`;
  const mb = kb / 1024;
  if (mb < 1024) return `${mb.toFixed(2)} MB`;
  const gb = mb / 1024;
  if (gb < 1024) return `${gb.toFixed(2)} GB`;
  const tb = gb / 1024;
  if (tb < 1024) return `${tb.toFixed(2)} TB`;
  const pb = tb / 1024;
  return `${pb.toFixed(2)} PB`;
}

function formatPackets(v: number): string {
  if (v < 1000) return v.toString();
  const k = v / 1000;
  if (k < 1000) return `${k.toFixed(1)} K`;
  const m = k / 1000;
  if (m < 1000) return `${m.toFixed(1)} M`;
  const b = m / 1000;
  if (b < 1000) return `${b.toFixed(1)} B`;
  const t = b / 1000;
  return `${t.toFixed(1)} T`;
}

// ---- Вкладка «Профили» --------------------------------------------------

function ProfilesTab({
  oltId,
  profiles,
  loading,
  error,
  refetch,
  fetching,
}: {
  oltId: number;
  profiles: Record<string, ProfileItem[]> | undefined;
  loading: boolean;
  error: boolean;
  refetch: () => void;
  fetching: boolean;
}) {
  const [open, setOpen] = useState<Set<string>>(new Set());
  const initialized = useRef(false);

  const [details, setDetails] = useState<
    Record<string, ProfileDetails | 'loading' | 'error'>
  >({});

  if (profiles && !initialized.current) {
    const firstNonEmpty = ABONENT_PROFILE_TYPES.find(
      t => (profiles[t.key] ?? []).length > 0,
    );
    if (firstNonEmpty) {
      setOpen(new Set([firstNonEmpty.key]));
    }
    initialized.current = true;
  }

  const toggleSection = (key: string) => {
    setOpen(prev => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const handleRowClick = async (ptype: string, name: string) => {
    const key = `${ptype}/${name}`;
    const current = details[key];

    if (current && current !== 'loading' && current !== 'error') {
      const next = { ...details };
      delete next[key];
      setDetails(next);
      return;
    }

    setDetails(prev => ({ ...prev, [key]: 'loading' }));
    try {
      const data = await OntManageApi.profileDetails(oltId, ptype, name);
      setDetails(prev => ({ ...prev, [key]: data }));
    } catch {
      setDetails(prev => ({ ...prev, [key]: 'error' }));
    }
  };

  if (error) {
    return (
      <ErrorState
        title="Не удалось загрузить список профилей"
        message="OLT не отвечает или CLI недоступен."
        onRetry={refetch}
      />
    );
  }

  if (loading || !profiles) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-16 w-full" />
        <Skeleton className="h-16 w-full" />
        <Skeleton className="h-16 w-full" />
        <Skeleton className="h-16 w-full" />
        <Skeleton className="h-16 w-full" />
        <Skeleton className="h-16 w-full" />
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {fetching && (
        <div className="text-xs text-slate-400 text-right">обновляю…</div>
      )}

      {ABONENT_PROFILE_TYPES.map(t => {
        const items = profiles[t.key] ?? [];
        const isOpen = open.has(t.key);
        return (
          <section key={t.key} className="card">
            <button
              type="button"
              onClick={() => toggleSection(t.key)}
              className="w-full flex items-center gap-2 p-3 text-left hover:bg-slate-50 transition-colors"
            >
              <span
                className={`text-slate-400 transition-transform ${
                  isOpen ? 'rotate-90' : ''
                }`}
              >
                ▶
              </span>
              <span className="font-medium flex-1">{t.label}</span>
              <span className="text-sm text-slate-500">
                {items.length === 0 ? (
                  <span className="text-slate-300">—</span>
                ) : (
                  `${items.length}`
                )}
              </span>
            </button>

            {isOpen && (
              <div className="border-t border-slate-100">
                {items.length === 0 ? (
                  <div className="p-3 text-sm text-slate-400 text-center">
                    Профилей нет
                  </div>
                ) : (
                  <table className="w-full text-sm">
                    <thead className="text-slate-500 border-b border-slate-100">
                      <tr>
                        <th className="text-right p-2 w-12"></th>
                        <th className="text-right p-2 w-16">#</th>
                        <th className="text-left p-2">Имя</th>
                        <th className="text-left p-2">Описание</th>
                      </tr>
                    </thead>
                    <tbody>
                      {items.map(p => {
                        const key = `${t.key}/${p.name}`;
                        const detail = details[key];
                        const hasDetail =
                          detail && detail !== 'loading' && detail !== 'error';
                        return (
                          <>
                            <tr
                              key={key}
                              onClick={() => handleRowClick(t.key, p.name)}
                              className="border-b border-slate-50 last:border-0 hover:bg-slate-50 cursor-pointer"
                            >
                              <td className="p-2 text-slate-400 text-right">
                                <span
                                  className={`inline-block transition-transform ${
                                    hasDetail ? 'rotate-90' : ''
                                  }`}
                                >
                                  ▶
                                </span>
                              </td>
                              <td className="p-2 text-right font-mono text-slate-500">
                                {p.index}
                              </td>
                              <td className="p-2 font-medium">{p.name}</td>
                              <td className="p-2 text-slate-600">
                                {p.description || (
                                  <span className="text-slate-300">—</span>
                                )}
                              </td>
                            </tr>
                            {detail && (
                              <tr key={`${key}-detail`} className="bg-slate-50">
                                <td colSpan={4} className="p-4">
                                  {detail === 'loading' ? (
                                    <div className="text-sm text-slate-400">
                                      Загружаю…
                                    </div>
                                  ) : detail === 'error' ? (
                                    <div className="text-sm text-red-600">
                                      Не удалось загрузить параметры профиля
                                    </div>
                                  ) : (
                                    <ProfileDetailsBlock
                                      ptype={t.key}
                                      data={detail as ProfileDetails}
                                    />
                                  )}
                                </td>
                              </tr>
                            )}
                          </>
                        );
                      })}
                    </tbody>
                  </table>
                )}
              </div>
            )}
          </section>
        );
      })}
    </div>
  );
}

function ProfileDetailsBlock({
  ptype,
  data,
}: {
  ptype: string;
  data: ProfileDetails;
}) {
  if (ptype === 'voice') {
    return (
      <div className="text-sm text-slate-400">
        Параметры voice-профиля не отображаются
      </div>
    );
  }

  if (ptype === 'cross-connect') {
    return (
      <KVGrid
        rows={[
          ['Model', data.model],
          ['Bridge group', data.bridge_group],
          ['Tag mode', data.tag_mode],
          ['Outer vid', data.outer_vid],
          ['Outer cos', data.outer_cos],
          ['Inner vid', data.inner_vid],
          ['U vid', data.u_vid],
          ['U cos', data.u_cos],
          ['Type', data.type],
          ['Priority queue', data.priority_queue],
          ['MAC table limit', data.mac_table_entry_limit],
        ]}
      />
    );
  }

  if (ptype === 'dba') {
    return (
      <KVGrid
        rows={[
          ['Service class', data.service_class],
          ['Status reporting', data.status_reporting],
          ['Alloc size', data.alloc_size],
          ['Alloc period', data.alloc_period],
          ['Fixed bandwidth', data.fixed_bandwidth],
          ['Guaranteed bandwidth', data.guaranteed_bandwidth],
          ['Besteffort bandwidth', data.besteffort_bandwidth],
          ['T-CONT allocation', data.tcont_allocation_scheme],
        ]}
      />
    );
  }

  if (ptype === 'ports') {
    return (
      <div className="space-y-4 text-sm">
        <KVGrid
          rows={[
            ['Multicast IP version', data.multicast_ip_version],
            ['IGMP version', data.igmp_version],
            ['IGMP mode', data.igmp_mode],
            ['IGMP immediate leave', formatBool(data.igmp_immediate_leave)],
            ['IGMP robustness', data.igmp_robustness],
            ['IGMP query interval', data.igmp_query_interval],
            ['IGMP query response', data.igmp_query_response_interval],
            ['MLD version', data.mld_version],
            ['MLD mode', data.mld_mode],
          ]}
        />
        {data.ports && data.ports.length > 0 && (
          <div>
            <div className="text-slate-500 mb-2">Порты</div>
            <table className="w-full text-sm">
              <thead className="text-slate-500 border-b border-slate-200">
                <tr>
                  <th className="text-left p-2">Порт</th>
                  <th className="text-left p-2">Speed</th>
                  <th className="text-left p-2">Duplex</th>
                  <th className="text-left p-2">Bridge group</th>
                  <th className="text-left p-2">Multicast</th>
                </tr>
              </thead>
              <tbody>
                {data.ports.map(p => (
                  <tr key={p.port_id} className="border-b border-slate-100 last:border-0">
                    <td className="p-2 font-mono">Port [{p.port_id}]</td>
                    <td className="p-2">{p.speed ?? '—'}</td>
                    <td className="p-2">{p.duplex ?? '—'}</td>
                    <td className="p-2 font-mono">{p.bridge_group ?? '—'}</td>
                    <td className="p-2">{formatBool(p.multicast_enable)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    );
  }

  if (ptype === 'shaping') {
    return (
      <KVGrid
        rows={[
          ['One policer', formatBool(data.downstream_one_policer)],
          ['Policer[0] enable', formatBool(data.policer0_enable)],
          ['Policer[0] peak rate', data.policer0_peak_rate],
          ['Broadcast threshold', data.storm_broadcast_threshold],
          ['Broadcast logging', formatBool(data.storm_broadcast_logging)],
          ['Broadcast shutdown', formatBool(data.storm_broadcast_shutdown)],
          ['Multicast threshold', data.storm_multicast_threshold],
          ['Multicast logging', formatBool(data.storm_multicast_logging)],
          ['Multicast shutdown', formatBool(data.storm_multicast_shutdown)],
        ]}
      />
    );
  }

  if (ptype === 'management') {
    return (
      <KVGrid
        rows={[
          ['Name', data.name],
          ['Description', data.description],
        ]}
      />
    );
  }

  return (
    <pre className="text-xs font-mono bg-slate-100 p-2 rounded overflow-auto">
      {JSON.stringify(data, null, 2)}
    </pre>
  );
}

function KVGrid({
  rows,
}: {
  rows: [string, unknown][];
}) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-x-6 gap-y-1 text-sm">
      {rows.map(([k, v]) => (
        <div key={k} className="flex justify-between gap-3">
          <span className="text-slate-500 truncate">{k}</span>
          <span className="font-mono shrink-0">
            {v === null || v === undefined || v === '' ? (
              <span className="text-slate-300">—</span>
            ) : (
              String(v)
            )}
          </span>
        </div>
      ))}
    </div>
  );
}

function formatBool(v: boolean | null | undefined): string {
  if (v === true) return 'true';
  if (v === false) return 'false';
  return '—';
}

// ---- PortsList ----------------------------------------------------------

function PortsList({ ports }: { ports: PortInfo[] | undefined }) {
  if (!ports || ports.length === 0) {
    return <span className="text-slate-300">—</span>;
  }
  return (
    <div className="flex flex-wrap gap-1">
      {ports.map(p => (
        <span
          key={p.index}
          title={`${p.full} · switch index ${p.index}`}
          className="inline-block px-1.5 py-0.5 rounded text-xs bg-slate-100 text-slate-700 font-mono"
        >
          {p.short}
        </span>
      ))}
    </div>
  );
}

// ---- BoolBadge ----------------------------------------------------------

function BoolBadge({ value }: { value: boolean | null }) {
  if (value === true) {
    return <span className="text-green-600 font-medium">✓</span>;
  }
  if (value === false) {
    return <span className="text-slate-300">—</span>;
  }
  return <span className="text-slate-300">?</span>;
}

// ---- Вспомогательные компоненты -----------------------------------------

function UplinkStateBadge({ status }: { status: string | null }) {
  if (status === 'up') {
    return (
      <span className="px-2 py-0.5 rounded text-xs bg-green-100 text-green-800">
        up
      </span>
    );
  }
  if (status === 'down') {
    return (
      <span className="px-2 py-0.5 rounded text-xs bg-slate-100 text-slate-500">
        down
      </span>
    );
  }
  return (
    <span className="px-2 py-0.5 rounded text-xs bg-slate-50 text-slate-400">
      {status || '—'}
    </span>
  );
}

function PonStateBadge({ state }: { state: string }) {
  const map: Record<string, string> = {
    ok: 'bg-green-100 text-green-800',
    failed: 'bg-red-100 text-red-800',
    cfgFailed: 'bg-red-100 text-red-800',
    disabled: 'bg-slate-100 text-slate-600',
    free: 'bg-slate-100 text-slate-600',
    inited: 'bg-blue-100 text-blue-800',
    cfgInProgress: 'bg-blue-100 text-blue-800',
    redundant: 'bg-indigo-100 text-indigo-800',
    unknown: 'bg-slate-50 text-slate-400',
  };
  const cls = map[state] || map.unknown;
  return <span className={`px-2 py-0.5 rounded text-xs ${cls}`}>{state}</span>;
}

function PortRow({
  oltId,
  p,
  ontInDb,
}: {
  oltId: number;
  p: GponPortState;
  ontInDb: number;
}) {
  const isEmpty = p.state === 'unknown' && p.sfp_vendor === null;
  const hasSfp = !!p.sfp_vendor;
  const hasOnt = ontInDb > 0;

  return (
    <tr className="border-b border-slate-100 last:border-0 hover:bg-slate-50">
      <td className="p-3 font-mono">GPON-{p.gpon_port}</td>
      <td className="p-3">
        <PonStateBadge state={p.state} />
      </td>
      <td className="p-3 text-right font-mono">
        {isEmpty ? <span className="text-slate-300">—</span> : ontInDb}
      </td>
      <td className="p-3">
        {hasSfp ? (
          <div className="leading-tight">
            <div className="font-medium">{p.sfp_vendor}</div>
            <div className="text-xs text-slate-500">
              {p.sfp_product_number || '—'}
              {p.sfp_revision ? ` · rev.${p.sfp_revision}` : ''}
            </div>
          </div>
        ) : (
          <span className="text-slate-300">SFP не установлен</span>
        )}
      </td>
      <td className="p-3 text-right font-mono">
        {p.tx_power_dbm !== null ? (
          `${p.tx_power_dbm >= 0 ? '+' : ''}${p.tx_power_dbm.toFixed(2)}`
        ) : (
          <span className="text-slate-300">—</span>
        )}
      </td>
      <td className="p-3 text-right font-mono">
        {p.temperature_c !== null ? (
          p.temperature_c
        ) : (
          <span className="text-slate-300">—</span>
        )}
      </td>
      <td className="p-3 text-right font-mono">
        {p.voltage_v !== null ? (
          p.voltage_v.toFixed(3)
        ) : (
          <span className="text-slate-300">—</span>
        )}
      </td>
      <td className="p-3 text-right font-mono">
        {p.tx_bias_ma !== null ? (
          p.tx_bias_ma.toFixed(2)
        ) : (
          <span className="text-slate-300">—</span>
        )}
      </td>
      <td className="p-3 text-right">
        {hasOnt ? (
          <Link
            to={`/olts/${oltId}/onts?gpon_port=${p.gpon_port}`}
            className="btn btn-secondary btn-sm"
          >
            Список ONT
          </Link>
        ) : (
          <span className="text-slate-300">—</span>
        )}
      </td>
    </tr>
  );
}

function Metric({
  title,
  value,
  accent,
  pending,
}: {
  title: string;
  value: number | string;
  accent?: 'green' | 'red';
  pending?: boolean;
}) {
  const color =
    accent === 'green'
      ? 'text-green-700'
      : accent === 'red'
      ? 'text-red-700'
      : 'text-slate-900';
  return (
    <div className="card p-4">
      <div className="text-sm text-slate-500">{title}</div>
      <div className={`text-2xl font-semibold mt-1 ${color}`}>
        {pending ? <Skeleton className="h-8 w-16" /> : value}
      </div>
    </div>
  );
}

function Row({ k, v, mono }: { k: string; v: string | number; mono?: boolean }) {
  return (
    <div className="flex py-0.5">
      <div className="w-56 shrink-0 text-slate-500">{k}</div>
      <div className={mono ? 'font-mono' : ''}>{v}</div>
    </div>
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
      className={`px-4 py-2 text-sm border-b-2 transition-colors inline-flex items-center ${
        active
          ? 'border-accent-500 text-accent-700 font-medium'
          : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
      }`}
    >
      {children}
    </button>
  );
}

// ---- Утилиты ------------------------------------------------------------

function formatUptime(sec: number | null): string {
  if (sec === null || sec <= 0) return '—';
  const days = Math.floor(sec / 86400);
  const hours = Math.floor((sec % 86400) / 3600);
  const mins = Math.floor((sec % 3600) / 60);
  if (days > 0) return `${days} д ${hours} ч ${mins} мин`;
  if (hours > 0) return `${hours} ч ${mins} мин`;
  return `${mins} мин`;
}

function formatPercent(v: number | null): string {
  return v === null ? '—' : `${v} %`;
}

function formatMb(bytes: number | null): string {
  if (bytes === null) return '—';
  return `${(bytes / 1024 / 1024).toFixed(1)} МБ`;
}

function formatKb(kb: number | null): string {
  if (kb === null) return '—';
  if (kb > 1024 * 1024) return `${(kb / 1024 / 1024).toFixed(2)} ГБ`;
  if (kb > 1024) return `${(kb / 1024).toFixed(1)} МБ`;
  return `${kb} КБ`;
}

function formatTemp(t: number | null): string {
  return t === null ? '—' : `${t} °C`;
}

function formatRpm(rpm: number | null): string {
  return rpm === null ? '—' : `${rpm} RPM`;
}

function formatLinkSpeed(mbps: number | null): string {
  if (mbps === null || mbps === 0) return '—';
  if (mbps >= 1000) return `${mbps / 1000} Gbit/s`;
  return `${mbps} Mbit/s`;
}

function formatKbit(v: number | null): string {
  if (v === null) return '—';
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(2)} Gbit/s`;
  if (v >= 1_000) return `${(v / 1_000).toFixed(2)} Mbit/s`;
  return `${v} kbit/s`;
}