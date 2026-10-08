"use client";

import { useParams, useSearchParams } from "next/navigation";
import { useState } from "react";
import {
  Card,
  EmptyState,
  ErrorState,
  SectionTitle,
  Spinner,
  StatusBadge,
} from "@/components/ui";
import { cn } from "@/lib/utilities";
import { streamUrl } from "@/lib/api/client";
import { useScenarios } from "@/features/scenarios/hooks";
import { useScenarioVideos, useVideoSpec, useVisualizeScenario } from "@/features/visualization/hooks";

export function VisualizationPanel() {
  const { id } = useParams<{ id: string }>();
  const search = useSearchParams();
  const [scenarioId, setScenarioId] = useState(search.get("scenario") || "");

  const scenariosQuery = useScenarios(id);
  const scenarios = scenariosQuery.data;

  const survivors = (scenarios || []).filter((s) => s.is_survivor);
  const active = scenarioId || survivors[0]?.id || "";

  const videosQuery = useScenarioVideos(active);
  const specQuery = useVideoSpec(id, active);
  const visualizeMutation = useVisualizeScenario(id, active, ["videos", active]);

  if (scenariosQuery.isLoading) return <Spinner />;
  if (scenariosQuery.isError) return <ErrorState message="Scenarios could not be loaded." />;
  if (!survivors.length) {
    return <EmptyState message="No surviving scenarios to visualize. Run analysis first." />;
  }

  const videos = videosQuery.data;
  const spec = specQuery.data;
  const readyVideo = videos?.find((v) => v.status === "READY");

  return (
    <div className="space-y-8">
      <div>
        <p className="term text-[10px] uppercase tracking-[0.3em]">{"// 3d reconstruction bay"}</p>
        <h2 className="mt-1 text-lg font-black uppercase tracking-[0.1em] text-[#dfe9f5]">
          Visualization<span className="text-[#4cc9f0]">.</span>
        </h2>
        <p className="mt-1 max-w-2xl text-xs leading-relaxed text-[#7e93b3]">
          Every video is a labeled 3D animated reconstruction derived from the scenario&apos;s
          visual-only specification. It is <span className="text-[#ffb454]">not recorded footage</span>{" "}
          and contains no case reports, evidence IDs or forensic reasoning.
        </p>
      </div>

      <div role="group" aria-label="Select scenario" className="flex flex-wrap gap-2">
        {survivors.map((s) => (
          <button
            key={s.id}
            onClick={() => setScenarioId(s.id)}
            aria-pressed={active === s.id}
            className={cn(
              "rounded-sm border px-3 py-1.5 text-[10px] uppercase tracking-[0.14em] transition",
              active === s.id
                ? "border-[#4cc9f0] bg-[#0b1428] text-[#4cc9f0] shadow-[0_0_10px_rgba(76,201,240,0.25)]"
                : "border-[#14305c] text-[#7e93b3] hover:text-[#dfe9f5]"
            )}
          >
            {s.hypothesis_label} · {s.score_total}
          </button>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
        <section aria-label="Reconstruction player" className="enter enter-1">
          <div className="hud-panel hud-corners relative aspect-video overflow-hidden rounded-md bg-black">
            {readyVideo ? (
              <video
                key={readyVideo.id}
                src={streamUrl(readyVideo.id)}
                controls
                aria-label="3D animated scenario reconstruction"
                className="h-full w-full object-contain"
              />
            ) : (
              <div className="relative flex h-full flex-col items-center justify-center gap-4 text-center">
                <div className="radar h-20 w-20">
                  <div className="blip" />
                </div>
                <p className="max-w-sm text-xs uppercase leading-relaxed tracking-[0.14em] text-[#7e93b3]">
                  No reconstruction generated for{" "}
                  <span className="text-[#4cc9f0]">
                    {survivors.find((s) => s.id === active)?.hypothesis_label}
                  </span>
                </p>
                <button
                  onClick={() => visualizeMutation.mutate()}
                  disabled={visualizeMutation.isPending}
                  className="btn-cmd rounded-sm px-4 py-2"
                >
                  {visualizeMutation.isPending ? "Queuing…" : "Generate 3D animated video"}
                </button>
                {visualizeMutation.isError && (
                  <p role="alert" className="term-danger max-w-sm text-xs">
                    {(visualizeMutation.error as Error).message}
                  </p>
                )}
              </div>
            )}
          </div>
          {readyVideo && (
            <div aria-live="polite" className="mt-2 flex items-center gap-3 text-[10px] uppercase tracking-[0.12em] text-[#7e93b3]">
              <StatusBadge status={readyVideo.status} />
              <span>{readyVideo.is_mock ? "Development mock renderer" : readyVideo.status}</span>
              <span className="ml-auto truncate text-[#46597a]">{readyVideo.label_text}</span>
            </div>
          )}
          {videosQuery.isError && (
            <p role="alert" className="term-danger mt-2 text-xs">Video status unavailable.</p>
          )}
        </section>

        <div className="space-y-6">
          <section aria-label="Visual spec" className="enter enter-2">
            <SectionTitle>Visual spec (visual-only)</SectionTitle>
            <Card className="hud-scan max-h-72 overflow-y-auto p-4">
              {specQuery.isError ? (
                <p role="alert" className="term-danger text-xs">Visual spec unavailable.</p>
              ) : spec ? (
                <pre className="whitespace-pre-wrap font-mono text-[11px] leading-relaxed text-[#7e93b3]">
                  {spec.visual_prompt}
                </pre>
              ) : (
                <p className="text-xs text-[#46597a]">Spec not built yet.</p>
              )}
            </Card>
          </section>

          <section aria-label="Shot list" className="enter enter-3">
            <SectionTitle>Shot list</SectionTitle>
            <div className="space-y-1.5">
              {(spec?.shots || []).map((s) => (
                <div key={s.shot_index} className="hud-panel rounded-sm p-2 text-xs">
                  <span className="font-mono text-[#4cc9f0]">#{s.shot_index}</span>
                  <span className="ml-2 text-[#46597a]">{s.duration_seconds}s</span>
                  <p className="mt-0.5 text-[#a9bcd9]">{s.description}</p>
                </div>
              ))}
              {!spec?.shots?.length && <p className="text-xs text-[#46597a]">No shots yet.</p>}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
