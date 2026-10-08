"use client";

import Link from "next/link";
import { useState } from "react";
import { Card, EmptyState, ErrorState, Spinner, Stat, StatusBadge, useToast } from "@/components/ui";
import { cn, fmtNumber, fmtTime } from "@/lib/utilities";
import { useCases, useCreateCase } from "@/features/cases/hooks";
import { useProviders } from "@/features/providers/hooks";
import { ProviderStatusPanel } from "@/features/providers/components/ProviderStatusPanel";

function Radar() {
  return (
    <div className="relative grid h-40 w-40 place-items-center" aria-hidden="true">
      <div className="absolute inset-0 rounded-full border border-[#14305c]/70" />
      <div className="absolute inset-6 rounded-full border border-[#14305c]/60" />
      <div className="absolute inset-12 rounded-full border border-[#14305c]/50" />
      <div className="absolute inset-0 rounded-full bg-[radial-gradient(circle,rgba(76,201,240,0.10),transparent_70%)]" />
      <div className="absolute inset-x-0 top-1/2 h-px bg-[#14305c]/50" />
      <div className="absolute inset-y-0 left-1/2 w-px bg-[#14305c]/50" />
      <div
        className="absolute inset-0 rounded-full"
        style={{
          background: "conic-gradient(from 0deg, rgba(76,201,240,0.5), transparent 70deg)",
          animation: "radar-rotate 3s linear infinite",
        }}
      />
      <div className="absolute left-1/2 top-1/2 h-1.5 w-1.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-[#4cc9f0] shadow-[0_0_8px_#4cc9f0]" />
      <div className="absolute left-[30%] top-[24%] h-1 w-1 rounded-full bg-[#5ce0a0] shadow-[0_0_6px_#5ce0a0]" />
      <div className="absolute right-[26%] top-[58%] h-1 w-1 rounded-full bg-[#ffb454] shadow-[0_0_6px_#ffb454]" />
      <span className="relative text-[9px] uppercase tracking-[0.3em] text-[#4cc9f0]">scanning</span>
    </div>
  );
}

export function CommandHome() {
  const toast = useToast();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  const {
    data: cases,
    isLoading,
    isError: casesError,
  } = useCases();

  const {
    data: providers,
    isError: providersError,
  } = useProviders();

  const createMutation = useCreateCase();

  const analyzed = (cases || []).filter((c) => c.status === "ANALYZED");
  const totalEvidence = (cases || []).reduce((s, c) => s + (c.evidence_count || 0), 0);
  const llm = providers?.llm;

  return (
    <div className="space-y-8">
      <section aria-labelledby="command-heading" className="hud-panel hud-corners hud-scan relative rounded-md p-5 sm:p-6">
        <div className="grid items-center gap-6 lg:grid-cols-[1fr_auto]">
          <div>
            <p className="term text-[10px] uppercase tracking-[0.3em]">{"// command console online"}</p>
            <h1 id="command-heading" className="mt-2 text-2xl font-black uppercase tracking-[0.12em] text-[#dfe9f5] sm:text-3xl">
              Case Command<span className="text-[#4cc9f0]">.</span>
              <span aria-hidden="true" className="led-static ml-2 inline-block align-middle" style={{ background: "#5ce0a0" }} />
            </h1>
            <p className="mt-2 max-w-2xl text-xs leading-relaxed text-[#7e93b3]">
              Every case is explored as a set of <span className="text-[#dfe9f5]">evidence-compatible
              explanations</span>. Hard constraints eliminate; survivors are ranked by{" "}
              <span className="text-[#dfe9f5]">Evidence Consistency Score</span> — never a verdict.
            </p>
            <div className="mt-3 flex flex-wrap gap-2 text-[10px] uppercase tracking-[0.16em]">
              <span className="chip rounded-sm px-2 py-1">Eliminate by constraint</span>
              <span className="chip rounded-sm px-2 py-1">Adversarial review</span>
              <span className="chip rounded-sm px-2 py-1">3D reconstruction</span>
              <span className="chip rounded-sm px-2 py-1">Full audit trail</span>
            </div>
          </div>
          <div className="hidden lg:block">
            <Radar />
          </div>
        </div>
      </section>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className="enter enter-1">
          <Stat label="Open Cases" value={fmtNumber(cases?.length ?? 0)} accent="#dfe9f5" />
        </div>
        <div className="enter enter-2">
          <Stat label="Analyzed" value={fmtNumber(analyzed.length)} accent="#5ce0a0" />
        </div>
        <div className="enter enter-3">
          <Stat label="Evidence Items" value={fmtNumber(totalEvidence)} accent="#4cc9f0" />
        </div>
        <div className="enter enter-4">
          <Stat
            label="LLM Mode"
            value={llm?.is_mock ? "MOCK" : (llm?.provider || "?")}
            accent={llm?.is_mock ? "#ffb454" : "#5ce0a0"}
          />
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_340px]">
        <section aria-labelledby="board-heading" className="enter enter-3">
          <div className="mb-3 flex items-center justify-between">
            <h2 id="board-heading" className="hud-title">Case Command Board</h2>
            <span className="text-[10px] uppercase tracking-[0.18em] text-[#46597a]">
              {cases?.length ?? 0} total
            </span>
          </div>
          {isLoading ? (
            <Spinner />
          ) : casesError ? (
            <ErrorState message="Case files could not be loaded." />
          ) : !cases || cases.length === 0 ? (
            <EmptyState message="No case files on the board. Create a new case to begin." />
          ) : (
            <div className="space-y-2">
              {cases.map((c, i) => (
                <Link key={c.id} href={`/cases/${c.id}`} className={cn("enter", `enter-${Math.min(i + 1, 6)}`)}>
                  <Card className="hover-glow group flex items-center gap-4 p-4">
                    <span
                      aria-hidden="true"
                      className="hidden h-8 w-1.5 shrink-0 rounded-full sm:block"
                      style={{
                        background: c.status === "ANALYZED" ? "#5ce0a0" : c.status === "DRAFT" ? "#4cc9f0" : "#ffb454",
                        boxShadow: "0 0 8px currentColor",
                      }}
                    />
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="truncate text-sm font-bold text-[#dfe9f5]">{c.name}</p>
                        <StatusBadge status={c.status} />
                      </div>
                      {c.description && (
                        <p className="mt-1 line-clamp-1 text-xs text-[#7e93b3]">{c.description}</p>
                      )}
                    </div>
                    <div className="text-right text-[10px] uppercase tracking-[0.14em] text-[#7e93b3]">
                      <div className="tabular-nums">{c.evidence_count} evidence</div>
                      <div className="mt-1 text-[#46597a]">{fmtTime(c.created_at)}</div>
                    </div>
                    <span aria-hidden="true" className="text-[#4cc9f0] opacity-0 transition group-hover:opacity-100">▸</span>
                  </Card>
                </Link>
              ))}
            </div>
          )}
        </section>

        <section aria-labelledby="new-case-heading" className="enter enter-4">
          <h2 id="new-case-heading" className="hud-title mb-3">New Case File</h2>
          <Card className="p-4">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (!name.trim()) return;
                createMutation.mutate(
                  { name, description },
                  { onError: (err) => toast(err.message) }
                );
              }}
              className="space-y-3"
            >
              <div>
                <label htmlFor="new-case-name" className="mb-1 block text-[10px] uppercase tracking-[0.18em] text-[#7e93b3]">Case name</label>
                <input
                  id="new-case-name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                  placeholder="CASE: subject found injured…"
                  className="field rounded-sm px-3 py-2"
                />
              </div>
              <div>
                <label htmlFor="new-case-synopsis" className="mb-1 block text-[10px] uppercase tracking-[0.18em] text-[#7e93b3]">Synopsis</label>
                <textarea
                  id="new-case-synopsis"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  rows={4}
                  placeholder="Fictional scenario outline…"
                  className="field resize-none rounded-sm px-3 py-2"
                />
              </div>
              <button
                type="submit"
                disabled={createMutation.isPending || !name.trim()}
                className="btn-cmd w-full rounded-sm px-3 py-2.5"
              >
                {createMutation.isPending ? "Opening file…" : "Open new case file"}
              </button>
            </form>
          </Card>

          <ProviderStatusPanel providers={providers} isError={providersError} />
        </section>
      </div>
    </div>
  );
}
