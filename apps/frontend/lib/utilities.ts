export function fmtTime(iso?: string): string {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleString(undefined, { dateStyle: "short", timeStyle: "short" });
}

export function fmtNumber(n: number | undefined | null): string {
  return (n ?? 0).toLocaleString();
}

export function shortId(id: string): string {
  return id.slice(0, 8);
}

export function cn(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(" ");
}
