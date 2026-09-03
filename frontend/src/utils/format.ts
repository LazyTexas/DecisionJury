// ============================================================
// 展示格式化工具
// 后端时间格式不统一：DB 输出 naive UTC（无时区标记），
// 判决书 / mock 数据带 +08:00 或 Z。这里统一解析后按本地时区展示。
// ============================================================

const TZ_PATTERN = /(Z|[+-]\d{2}:?\d{2})$/i;

/** 解析后端时间字符串；naive（无时区标记）按 UTC 解释，返回 Date | null */
export function parseServerTime(value: string | null | undefined): Date | null {
  if (!value) return null;
  const trimmed = value.trim();
  if (!trimmed) return null;
  const hasTz = TZ_PATTERN.test(trimmed);
  const parsed = new Date(hasTz ? trimmed : `${trimmed}Z`);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

/** 仅日期：2026-07-05 */
export function formatDate(value: string | null | undefined): string {
  const d = parseServerTime(value);
  if (!d) return '—';
  return d.toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' });
}

/** 日期 + 时间：2026-07-05 14:30 */
export function formatDateTime(value: string | null | undefined): string {
  const d = parseServerTime(value);
  if (!d) return '—';
  return d.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  });
}
