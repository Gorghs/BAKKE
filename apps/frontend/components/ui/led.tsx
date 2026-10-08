"use client";

export function Led({ color, pulse = true }: { color: string; pulse?: boolean }) {
  return (
    <span
      aria-hidden="true"
      className={pulse ? "led" : "led-static"}
      style={{ background: color, color, boxShadow: `0 0 6px ${color}88` }}
    />
  );
}
