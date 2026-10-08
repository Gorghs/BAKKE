"use client";

export function SeverityDot({ level }: { level: string }) {
  const color = level === "HARD" ? "#ff5c5c" : level === "SOFT" ? "#ffb454" : "#7e93b3";
  return (
    <span
      aria-hidden="true"
      className="led"
      style={{ background: color, color, animationDuration: level === "HARD" ? "0.8s" : "1.6s" }}
      title={level}
    />
  );
}
