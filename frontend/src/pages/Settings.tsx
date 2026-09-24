import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { SettingsApi, Settings as SettingsT } from '../api/client';

type FormState = Partial<SettingsT> & { cli_password?: string };

export default function Settings() {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ['settings'], queryFn: SettingsApi.get });

  const [form, setForm] = useState<FormState>({});
  const [testIp, setTestIp] = useState('');

  useEffect(() => { if (data) setForm({ ...data, cli_password: '' }); }, [data]);

  const saveMut = useMutation({
    mutationFn: () => SettingsApi.put(form),
    onSuccess: () => {
      toast.success('Настройки сохранены');
      qc.invalidateQueries({ queryKey: ['settings'] });
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || 'Не удалось сохранить'),
  });

  const testMut = useMutation({
    mutationFn: () => SettingsApi.test(testIp, form.default_transport as 'ssh' | 'telnet'),
    onSuccess: (r: any) => {
      if (r.ok) {
        toast.success(`Подключение ${r.transport.toUpperCase()} к ${r.ip}: OK`);
      } else {
        toast.error(`Не удалось подключиться к ${r.ip}`, { description: r.error, duration: 10000 });
      }
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || 'Ошибка запроса'),
  });

  const upd = <K extends keyof FormState>(k: K, v: FormState[K]) =>
    setForm(f => ({ ...f, [k]: v }));

  return (
    <div className="max-w-2xl">
      <h1 className="text-xl font-semibold mb-4">Настройки</h1>

      <section className="card p-4 mb-4">
        <h2 className="font-medium mb-3">Учётные данные CLI (единые для всех OLT)</h2>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-sm mb-1 text-slate-600">Логин</label>
            <input
              value={form.cli_user ?? ''}
              onChange={e => upd('cli_user', e.target.value)}
              className="input-base"
            />
          </div>
          <div>
            <label className="block text-sm mb-1 text-slate-600">
              Пароль {data?.cli_password_set ? '(уже задан, оставьте пустым)' : ''}
            </label>
            <input
              type="password"
              value={form.cli_password ?? ''}
              onChange={e => upd('cli_password', e.target.value)}
              placeholder="Оставьте пустым, чтобы не менять"
              className="input-base"
            />
          </div>
        </div>

        <div className="mt-3">
          <label className="block text-sm mb-1 text-slate-600">Транспорт CLI по умолчанию</label>
          <select
            value={form.default_transport ?? 'telnet'}
            onChange={e => upd('default_transport', e.target.value as any)}
            className="select-base w-40"
          >
            <option value="telnet">Telnet</option>
            <option value="ssh">SSH</option>
          </select>
        </div>
      </section>

      <section className="card p-4 mb-4">
        <h2 className="font-medium mb-3">SNMP</h2>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-sm mb-1 text-slate-600">Community (read-only)</label>
            <input
              value={form.snmp_community_ro ?? ''}
              onChange={e => upd('snmp_community_ro', e.target.value)}
              className="input-base font-mono"
            />
          </div>
          <div>
            <label className="block text-sm mb-1 text-slate-600">Community (read-write)</label>
            <input
              value={form.snmp_community_rw ?? ''}
              onChange={e => upd('snmp_community_rw', e.target.value)}
              className="input-base font-mono"
            />
          </div>
        </div>
      </section>

      <section className="card p-4 mb-4">
        <h2 className="font-medium mb-3">Интервалы опроса</h2>
        <div className="grid grid-cols-3 gap-3">
          <div>
            <label className="block text-sm mb-1 text-slate-600">Состояние ONT, с</label>
            <input
              type="number"
              value={form.poll_interval_state_sec ?? 15}
              onChange={e => upd('poll_interval_state_sec', +e.target.value)}
              className="input-base"
            />
          </div>
          <div>
            <label className="block text-sm mb-1 text-slate-600">RSSI, с</label>
            <input
              type="number"
              value={form.poll_interval_rssi_sec ?? 60}
              onChange={e => upd('poll_interval_rssi_sec', +e.target.value)}
              className="input-base"
            />
          </div>
          <div>
            <label className="block text-sm mb-1 text-slate-600">Ping, с</label>
            <input
              type="number"
              value={form.poll_interval_ping_sec ?? 60}
              onChange={e => upd('poll_interval_ping_sec', +e.target.value)}
              className="input-base"
            />
          </div>
        </div>
      </section>

      <div className="flex gap-2 mb-6">
        <button
          onClick={() => saveMut.mutate()}
          disabled={saveMut.isPending}
          className="btn btn-primary"
        >
          {saveMut.isPending ? 'Сохраняю…' : 'Сохранить'}
        </button>
      </div>

      <section className="card p-4">
        <h2 className="font-medium mb-3">Проверить подключение</h2>
        <div className="flex gap-2">
          <input
            value={testIp}
            onChange={e => setTestIp(e.target.value)}
            placeholder="IP OLT, например 10.10.1.105"
            className="input-base flex-1 font-mono"
          />
          <button
            onClick={() => testMut.mutate()}
            disabled={!testIp || testMut.isPending}
            className="btn btn-secondary"
          >
            {testMut.isPending ? 'Проверяю…' : 'Проверить'}
          </button>
        </div>
        <p className="text-xs text-slate-500 mt-2">
          Перед проверкой нажмите «Сохранить», если только что меняли логин/пароль.
        </p>
      </section>
    </div>
  );
}