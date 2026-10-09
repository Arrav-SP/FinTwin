/** Values arrive from the API as numbers, decimal strings, or null. */
export type Numeric = number | string | null | undefined;

const MISSING = "—";

export function toNumber(value: Numeric): number | null {
  if (value === null || value === undefined || value === "") return null;
  const parsed = typeof value === "number" ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function formatNumber(value: Numeric, digits = 1): string {
  const parsed = toNumber(value);
  return parsed === null ? MISSING : parsed.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

export function formatInteger(value: Numeric): string {
  return formatNumber(value, 0);
}

export function formatPercent(value: Numeric, digits = 1): string {
  const formatted = formatNumber(value, digits);
  return formatted === MISSING ? MISSING : `${formatted}%`;
}

export function scenarioLabel(code: string | null | undefined): string {
  if (!code) return MISSING;
  const words = code.toLowerCase().replaceAll("_", " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

export function shortId(id: string | null | undefined): string {
  return id ? id.slice(0, 8) : MISSING;
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return MISSING;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? MISSING : date.toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}
