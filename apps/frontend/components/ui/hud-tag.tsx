"use client";

export function HudTag({ children }: { children: React.ReactNode }) {
  return <span className="chip inline-block rounded-sm px-1.5 py-0.5 uppercase tracking-[0.12em]">{children}</span>;
}
