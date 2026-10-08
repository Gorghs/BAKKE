"use client";

export function Spinner() {
  return (
    <div
      role="status"
      className="flex items-center justify-center gap-3 py-16 text-xs uppercase tracking-[0.2em] text-[#7e93b3]"
    >
      <div className="radar">
        <div className="blip" />
      </div>
      <span>scanning</span>
    </div>
  );
}
