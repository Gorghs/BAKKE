"use client";

export function ErrorState({ message }: { message: string }) {
  return (
    <div
      role="alert"
      className="hud-panel hud-corners relative rounded-md border-dashed border-[#ff5c5c]/50 py-10 text-center"
    >
      <p className="term-danger px-4 text-xs uppercase tracking-[0.16em]">{message}</p>
      <p className="mt-2 text-[10px] tracking-[0.3em] text-[#46597a]">SIGNAL LOST</p>
    </div>
  );
}
