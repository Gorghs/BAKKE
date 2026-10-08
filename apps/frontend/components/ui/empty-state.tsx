"use client";

export function EmptyState({ message }: { message: string }) {
  return (
    <div className="hud-panel hud-corners relative rounded-md border-dashed py-10 text-center">
      <p className="px-4 text-xs uppercase tracking-[0.16em] text-[#7e93b3]">{message}</p>
      <p className="mt-2 text-[10px] tracking-[0.3em] text-[#46597a]">NO DATA</p>
    </div>
  );
}
