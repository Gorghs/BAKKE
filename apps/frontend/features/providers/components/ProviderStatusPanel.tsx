"use client";

import type { ProviderStatus } from "@/lib/types";
import { Led } from "@/components/ui";

export function ProviderStatusPanel({
  providers,
  isError,
}: {
  providers?: ProviderStatus;
  isError?: boolean;
}) {
  const llm = providers?.llm;
  return (
    <div className="hud-panel hud-corners mt-4 p-3 text-[10px] uppercase tracking-[0.16em] text-[#46597a]">
      <div className="mb-2 flex items-center gap-2 text-[#7e93b3]">
        <Led color={llm?.is_mock ? "#ffb454" : "#5ce0a0"} /> Provider status
      </div>
      {isError ? (
        <p className="term-danger text-[10px]">Provider status unavailable.</p>
      ) : (
        <div className="grid grid-cols-2 gap-1">
          {providers &&
            Object.entries(providers)
              .filter(([k]) => k !== "note")
              .map(([k, v]) => {
                const isMock = (v as { is_mock?: boolean })?.is_mock;
                return (
                  <div key={k} className="flex items-center gap-1.5">
                    <span
                      aria-hidden="true"
                      className="led-static"
                      style={{ background: isMock ? "#ffb454" : "#5ce0a0" }}
                    />
                    <span className="truncate">
                      {k}: {isMock ? "mock" : "live"}
                    </span>
                  </div>
                );
              })}
        </div>
      )}
    </div>
  );
}
