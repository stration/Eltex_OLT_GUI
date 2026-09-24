/**
 * Утилиты форматирования.
 *
 * Создать папку `src/lib`, если её ещё нет.
 */

/**
 * Форматирует ISO-дату в «человеческий» вид:
 *   < 30 сек   → «только что»
 *   < 60 мин   → «5 минут назад»
 *   < 24 ч     → «2 часа назад»
 *   вчера      → «вчера в 11:33»
 *   < 7 дней   → «3 дня назад»
 *   иначе      → «23.09.2026, 11:33»
 */
export function formatRelativeTime(iso: string | null | undefined): string {
  if (!iso) return '—';

  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return '—';

  const now = Date.now();
  const diffSec = Math.floor((now - t) / 1000);

  if (diffSec < 30) return 'только что';
  if (diffSec < 60) return `${diffSec} сек назад`;

  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) {
    return `${diffMin} ${plural(diffMin, 'минуту', 'минуты', 'минут')} назад`;
  }

  const diffHours = Math.floor(diffMin / 60);
  if (diffHours < 24) {
    return `${diffHours} ${plural(diffHours, 'час', 'часа', 'часов')} назад`;
  }

  const d = new Date(t);
  const nowD = new Date(now);
  const isYesterday =
    d.getDate() === nowD.getDate() - 1 &&
    d.getMonth() === nowD.getMonth() &&
    d.getFullYear() === nowD.getFullYear();

  if (isYesterday) {
    const hh = pad2(d.getHours());
    const mm = pad2(d.getMinutes());
    return `вчера в ${hh}:${mm}`;
  }

  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 7) {
    return `${diffDays} ${plural(diffDays, 'день', 'дня', 'дней')} назад`;
  }

  return formatFullDateTime(d);
}

/** «23.09.2026, 11:33» */
export function formatFullDateTime(d: Date): string {
  const dd = pad2(d.getDate());
  const mm = pad2(d.getMonth() + 1);
  const yyyy = d.getFullYear();
  const hh = pad2(d.getHours());
  const mi = pad2(d.getMinutes());
  return `${dd}.${mm}.${yyyy}, ${hh}:${mi}`;
}

function pad2(n: number): string {
  return n < 10 ? `0${n}` : String(n);
}

function plural(n: number, one: string, few: string, many: string): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return one;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return few;
  return many;
}