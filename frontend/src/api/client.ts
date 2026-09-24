import axios from 'axios';
import { trackRequestStart, trackRequestEnd } from '../components/TopLoadingBar';

export const api = axios.create({ baseURL: '' });

api.interceptors.request.use(config => {
  trackRequestStart();
  return config;
});

api.interceptors.response.use(
  response => {
    trackRequestEnd();
    return response;
  },
  error => {
    trackRequestEnd();
    return Promise.reject(error);
  },
);

// ---- OLT ----------------------------------------------------------------

export interface Olt {
  id: number;
  ip: string;
  name: string | null;
  model: string | null;
  hw_revision: string | null;
  status: 'online' | 'offline' | 'unknown';
  last_ping_ms: number | null;
  last_seen_at: string | null;
  notes: string | null;
  created_at: string;
}

export interface Settings {
  cli_user: string | null;
  snmp_community_ro: string;
  snmp_community_rw: string | null;
  default_transport: 'ssh' | 'telnet';
  poll_interval_state_sec: number;
  poll_interval_rssi_sec: number;
  poll_interval_ping_sec: number;
  cli_password_set: boolean;
  updated_at: string | null;
}

export interface CheckResult {
  ip: string;
  ping_ok: boolean;
  ping_ms: number | null;
  snmp_ok: boolean;
  snmp_error: string | null;
  model: string | null;
  hw_revision: string | null;
}

export interface GponPortState {
  gpon_port: number;
  state: string;
  state_num: number | null;
  ont_count: number | null;
  sfp_vendor: string | null;
  sfp_product_number: string | null;
  sfp_revision: string | null;
  tx_power_dbm: number | null;
  temperature_c: number | null;
  voltage_v: number | null;
  tx_bias_ma: number | null;
}

export interface OltPsuInfo {
  index: number;
  name: string | null;
  type: string | null;
  intact: boolean | null;
}

export interface OltSystemInfo {
  uptime_sec: number | null;
  firmware_rev: string | null;
  hardware_rev: string | null;
  mac: string | null;

  cpu_load_1m: number | null;
  cpu_load_5m: number | null;
  cpu_load_15m: number | null;

  ram_free_bytes: number | null;
  disk_free_kb: number | null;

  fan0_rpm: number | null;
  fan1_rpm: number | null;
  sensor1_temp: number | null;
  sensor2_temp: number | null;

  psu: OltPsuInfo[];
}

export interface PortInfo {
  index: number;
  short: string;
  full: string;
}

export interface OltVlan {
  vid: number;
  slot: number | null;
  name: string | null;
  tagged_ports_hex: string | null;
  tagged_ports: number[];
  tagged_ports_info: PortInfo[];
  untagged_ports_hex: string | null;
  untagged_ports: number[];
  untagged_ports_info: PortInfo[];
  igmp_snooping: boolean | null;
  igmp_querier: boolean | null;
  igmp_query_interval: number | null;
  igmp_mrouter_ports?: number[];
  igmp_mrouter_ports_info?: PortInfo[];
  mld_snooping: boolean | null;
  mld_querier: boolean | null;
  mld_query_interval: number | null;
  mld_mrouter_ports?: number[];
  mld_mrouter_ports_info?: PortInfo[];
  isolation: boolean | null;
  mac_duplication: boolean | null;
  multicast_loopback: boolean | null;
}

// ---- Uplink-порты -------------------------------------------------------

export interface UplinkCounters {
  rx_bytes: number | null;
  tx_bytes: number | null;
  rx_pkts: number | null;
  tx_pkts: number | null;
  rx_errors: number | null;
  rx_bad_bytes: number | null;
  rx_crc_errors: number | null;
  rx_drops: number | null;
  rx_broadcast: number | null;
  rx_multicast: number | null;
  rx_undersize: number | null;
  rx_oversize: number | null;
  rx_fragments: number | null;
  rx_jabber: number | null;
  rx_mac_errors: number | null;
  tx_mac_errors: number | null;
  tx_collisions: number | null;
  tx_late_collisions: number | null;
  tx_flow_control: number | null;
  rx_flow_control: number | null;
  rx_bad_flow_control: number | null;
}

export interface UplinkPort {
  if_index: number;
  name: string;
  if_descr: string | null;
  oper_status: string | null;
  oper_status_num: number | null;
  speed_bps: number | null;
  speed_mbps: number | null;
  last_kbits_sent: number | null;
  last_kbits_recv: number | null;
  last_frames_sent: number | null;
  last_frames_recv: number | null;
  avg_kbits_sent: number | null;
  avg_kbits_recv: number | null;
  avg_frames_sent: number | null;
  avg_frames_recv: number | null;
  counters: UplinkCounters | null;
}

// ---- Профили ------------------------------------------------------------

export interface ProfileItem {
  index: number;
  name: string;
  description: string;
}

export interface ProfileDetails {
  name: string | null;
  description: string | null;
  model?: string | null;
  bridge_group?: number | null;
  tag_mode?: string | null;
  outer_vid?: number | null;
  outer_cos?: string | null;
  inner_vid?: string | null;
  u_vid?: string | null;
  u_cos?: string | null;
  mac_table_entry_limit?: string | null;
  type?: string | null;
  priority_queue?: number | null;
  service_class?: string | null;
  status_reporting?: string | null;
  alloc_size?: number | null;
  alloc_period?: number | null;
  fixed_bandwidth?: number | null;
  guaranteed_bandwidth?: number | null;
  besteffort_bandwidth?: number | null;
  tcont_allocation_scheme?: string | null;
  multicast_ip_version?: string | null;
  igmp_version?: string | null;
  igmp_mode?: string | null;
  igmp_immediate_leave?: boolean | null;
  igmp_robustness?: number | null;
  igmp_query_interval?: number | null;
  igmp_query_response_interval?: number | null;
  mld_version?: string | null;
  mld_mode?: string | null;
  ports?: {
    port_id: number;
    speed: string | null;
    duplex: string | null;
    bridge_group: number | null;
    multicast_enable: boolean | null;
  }[];
  downstream_one_policer?: boolean | null;
  policer0_enable?: boolean | null;
  policer0_peak_rate?: number | null;
  storm_broadcast_threshold?: number | null;
  storm_broadcast_logging?: boolean | null;
  storm_broadcast_shutdown?: boolean | null;
  storm_multicast_threshold?: number | null;
  storm_multicast_logging?: boolean | null;
  storm_multicast_shutdown?: boolean | null;
}

// ---- Глобальный поиск ONT -----------------------------------------------

export interface GlobalOntSearchItem {
  olt_id: number;
  olt_name: string;
  olt_ip: string;
  gpon_port: number;
  ont_id: number;
  serial: string;
  status: string;
  rssi_db: number | null;
  version: string | null;
  equipment_id: string | null;
  description: string | null;
  last_seen_at: string | null;
}

// ---- Активные аварии OLT ------------------------------------------------

export interface OltAlarm {
  index: number;
  type: string;
  severity: string;        // lowercase: info | minor | major | critical
  severity_raw: string;    // как в CLI: Info | Minor | Major | Critical
  description: string;
  ont_gpon_port: number | null;
  ont_id: number | null;
  ont_serial: string | null;
}
// ---- MAC-таблица коммутатора OLT ----------------------------------------

export interface OltMacEntry {
  vid: number;
  mac: string;
  interface: string;       // "front-port 0", "pon-port 1", "mgmt-pon-port 0", "CPU"
  type: 'dynamic' | 'static';
}

export interface OltMacTableResponse {
  items: OltMacEntry[];
  total: number;
  limit: number;
}
// ---- Сводка для главной ------------------------------------------------

export interface DashboardSummary {
  olts_total: number;
  olts_online: number;
  olts_offline: number;
  onts_total: number;
  onts_ok: number;
  onts_offline: number;
  onts_other: number;
}

export const DashboardApi = {
  summary: () =>
    api.get<DashboardSummary>('/api/dashboard/summary').then(r => r.data),
};

export const OltsApi = {
  list: () => api.get<Olt[]>('/api/olts').then(r => r.data),
  get: (id: number) => api.get<Olt>(`/api/olts/${id}`).then(r => r.data),
  add: (ip: string, name?: string, notes?: string) =>
    api.post<Olt>('/api/olts', { ip, name, notes }).then(r => r.data),
  patch: (id: number, data: { name?: string; notes?: string }) =>
    api.patch<Olt>(`/api/olts/${id}`, data).then(r => r.data),
  remove: (id: number) => api.delete(`/api/olts/${id}`),
  check: (id: number) =>
    api.post<CheckResult>(`/api/olts/${id}/check`).then(r => r.data),
  checkAll: () =>
    api.post<CheckResult[]>('/api/olts/check-all').then(r => r.data),
  gponPorts: (id: number) =>
    api.get<GponPortState[]>(`/api/olts/${id}/gpon-ports`).then(r => r.data),
  system: (id: number) =>
    api.get<OltSystemInfo>(`/api/olts/${id}/system`).then(r => r.data),
  vlans: (id: number) =>
    api.get<OltVlan[]>(`/api/olts/${id}/vlans`).then(r => r.data),
  uplinks: (id: number) =>
    api
      .get<{ ports: UplinkPort[] }>(`/api/olts/${id}/uplinks`)
      .then(r => r.data.ports),
  alarms: (id: number) =>
    api
      .get<{ items: OltAlarm[]; total: number }>(`/api/olts/${id}/alarms`)
      .then(r => r.data),
  macs: (id: number) =>
    api
      .get<OltMacTableResponse>(`/api/olts/${id}/macs`)
      .then(r => r.data),
};

export const SettingsApi = {
  get: () => api.get<Settings>('/api/settings').then(r => r.data),
  put: (data: Partial<Settings> & { cli_password?: string }) =>
    api.put<Settings>('/api/settings', data).then(r => r.data),
  test: (ip: string, transport?: 'ssh' | 'telnet') =>
    api
      .post<{ ip: string; transport: string; ok: boolean; error: string | null }>(
        '/api/settings/test-connection',
        { ip, transport },
      )
      .then(r => r.data),
};

// ---- ONT ----------------------------------------------------------------

export interface Ont {
  id: number;
  olt_id: number;
  gpon_port: number;
  ont_id: number;
  serial: string;
  status: string;
  rssi_db: number | null;
  version: string | null;
  equipment_id: string | null;
  description: string | null;
  last_seen_at: string | null;
  updated_at: string;
}

export interface OntsSummary {
  total: number;
  by_status: Record<string, number>;
  by_port: Record<string, Record<string, number>>;
}

export interface RssiPoint {
  ts: string;
  rssi_db: number;
}

export interface RssiHistory {
  ont_id: number;
  gpon_port: number;
  hours: number;
  points: RssiPoint[];
}

export const OntsApi = {
  summary: (oltId: number) =>
    api.get<OntsSummary>(`/api/olts/${oltId}/onts/summary`).then(r => r.data),

  list: (
    oltId: number,
    opts?: { status?: string; gpon_port?: number; search?: string },
  ) =>
    api.get<Ont[]>(`/api/olts/${oltId}/onts`, { params: opts }).then(r => r.data),

  get: (oltId: number, port: number, ontId: number) =>
    api.get<Ont>(`/api/olts/${oltId}/onts/${port}/${ontId}`).then(r => r.data),

  rssiHistory: (oltId: number, port: number, ontId: number, hours = 24) =>
    api
      .get<RssiHistory>(
        `/api/olts/${oltId}/onts/${port}/${ontId}/rssi-history`,
        { params: { hours } },
      )
      .then(r => r.data),

  configuration: (oltId: number, port: number, ontId: number) =>
    api
      .get<OntFullConfig>(
        `/api/olts/${oltId}/onts/${port}/${ontId}/configuration`,
      )
      .then(r => r.data),

  globalSearch: (q: string, limit = 200) =>
    api
      .get<{ items: GlobalOntSearchItem[]; total: number; limit: number }>(
        '/api/onts/search',
        { params: { q, limit } },
      )
      .then(r => r.data),
};

// ---- Действия с ONT -----------------------------------------------------

export type OntAction =
  | 'reconfigure'
  | 'reset'
  | 'restore'
  | 'enable'
  | 'disable'
  | 'replace-serial'
  | 'delete';

export interface OntActionResponse {
  ok: boolean;
  output: string;
  error: string | null;
}

export const OntActionsApi = {
  run: (
    oltId: number,
    port: number,
    ontId: number,
    action: OntAction,
    newSerial?: string,
  ) =>
    api
      .post<OntActionResponse>(
        `/api/olts/${oltId}/onts/${port}/${ontId}/actions/${action}`,
        { confirm: true },
        { params: newSerial ? { new_serial: newSerial } : undefined },
      )
      .then(r => r.data),
};

// ---- Автообнаружение и добавление ONT -----------------------------------

export interface UnactivatedOnt {
  gpon_port: number;
  ont_id: number | null;
  serial: string;
  status: string;
  rssi_db: number | null;
  version: string | null;
  equipment_id: string | null;
  description: string | null;
}

export interface CliResult {
  ok: boolean;
  output: string;
  error: string | null;
}

export interface OntAddPayload {
  gpon_port: number;
  ont_id: number;
  serial: string;
  description?: string | null;
  template?: string | null;
  profile_cross_connect?: string | null;
  profile_dba?: string | null;
  profile_ports?: string | null;
  profile_management?: string | null;
}

export const OntManageApi = {
  autofind: (oltId: number, enable: boolean, ports?: number[]) =>
    api
      .post<CliResult>(`/api/olts/${oltId}/autofind`, { enable, ports })
      .then(r => r.data),

  unactivated: (oltId: number) =>
    api
      .get<{ items: UnactivatedOnt[]; total: number }>(
        `/api/olts/${oltId}/onts/unactivated`,
      )
      .then(r => r.data.items),

  nextFreeId: (oltId: number, gponPort: number) =>
    api
      .get<{ ont_id: number }>(
        `/api/olts/${oltId}/onts/next-free-id`,
        { params: { gpon_port: gponPort } },
      )
      .then(r => r.data.ont_id),

  add: (oltId: number, payload: OntAddPayload) =>
    api
      .post<CliResult>(`/api/olts/${oltId}/onts`, payload)
      .then(r => r.data),

  profiles: (oltId: number, ptype: string) =>
    api
      .get<{ items: ProfileItem[] }>(`/api/olts/${oltId}/profiles/${ptype}`)
      .then(r => r.data.items),

  profileDetails: (oltId: number, ptype: string, name: string) =>
    api
      .get<{ params: ProfileDetails }>(
        `/api/olts/${oltId}/profiles/${ptype}/${encodeURIComponent(name)}`,
      )
      .then(r => r.data.params),

  templates: (oltId: number) =>
    api
      .get<{ items: ProfileItem[] }>(`/api/olts/${oltId}/templates`)
      .then(r => r.data.items),
};

// ---- Полная конфигурация ONT --------------------------------------------

export interface OntServiceConfig {
  service_id: number;
  profile_cross_connect: string | null;
  profile_cross_connect_desc: string | null;
  profile_dba: string | null;
  profile_dba_desc: string | null;
  custom_cross_connect: string;
  custom_svid: number | null;
  custom_cvid: number | null;
  custom_cos: number | null;
  selective_tunnel_user_vlans: string | null;
}

export interface OntPortConfig {
  port_id: number;
  shutdown: boolean;
  poe_enable: boolean;
  poe_pse_class_control: number;
  poe_power_priority: string | null;
}

export interface OntFullConfig {
  description: string | null;
  enabled: boolean;
  serial: string | null;
  password: string | null;
  fec_up: boolean;
  easy_mode: boolean;
  downstream_broadcast: boolean;
  downstream_broadcast_filter: boolean;
  downstream_multicast_filter: boolean;
  ber_interval: string | null;
  ber_update_period: number;
  rf_port_state: string | null;
  omci_error_tolerant: boolean;

  services: OntServiceConfig[];

  profile_shaping: string | null;
  profile_ports: string | null;
  profile_management: string | null;
  profile_voice: string | null;
  template: string | null;

  pppoe_sessions_unlimited: boolean;
  collect_utilization_statistics: boolean;

  ports: OntPortConfig[];
}

// ---- Редактирование общих параметров ONT --------------------------------

export interface OntGeneralEditPayload {
  description?: string | null;
  password?: string | null;
  fec_up?: boolean;
  easy_mode?: boolean;
  downstream_broadcast?: boolean;
  downstream_broadcast_filter?: boolean;
  downstream_multicast_filter?: boolean;
  omci_error_tolerant?: boolean;
  rf_port_state?: string;
  profile_ports?: string | null;
  profile_management?: string | null;
  profile_shaping?: string | null;
  profile_voice?: string | null;
  template?: string | null;
}

export interface OntGeneralEditResponse {
  ok: boolean;
  output: string;
  error: string | null;
  changes: string[];
}

export const OntEditApi = {
  updateGeneral: (
    oltId: number, port: number, ontId: number,
    payload: OntGeneralEditPayload,
  ) =>
    api
      .put<OntGeneralEditResponse>(
        `/api/olts/${oltId}/onts/${port}/${ontId}/general`,
        payload,
      )
      .then(r => r.data),
};

// ---- Сервисы ONT --------------------------------------------------------

export interface OntServiceEditPayload {
  profile_cross_connect?: string | null;
  profile_dba?: string | null;
  custom_enabled?: boolean;
  cvid?: number;
  svid?: number;
  cos?: number;
  selective_tunnel_uvid?: string;
  utilization_enable?: boolean;
}

export interface OntServiceEditResponse {
  ok: boolean;
  output: string;
  error: string | null;
  changes: string[];
}

export const OntServicesApi = {
  update: (
    oltId: number, port: number, ontId: number, serviceId: number,
    payload: OntServiceEditPayload,
  ) =>
    api
      .put<OntServiceEditResponse>(
        `/api/olts/${oltId}/onts/${port}/${ontId}/services/${serviceId}`,
        payload,
      )
      .then(r => r.data),

  remove: (oltId: number, port: number, ontId: number, serviceId: number) =>
    api
      .delete<OntServiceEditResponse>(
        `/api/olts/${oltId}/onts/${port}/${ontId}/services/${serviceId}`,
      )
      .then(r => r.data),
};

// ---- MAC-адреса ONT -----------------------------------------------------

export interface OntMacEntry {
  gpon_port: number;
  ont_id: number;
  gem: number | null;
  uvid: number | null;
  cvid: number | null;
  svid: number | null;
  mac: string;
}

export interface OntMacsResponse {
  items: OntMacEntry[];
  total: number;
}

export interface OntMacsSummaryResponse {
  by_ont: Record<string, string[]>;
}

export const OntMacsApi = {
  forOnt: (oltId: number, port: number, ontId: number) =>
    api
      .get<OntMacsResponse>(`/api/olts/${oltId}/onts/${port}/${ontId}/macs`)
      .then(r => r.data),

  summary: (oltId: number) =>
    api
      .get<OntMacsSummaryResponse>(`/api/olts/${oltId}/onts/macs-summary`)
      .then(r => r.data.by_ont),

  clearCache: (oltId: number) =>
    api
      .post<{ ok: boolean }>(`/api/olts/${oltId}/onts/macs-cache/clear`)
      .then(r => r.data),
};

// ---- Порты ONT ----------------------------------------------------------

export interface OntPortState {
  port_id: number;
  link: string | null;
  speed: string | null;
  duplex: string | null;
  poe_state: string | null;
}

export interface OntPortsResponse {
  items: OntPortState[];
  total: number;
}

export const OntPortsApi = {
  forOnt: (oltId: number, port: number, ontId: number) =>
    api
      .get<OntPortsResponse>(`/api/olts/${oltId}/onts/${port}/${ontId}/ports`)
      .then(r => r.data),
};