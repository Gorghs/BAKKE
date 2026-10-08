"use client";

import { useParams } from "next/navigation";
import { useState } from "react";
import {
  Card,
  EmptyState,
  ErrorState,
  SectionTitle,
  Spinner,
  StatusBadge,
} from "@/components/ui";
import { cn, fmtTime } from "@/lib/utilities";
import { useEvidence, useUploadEvidence } from "@/features/evidence/hooks";

const ITEM_TYPES = [
  "POST_MORTEM_REPORT",
  "FORENSIC_REPORT",
  "INVESTIGATOR_REPORT",
  "WITNESS_STATEMENT",
  "AUDIO",
  "IMAGE",
  "VIDEO",
  "DOCUMENT",
];

export function EvidencePanel() {
  const { id } = useParams<{ id: string }>();
  const [itemType, setItemType] = useState("DOCUMENT");
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);

  const { data: evidence, isLoading, isError } = useEvidence(id);
  const uploadMutation = useUploadEvidence(id);

  return (
    <div className="grid gap-8 lg:grid-cols-[1fr_340px]">
      <section aria-labelledby="evidence-heading">
        <div className="mb-3 flex items-center justify-between">
          <SectionTitle>
            <span id="evidence-heading">Evidence items</span>
          </SectionTitle>
          <span className="text-[10px] uppercase tracking-[0.18em] text-[#46597a]" aria-live="polite">
            {evidence?.length ?? 0} items
          </span>
        </div>
        {isLoading ? (
          <Spinner />
        ) : isError ? (
          <ErrorState message="Evidence items could not be loaded." />
        ) : !evidence || evidence.length === 0 ? (
          <EmptyState message="No evidence logged in this case file." />
        ) : (
          <div className="space-y-2">
            {evidence.map((e, i) => (
              <Card key={e.id} className={cn("hover-glow hud-sweep flex items-center gap-3 p-3", "enter", `enter-${Math.min(i + 1, 6)}`)}>
                <span
                  aria-hidden="true"
                  className="led-static hidden shrink-0 sm:block"
                  style={{ background: e.status === "UPLOADED" ? "#ffb454" : "#5ce0a0" }}
                />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-xs text-[#4cc9f0]">{e.evidence_id}</span>
                    <span className="chip rounded-sm px-1.5 py-0.5 text-[10px]">{e.item_type}</span>
                    <StatusBadge status={e.status} />
                  </div>
                  <p className="mt-1 truncate text-sm font-medium text-[#dfe9f5]">{e.title}</p>
                </div>
                <div className="text-right text-[10px] uppercase tracking-[0.12em] text-[#7e93b3]">
                  <div className={e.extracted ? "term" : "text-[#46597a]"}>
                    {e.extracted ? "extracted" : "pending"}
                  </div>
                  <div className="mt-1 text-[#46597a]">{fmtTime(e.created_at)}</div>
                </div>
              </Card>
            ))}
          </div>
        )}
      </section>

      <section aria-labelledby="log-evidence-heading">
        <SectionTitle>
          <span id="log-evidence-heading">Log evidence</span>
        </SectionTitle>
        <Card className="hud-scan space-y-3 p-4">
          <div>
            <label htmlFor="evidence-type" className="mb-1 block text-[10px] uppercase tracking-[0.18em] text-[#7e93b3]">Type</label>
            <select
              id="evidence-type"
              value={itemType}
              onChange={(e) => setItemType(e.target.value)}
              className="field rounded-sm px-3 py-2"
            >
              {ITEM_TYPES.map((t) => (
                <option key={t} value={t} className="bg-[#070d1c]">
                  {t}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="evidence-title" className="mb-1 block text-[10px] uppercase tracking-[0.18em] text-[#7e93b3]">Title</label>
            <input
              id="evidence-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Post-mortem report…"
              className="field rounded-sm px-3 py-2"
            />
          </div>
          <div>
            <label htmlFor="evidence-text" className="mb-1 block text-[10px] uppercase tracking-[0.18em] text-[#7e93b3]">
              Text content
            </label>
            <textarea
              id="evidence-text"
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={5}
              placeholder="Paste or describe the evidence…"
              className="field resize-none rounded-sm px-3 py-2"
            />
          </div>
          <div>
            <label htmlFor="evidence-file" className="mb-1 block text-[10px] uppercase tracking-[0.18em] text-[#7e93b3]">
              Or attach file
            </label>
            <input
              id="evidence-file"
              type="file"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="w-full text-xs text-[#7e93b3] file:mr-3 file:rounded-sm file:border file:border-[#14305c] file:bg-[#0b1428] file:px-3 file:py-1.5 file:text-[10px] file:uppercase file:tracking-[0.14em] file:text-[#4cc9f0]"
            />
          </div>
          <button
            onClick={() => uploadMutation.mutate({ itemType, title, text, file })}
            disabled={uploadMutation.isPending || (!text.trim() && !file)}
            className="btn-cmd w-full rounded-sm px-3 py-2.5"
          >
            {uploadMutation.isPending ? "Transmitting…" : "Log evidence"}
          </button>
          {uploadMutation.isError && (
            <p role="alert" className="term-danger text-xs">{(uploadMutation.error as Error).message}</p>
          )}
        </Card>
        <p className="mt-2 text-[10px] uppercase leading-relaxed tracking-[0.12em] text-[#46597a]">
          After logging evidence, run analysis from Overview to extract facts, find constraints
          and generate scenario candidates.
        </p>
      </section>
    </div>
  );
}
