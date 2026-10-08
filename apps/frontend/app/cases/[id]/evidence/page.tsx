"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import axios from "axios";
import { useState } from "react";
import { api, cn, fmtTime } from "@/lib/api";
import type { EvidenceOut } from "@/lib/types";
import { Card, EmptyState, SectionTitle, Spinner, StatusBadge } from "@/components/ui";

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

export default function EvidencePage() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();
  const [itemType, setItemType] = useState("DOCUMENT");
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);

  const { data: evidence, isLoading } = useQuery({
    queryKey: ["evidence", id],
    queryFn: async () => (await api.get<EvidenceOut[]>(`/cases/${id}/evidence`)).data,
  });

  const uploadMutation = useMutation({
    mutationFn: async () => {
      const fd = new FormData();
      fd.append("item_type", itemType);
      fd.append("title", title || itemType);
      fd.append("description", title || itemType);
      fd.append("raw_text", text);
      if (file) fd.append("file", file);
      const { data } = await axios.post(`${api.defaults.baseURL}/cases/${id}/evidence`, fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      return data;
    },
    onSuccess: () => {
      setTitle("");
      setText("");
      setFile(null);
      qc.invalidateQueries({ queryKey: ["evidence", id] });
      qc.invalidateQueries({ queryKey: ["case", id] });
      qc.invalidateQueries({ queryKey: ["dashboard", id] });
    },
  });

  return (
    <div className="grid gap-8 lg:grid-cols-[1fr_340px]">
      <section>
        <div className="mb-3 flex items-center justify-between">
          <SectionTitle>Evidence items</SectionTitle>
          <span className="text-[10px] uppercase tracking-[0.18em] text-[#46597a]">
            {evidence?.length ?? 0} items
          </span>
        </div>
        {isLoading ? (
          <Spinner />
        ) : !evidence || evidence.length === 0 ? (
          <EmptyState message="No evidence logged in this case file." />
        ) : (
          <div className="space-y-2">
            {evidence.map((e, i) => (
              <Card key={e.id} className={cn("hover-glow hud-sweep flex items-center gap-3 p-3", "enter", `enter-${Math.min(i + 1, 6)}`)}>
                <span
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

      <section>
        <SectionTitle>Log evidence</SectionTitle>
        <Card className="hud-scan space-y-3 p-4">
          <div>
            <label className="mb-1 block text-[10px] uppercase tracking-[0.18em] text-[#7e93b3]">Type</label>
            <select
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
            <label className="mb-1 block text-[10px] uppercase tracking-[0.18em] text-[#7e93b3]">Title</label>
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Post-mortem report…"
              className="field rounded-sm px-3 py-2"
            />
          </div>
          <div>
            <label className="mb-1 block text-[10px] uppercase tracking-[0.18em] text-[#7e93b3]">
              Text content
            </label>
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={5}
              placeholder="Paste or describe the evidence…"
              className="field resize-none rounded-sm px-3 py-2"
            />
          </div>
          <div>
            <label className="mb-1 block text-[10px] uppercase tracking-[0.18em] text-[#7e93b3]">
              Or attach file
            </label>
            <input
              type="file"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="w-full text-xs text-[#7e93b3] file:mr-3 file:rounded-sm file:border file:border-[#14305c] file:bg-[#0b1428] file:px-3 file:py-1.5 file:text-[10px] file:uppercase file:tracking-[0.14em] file:text-[#4cc9f0]"
            />
          </div>
          <button
            onClick={() => uploadMutation.mutate()}
            disabled={uploadMutation.isPending || (!text.trim() && !file)}
            className="btn-cmd w-full rounded-sm px-3 py-2.5"
          >
            {uploadMutation.isPending ? "Transmitting…" : "Log evidence"}
          </button>
          {uploadMutation.isError && (
            <p className="term-danger text-xs">{(uploadMutation.error as Error).message}</p>
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
