"use client";

import { cn } from "@/lib/utilities";

export function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={cn("hud-panel hud-corners rounded-md", className)}>{children}</div>
  );
}
