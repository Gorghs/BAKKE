"use client";

import { Card, SectionTitle, StatusBadge } from "@/components/ui";
import type { VideoOut } from "@/lib/types";
import { useVisualizeScenario } from "@/features/visualization/hooks";

export function ScenarioVideoCard({
  caseId,
  scenarioId,
  isSurvivor,
  video,
}: {
  caseId: string;
  scenarioId: string;
  isSurvivor: boolean;
  video: VideoOut | null;
}) {
  const visualizeMutation = useVisualizeScenario(caseId, scenarioId, [
    "scenario",
    caseId,
    scenarioId,
  ]);

  return (
    <section aria-label="Visualization" className="enter enter-4">
      <SectionTitle>Visualization</SectionTitle>
      <Card className="hud-scan p-4">
        {video ? (
          <div>
            <StatusBadge status={video.status} />
            <p className="mt-2 text-[10px] uppercase leading-relaxed tracking-[0.1em] text-[#7e93b3]">
              {video.label_text}
            </p>
            {video.is_mock && (
              <p className="term-warn mt-1 text-[10px] uppercase tracking-[0.14em]">
                Development mock renderer.
              </p>
            )}
            <a
              href={`/cases/${caseId}/visualization?scenario=${scenarioId}`}
              className="btn-cmd mt-3 inline-block rounded-sm px-3 py-1.5"
            >
              Watch visualization
            </a>
          </div>
        ) : isSurvivor ? (
          <div className="space-y-2">
            <p className="text-[10px] uppercase leading-relaxed tracking-[0.1em] text-[#7e93b3]">
              Generate a 3D animated reconstruction of this scenario. The video is produced
              from a visual-only specification and is labeled NOT RECORDED FOOTAGE.
            </p>
            <button
              onClick={() => visualizeMutation.mutate()}
              disabled={visualizeMutation.isPending}
              className="btn-cmd w-full rounded-sm px-3 py-2"
            >
              {visualizeMutation.isPending ? "Queuing…" : "Generate 3D animated video"}
            </button>
            {visualizeMutation.isError && (
              <p role="alert" className="term-danger text-xs">
                {(visualizeMutation.error as Error).message}
              </p>
            )}
          </div>
        ) : (
          <p className="text-[10px] uppercase tracking-[0.14em] text-[#46597a]">
            Rejected scenarios are not visualized.
          </p>
        )}
      </Card>
    </section>
  );
}
